# -*- coding: utf-8 -*-
"""
FedPromptGuard Demo Configuration
===================================

Single source of truth for all paths, model metadata, and constants used
across the Streamlit dashboard and demo scripts.

Sections:
    - Project paths and sys.path setup
    - API connection settings
    - Model registry (MODEL_INFO) with performance metrics, privacy info,
      training data, and known blind spots for all 6 models
    - Canonical display order (MODEL_ORDER)
    - Risk classification thresholds and colour mapping
"""

from pathlib import Path
import sys

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
"""Root directory of the FedPromptGuard project."""

SRC_DIR = PROJECT_ROOT / "src"
"""Source directory containing model definitions and training code."""

sys.path.append(str(SRC_DIR))

# ---------------------------------------------------------------------------
# API connection
# ---------------------------------------------------------------------------

API_URL = "http://localhost:8000"
"""Base URL for the FedPromptGuard FastAPI server."""

API_TIMEOUT = 30
"""Default request timeout in seconds for API calls."""

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

MODEL_INFO = {
    "Healthcare Local": {
        "api_key": "local_healthcare",
        "weights": PROJECT_ROOT / "results/e1_local/local_healthcare_seed42.pt",
        "domain": "Healthcare",
        "f1": 0.7400,
        "auc": 0.9080,
        "precision": 0.6077,
        "recall": 0.9468,
        "privacy": "Full \u2014 patient data never leaves hospital servers",
        "trained_on": "MedQuAD (14,979 clinical questions)",
        "blind_spots": "Financial fraud attacks, security bypass attempts",
        "dp": False,
        "epsilon": None,
        "color": "1B4F72",
        "description": (
            "Trained exclusively on healthcare domain data. "
            "Strong on clinical attacks, weak on cross-domain threats."
        ),
    },
    "Financial Local": {
        "api_key": "local_financial",
        "weights": PROJECT_ROOT / "results/e1_local/local_financial_seed42.pt",
        "domain": "Financial Services",
        "f1": 0.5681,
        "auc": 0.9349,
        "precision": 0.4059,
        "recall": 0.9468,
        "privacy": "Full \u2014 transaction data never leaves bank servers",
        "trained_on": "FinGPT-FiQA (6,647 financial questions)",
        "blind_spots": "Clinical manipulation attacks, technical security exploits",
        "dp": False,
        "epsilon": None,
        "color": "E67E22",
        "description": (
            "Trained on banking and investment queries. "
            "Misses healthcare and security domain attacks entirely."
        ),
    },
    "Security Local": {
        "api_key": "local_security",
        "weights": PROJECT_ROOT / "results/e1_local/local_security_seed42.pt",
        "domain": "Cybersecurity",
        "f1": 0.4804,
        "auc": 0.8871,
        "precision": 0.3214,
        "recall": 0.9511,
        "privacy": "Full \u2014 incident data stays in SOC",
        "trained_on": "Fenrir v2.0 (83,237 security questions)",
        "blind_spots": "Clinical manipulation, financial fraud framing",
        "dp": False,
        "epsilon": None,
        "color": "991B1B",
        "description": (
            "Hardest detection boundary \u2014 security analysts legitimately "
            "discuss exploits. F1=0.48 reveals severe cross-domain blind spots."
        ),
    },
    "General Local": {
        "api_key": "local_general",
        "weights": PROJECT_ROOT / "results/e1_local/local_general_seed42.pt",
        "domain": "General Enterprise",
        "f1": 0.8637,
        "auc": 0.9464,
        "precision": 0.9025,
        "recall": 0.8284,
        "privacy": "Full \u2014 internal queries stay on-premise",
        "trained_on": "MPDD general dataset",
        "blind_spots": "Highly specialised domain-specific attacks",
        "dp": False,
        "epsilon": None,
        "color": "166534",
        "description": (
            "Best performing local model. MPDD covers broad attack patterns "
            "giving better generalisation."
        ),
    },
    "Federated (FedAvg)": {
        "api_key": "federated_fedavg",
        "weights": PROJECT_ROOT / "results/e2_fedavg/e2_fedavg_seed42.pt",
        "domain": "All Domains",
        "f1": 0.9478,
        "auc": 0.9972,
        "precision": 0.9213,
        "recall": 0.9762,
        "privacy": "Partial \u2014 weight updates shared, no raw data",
        "trained_on": "All 4 clients \u2014 20 FedAvg rounds",
        "blind_spots": "Minor performance cost vs centralised oracle",
        "dp": False,
        "epsilon": None,
        "color": "0D9488",
        "description": (
            "The core contribution. 97% of centralised oracle performance "
            "with zero data sharing. Closes all domain blind spots."
        ),
    },
    "Federated + DP (\u03b5=1)": {
        "api_key": "federated_dp_eps1",
        "weights": PROJECT_ROOT / "results/e3_fedavg_dp/e3_eps1_seed42_final.pt",
        "domain": "All Domains",
        "f1": 0.7989,
        "auc": 0.9510,
        "precision": 0.9475,
        "recall": 0.7058,
        "privacy": "Formal (\u03b5,\u03b4)-DP \u2014 mathematical privacy guarantee",
        "trained_on": "All 4 clients \u2014 FedAvg + DP-SGD at \u03b5=1",
        "blind_spots": "Reduced recall due to DP noise",
        "dp": True,
        "epsilon": 1.0,
        "color": "7C3AED",
        "description": (
            "Formal privacy guarantee. HIPAA/GDPR deployable. "
            "\u03b5=1 means adversary cannot determine training data membership "
            "with more than e\u22482.72\u00d7 confidence."
        ),
    },
}
"""Complete metadata registry for all 6 FedPromptGuard models.

Each entry contains:
    api_key      — Key used in API requests to ``/classify``
    weights      — Path to the ``.pt`` weight file
    domain       — Domain the model covers
    f1           — F1 score on the test set
    auc          — ROC-AUC on the test set
    precision    — Precision on the test set
    recall       — Recall on the test set
    privacy      — Human-readable privacy guarantee description
    trained_on   — Dataset and training configuration
    blind_spots  — Known weaknesses / domain gaps
    dp           — Whether Differential Privacy was used
    epsilon      — DP epsilon value (None if not DP)
    color        — Hex colour code for UI display (without #)
    description  — One-line summary of the model
"""

# ---------------------------------------------------------------------------
# Display order
# ---------------------------------------------------------------------------

MODEL_ORDER = [
    "Healthcare Local",
    "Financial Local",
    "Security Local",
    "General Local",
    "Federated (FedAvg)",
    "Federated + DP (\u03b5=1)",
]
"""Canonical display order: local models first, then federated variants."""

# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------

RISK_THRESHOLDS = {
    "CRITICAL": 0.95,
    "HIGH": 0.85,
    "MEDIUM": 0.70,
    "LOW": 0.55,
}
"""Adversarial confidence thresholds for each risk level.

A prompt labelled ADVERSARIAL with confidence >= threshold is assigned
the corresponding risk level.  Prompts below LOW are classified MINIMAL.
"""

RISK_COLORS = {
    "CRITICAL": "991B1B",
    "HIGH": "C2410C",
    "MEDIUM": "B45309",
    "LOW": "166534",
    "NONE": "166534",
}
"""Hex colour codes (without #) for each risk level in UI displays."""
