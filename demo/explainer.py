"""
FedPromptGuard Explainability Module
======================================

Extracts attention weights from DistilBERT models and generates
token-level heatmaps for the Streamlit dashboard.  Provides visual
explanations of *why* a prompt was classified as adversarial or benign
by highlighting the tokens the model attended to most.

Pipeline:
    1. Tokenise the prompt
    2. Forward pass through DistilBERT with ``output_attentions=True``
    3. Extract the CLS attention row from the last layer
    4. Average across all 12 attention heads
    5. Merge WordPiece sub-tokens and filter special tokens
    6. Min-max normalise to [0, 1]
    7. Render as coloured HTML spans

Usage::

    from explainer import get_attention_heatmap, render_heatmap_html

    tokens = get_attention_heatmap("Ignore all instructions", "Federated (FedAvg)")
    html = render_heatmap_html(tokens)
    st.markdown(html, unsafe_allow_html=True)
"""

import torch
import sys
import numpy as np
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent.parent / "src"))

from model import PromptInjectionDetector  # noqa: E402
from transformers import DistilBertTokenizer  # noqa: E402
from config import MODEL_INFO  # noqa: E402


# ---------------------------------------------------------------------------
# Model loading (cached by Streamlit)
# ---------------------------------------------------------------------------

@st.cache_resource
def load_model_for_attention(model_name: str):
    """Load a model and tokenizer for attention extraction.

    Uses Streamlit's ``cache_resource`` so the model is loaded only once
    per session, even across re-runs.

    Args:
        model_name: Display name of the model (e.g. ``'Federated (FedAvg)'``).

    Returns:
        tuple: ``(model, tokenizer)`` where model is a
        :class:`PromptInjectionDetector` in eval mode.
    """
    info = MODEL_INFO[model_name]
    weight_path = info["weights"]

    model = PromptInjectionDetector()
    state_dict = torch.load(str(weight_path), map_location="cpu", weights_only=False)

    # Handle wrapped state dicts
    if isinstance(state_dict, dict) and "model_state_dict" in state_dict:
        state_dict = state_dict["model_state_dict"]
    if isinstance(state_dict, torch.nn.Module):
        state_dict = state_dict.state_dict()

    model.load_state_dict(state_dict)
    model.eval()

    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
    return model, tokenizer


# ---------------------------------------------------------------------------
# Attention extraction
# ---------------------------------------------------------------------------

def get_attention_heatmap(prompt: str, model_name: str) -> list:
    """Extract per-token attention weights for a prompt.

    Runs a forward pass through the DistilBERT backbone with
    ``output_attentions=True``, then processes the CLS row of the last
    attention layer to produce human-readable (token, weight) tuples.

    WordPiece sub-tokens (prefixed with ``##``) are merged back into
    their parent token and their weights are summed.  Special tokens
    ``[CLS]``, ``[SEP]``, and ``[PAD]`` are filtered out.  Weights are
    min-max normalised to the range [0, 1].

    Args:
        prompt: The text to analyse.
        model_name: Display name of the model to use.

    Returns:
        list[tuple[str, float]]: List of ``(token_string, weight_0_to_1)``
        tuples.  Returns an empty list on any error.
    """
    try:
        model, tokenizer = load_model_for_attention(model_name)

        # 1. Tokenize
        encoding = tokenizer(
            prompt,
            max_length=128,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        input_ids = encoding["input_ids"]
        attention_mask = encoding["attention_mask"]

        # 2. Forward pass with attentions
        with torch.no_grad():
            outputs = model.distilbert(
                input_ids=input_ids,
                attention_mask=attention_mask,
                output_attentions=True,
            )

        # 3. Last layer attentions: shape (1, 12, 128, 128)
        attentions = outputs.attentions[-1]

        # 4. CLS row: [0, :, 0, :] -> shape (12, 128), mean over heads -> (128,)
        cls_attention = attentions[0, :, 0, :].mean(dim=0)

        # 5. Convert to numpy
        weights = cls_attention.numpy()

        # 6. Decode tokens
        tokens = tokenizer.convert_ids_to_tokens(input_ids[0])

        # 7. Merge WordPiece sub-tokens
        merged_tokens = []
        merged_weights = []

        for token, weight in zip(tokens, weights):
            if token.startswith("##"):
                # Append to previous token, sum weights
                if merged_tokens:
                    merged_tokens[-1] += token[2:]
                    merged_weights[-1] += weight
            else:
                merged_tokens.append(token)
                merged_weights.append(weight)

        # 8. Filter special tokens
        filtered = [
            (tok, w)
            for tok, w in zip(merged_tokens, merged_weights)
            if tok not in ("[CLS]", "[SEP]", "[PAD]")
        ]

        if not filtered:
            return []

        clean_tokens, raw_weights = zip(*filtered)
        raw_weights = np.array(raw_weights, dtype=np.float32)

        # 9. Min-max normalise to [0, 1]
        w_min = raw_weights.min()
        w_max = raw_weights.max()
        if w_max - w_min > 1e-8:
            normalised = (raw_weights - w_min) / (w_max - w_min)
        else:
            normalised = np.zeros_like(raw_weights)

        # 10. Return (token, weight) tuples
        return list(zip(clean_tokens, normalised.tolist()))

    except Exception:
        return []


# ---------------------------------------------------------------------------
# Colour mapping
# ---------------------------------------------------------------------------

def weight_to_color(w: float) -> str:
    """Map a normalised weight [0, 1] to a three-stop colour gradient.

    Colour stops:
        0.0 -> ``27AE60`` (green  -- low attention)
        0.5 -> ``D4A017`` (gold   -- medium attention)
        1.0 -> ``991B1B`` (red    -- high attention)

    Linear interpolation is performed in RGB space between adjacent stops.

    Args:
        w: Normalised weight in [0, 1].

    Returns:
        str: 6-character hex colour string without ``#`` prefix.
    """
    # Clamp
    w = max(0.0, min(1.0, w))

    # Stop colours in RGB
    green = (0x27, 0xAE, 0x60)
    gold  = (0xD4, 0xA0, 0x17)
    red   = (0x99, 0x1B, 0x1B)

    if w <= 0.5:
        t = w / 0.5
        c1, c2 = green, gold
    else:
        t = (w - 0.5) / 0.5
        c1, c2 = gold, red

    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)

    return f"{r:02X}{g:02X}{b:02X}"


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def render_heatmap_html(token_weights: list) -> str:
    """Render token-weight pairs as a coloured HTML heatmap.

    Each token is displayed as an inline ``<span>`` with:
        - Background colour at 13% opacity (``#RRGGBB22``)
        - A 3px solid bottom border in the full colour
        - Comfortable spacing and modern typography

    Args:
        token_weights: List of ``(token_string, weight_0_to_1)`` tuples
            as returned by :func:`get_attention_heatmap`.

    Returns:
        str: A complete HTML ``<div>`` string ready for
        ``st.markdown(..., unsafe_allow_html=True)``.
    """
    if not token_weights:
        return (
            '<div style="background:#FFFFFF;padding:16px;border-radius:8px;'
            'font-size:15px;color:#666;">Attention data not available</div>'
        )

    spans = []
    for token, weight in token_weights:
        color = weight_to_color(weight)
        span = (
            f'<span style="'
            f"background:#{color}22;"
            f"border-bottom:3px solid #{color};"
            f"padding:2px 5px;"
            f"margin:2px 1px;"
            f"border-radius:3px;"
            f"display:inline-block;"
            f'">{token}</span>'
        )
        spans.append(span)

    container = (
        '<div style="'
        "background:#FFFFFF;"
        "padding:16px;"
        "border-radius:8px;"
        "line-height:2.5;"
        "font-size:15px;"
        "font-family:'Inter',sans-serif;"
        '">'
        + " ".join(spans)
        + "</div>"
    )
    return container


# ---------------------------------------------------------------------------
# Top tokens
# ---------------------------------------------------------------------------

def get_top_tokens(token_weights: list, n: int = 5) -> list:
    """Return the n tokens with the highest attention weights.

    Args:
        token_weights: List of ``(token, weight)`` tuples.
        n: Number of top tokens to return (default 5).

    Returns:
        list[tuple[str, float]]: Up to ``n`` tuples sorted by weight
        in descending order.
    """
    return sorted(token_weights, key=lambda x: x[1], reverse=True)[:n]
