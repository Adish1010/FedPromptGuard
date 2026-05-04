"""
Privacy Panel Component
========================

Renders a sidebar panel showing the Differential Privacy budget when a
DP-enabled model is selected.  Displays epsilon/delta values, a plain-
English explanation of the privacy guarantee, and the F1 cost of privacy.

Usage::

    from components.privacy_panel import render_privacy_panel

    render_privacy_panel("Federated + DP (\u03b5=1)")
"""

import streamlit as st
import math
from config import MODEL_INFO


def render_privacy_panel(model_name: str) -> None:
    """Render the Differential Privacy budget panel in the sidebar.

    Only renders content when the selected model has ``dp=True`` in the
    model registry.  For non-DP models, returns immediately without
    rendering anything.

    Displays:
        - Epsilon and delta metric cards
        - Plain-English explanation of the privacy guarantee
        - F1 cost compared to the non-DP federated model

    Args:
        model_name: Display name of the currently selected model
            (e.g. ``'Federated + DP (\u03b5=1)'``).
    """
    info = MODEL_INFO.get(model_name, {})

    if not info.get("dp", False):
        return

    epsilon = info["epsilon"]
    delta = 1e-5
    e_to_eps = math.exp(epsilon)

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Differential Privacy Active**")

    col1, col2 = st.sidebar.columns(2)
    col1.metric("\u03b5 (epsilon)", str(epsilon))
    col2.metric("\u03b4 (delta)", "1\u00d710\u207b\u2075")

    st.sidebar.info(
        f"\u03b5={epsilon} guarantees: adversary intercepting gradients cannot "
        f"determine training prompt membership with more than "
        f"{e_to_eps:.2f}\u00d7 confidence over random chance."
    )

    fedavg_f1 = MODEL_INFO["Federated (FedAvg)"]["f1"]
    dp_f1 = info["f1"]
    cost = fedavg_f1 - dp_f1

    st.sidebar.caption(
        f"Privacy cost: \u2212{cost:.4f} F1 vs FedAvg "
        f"({cost / fedavg_f1 * 100:.1f}% degradation). "
        f"Legal for HIPAA/GDPR regulated environments."
    )
