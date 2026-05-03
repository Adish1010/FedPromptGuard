"""
FedPromptGuard API Server
=========================

A FastAPI-based REST API for adversarial prompt injection detection
using DistilBERT-based binary classifiers trained via federated learning.

Endpoints:
    GET  /health          – Service health check
    GET  /models          – List available models
    GET  /metrics         – Request / blocking statistics
    POST /classify        – Classify a single prompt
    POST /classify/batch  – Classify up to 50 prompts in one call
"""

import sys
import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

import torch
import torch.nn.functional as F
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Project path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.model import PromptInjectionDetector  # noqa: E402
from transformers import DistilBertTokenizer     # noqa: E402

# ---------------------------------------------------------------------------
# Model registry  (model_key → relative .pt path from PROJECT_ROOT)
# ---------------------------------------------------------------------------
MODEL_REGISTRY = {
    "local_healthcare":  "results/e1_local/local_healthcare_seed42.pt",
    "local_financial":   "results/e1_local/local_financial_seed42.pt",
    "local_security":    "results/e1_local/local_security_seed42.pt",
    "local_general":     "results/e1_local/local_general_seed42.pt",
    "federated_fedavg":  "results/e2_fedavg/e2_fedavg_seed42.pt",
    "federated_dp_eps1": "results/e3_fedavg_dp/e3_eps1_seed42_final.pt",
}

# ---------------------------------------------------------------------------
# Risk thresholds
# ---------------------------------------------------------------------------
RISK_THRESHOLDS = [
    (0.95, "CRITICAL"),
    (0.85, "HIGH"),
    (0.70, "MEDIUM"),
    (0.55, "LOW"),
]

# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    """Schema for a single prompt classification request."""
    prompt: str = Field(..., max_length=2000, description="The prompt text to classify")
    model: str = Field(default="federated_fedavg", description="Model key from the registry")
    organisation_id: str = Field(default="default", description="Organisation identifier")


class ClassifyResponse(BaseModel):
    """Schema for a single prompt classification response."""
    model_config = {"protected_namespaces": ()}

    request_id: str
    timestamp: str
    prompt_length: int
    label: str
    confidence: float
    risk_level: str
    adversarial_probability: float
    benign_probability: float
    model_used: str
    inference_time_ms: float
    action: str


class BatchRequest(BaseModel):
    """Schema for a batch classification request (up to 50 prompts)."""
    prompts: List[str]
    model: str = Field(default="federated_fedavg", description="Model key from the registry")
    organisation_id: str = Field(default="default", description="Organisation identifier")


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
loaded_models: dict = {}
tokenizer: Optional[DistilBertTokenizer] = None
start_time: float = time.time()
total_requests: int = 0
total_blocked: int = 0

# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated on_event)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Pre-load the tokenizer and default model before accepting requests."""
    load_tokenizer()
    load_model("federated_fedavg")
    print("✅  Tokenizer and federated_fedavg model loaded.")
    yield


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FedPromptGuard API",
    version="1.0.0",
    description="Adversarial prompt injection detection API powered by federated-learning DistilBERT models.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def load_tokenizer() -> DistilBertTokenizer:
    """Load and cache the DistilBERT tokenizer.

    Returns:
        DistilBertTokenizer: The cached tokenizer instance.
    """
    global tokenizer
    if tokenizer is None:
        tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
    return tokenizer


def load_model(model_key: str) -> PromptInjectionDetector:
    """Load a model by its registry key, caching it for subsequent calls.

    Args:
        model_key: Key that identifies the model in MODEL_REGISTRY.

    Returns:
        PromptInjectionDetector: The loaded model in eval mode.

    Raises:
        HTTPException 404: If model_key is not in the registry.
        HTTPException 503: If the weight file cannot be loaded.
    """
    global loaded_models

    if model_key in loaded_models:
        return loaded_models[model_key]

    if model_key not in MODEL_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_key}' not found. Available: {list(MODEL_REGISTRY.keys())}",
        )

    weight_path = PROJECT_ROOT / MODEL_REGISTRY[model_key]

    try:
        model = PromptInjectionDetector()
        state_dict = torch.load(str(weight_path), map_location="cpu", weights_only=False)

        # Handle state dicts wrapped in a top-level key (e.g. {"model_state_dict": ...})
        if isinstance(state_dict, dict) and "model_state_dict" in state_dict:
            state_dict = state_dict["model_state_dict"]

        # If torch.load returned an nn.Module directly, extract its state_dict
        if isinstance(state_dict, torch.nn.Module):
            state_dict = state_dict.state_dict()

        model.load_state_dict(state_dict)
        model.eval()
        loaded_models[model_key] = model
        return model
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail=f"Weight file not found: {weight_path}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to load model '{model_key}': {exc}",
        )


def get_risk_level(confidence: float, label: str) -> str:
    """Determine the risk level based on adversarial confidence and label.

    Args:
        confidence: Model confidence for the predicted label.
        label: The predicted label ('ADVERSARIAL' or 'BENIGN').

    Returns:
        A risk-level string: CRITICAL, HIGH, MEDIUM, LOW, or MINIMAL.
    """
    if label == "BENIGN":
        return "MINIMAL"

    for threshold, level in RISK_THRESHOLDS:
        if confidence >= threshold:
            return level
    return "MINIMAL"


def run_inference(prompt: str, model_key: str) -> dict:
    """Run inference on a single prompt using the specified model.

    Tokenises the prompt, performs a forward pass, and returns a dictionary
    with prediction details including timing information.

    Args:
        prompt: The text to classify.
        model_key: Key that identifies the model in MODEL_REGISTRY.

    Returns:
        dict containing label, confidence, probabilities, risk_level,
        action, model_used, and inference_time_ms.
    """
    tok = load_tokenizer()
    model = load_model(model_key)

    encoding = tok(
        prompt,
        max_length=128,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )

    input_ids = encoding["input_ids"]
    attention_mask = encoding["attention_mask"]

    t0 = time.time()
    with torch.no_grad():
        logits = model(input_ids=input_ids, attention_mask=attention_mask)
    inference_time_ms = (time.time() - t0) * 1000

    probs = F.softmax(logits, dim=-1).squeeze()
    benign_prob = probs[0].item()
    adversarial_prob = probs[1].item()

    label = "ADVERSARIAL" if adversarial_prob > benign_prob else "BENIGN"
    confidence = max(benign_prob, adversarial_prob)
    risk_level = get_risk_level(confidence, label)
    action = "BLOCK" if label == "ADVERSARIAL" else "ALLOW"

    return {
        "label": label,
        "confidence": round(confidence, 6),
        "adversarial_probability": round(adversarial_prob, 6),
        "benign_probability": round(benign_prob, 6),
        "risk_level": risk_level,
        "action": action,
        "model_used": model_key,
        "inference_time_ms": round(inference_time_ms, 2),
    }





# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Return service health status, loaded model count, and uptime."""
    return {
        "status": "healthy",
        "models_loaded": list(loaded_models.keys()),
        "uptime_seconds": round(time.time() - start_time, 2),
        "total_requests": total_requests,
        "total_blocked": total_blocked,
    }


@app.get("/models")
async def models():
    """List every model in the registry along with default and recommended picks."""
    return {
        "available_models": list(MODEL_REGISTRY.keys()),
        "default_model": "federated_fedavg",
        "recommended": "federated_fedavg",
    }


@app.get("/metrics")
async def metrics():
    """Return aggregate request statistics and current memory footprint."""
    return {
        "total_requests": total_requests,
        "total_blocked": total_blocked,
        "block_rate": round(total_blocked / total_requests, 4) if total_requests else 0.0,
        "models_in_memory": list(loaded_models.keys()),
        "uptime_seconds": round(time.time() - start_time, 2),
    }


@app.post("/classify", response_model=ClassifyResponse)
async def classify(request: ClassifyRequest):
    """Classify a single prompt as ADVERSARIAL or BENIGN.

    Validates prompt length, runs inference, increments global counters,
    and returns a ClassifyResponse.

    Raises:
        HTTPException 400: If the prompt is empty or exceeds 2 000 characters.
    """
    global total_requests, total_blocked

    # --- input validation ---------------------------------------------------
    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")
    if len(request.prompt) > 2000:
        raise HTTPException(status_code=400, detail="Prompt exceeds 2000 character limit.")

    # --- inference -----------------------------------------------------------
    result = run_inference(request.prompt, request.model)

    # --- bookkeeping ---------------------------------------------------------
    total_requests += 1
    if result["action"] == "BLOCK":
        total_blocked += 1

    return ClassifyResponse(
        request_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        prompt_length=len(request.prompt),
        **result,
    )


@app.post("/classify/batch")
async def classify_batch(request: BatchRequest):
    """Classify a batch of prompts (maximum 50).

    Returns per-prompt results together with aggregate counts of blocked
    and allowed prompts.

    Raises:
        HTTPException 400: If the batch exceeds 50 prompts or is empty.
    """
    global total_requests, total_blocked

    if not request.prompts:
        raise HTTPException(status_code=400, detail="Prompt list must not be empty.")
    if len(request.prompts) > 50:
        raise HTTPException(status_code=400, detail="Batch size exceeds the 50-prompt limit.")

    results = []
    blocked = 0
    allowed = 0

    for prompt in request.prompts:
        if not prompt or not prompt.strip():
            results.append({"error": "Empty prompt skipped"})
            continue

        result = run_inference(prompt, request.model)

        total_requests += 1
        if result["action"] == "BLOCK":
            total_blocked += 1
            blocked += 1
        else:
            allowed += 1

        results.append(
            {
                "request_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "prompt_length": len(prompt),
                **result,
            }
        )

    return {
        "batch_size": len(request.prompts),
        "blocked": blocked,
        "allowed": allowed,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Run directly: python api/server.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
