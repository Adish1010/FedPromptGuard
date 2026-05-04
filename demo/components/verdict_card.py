"""
Verdict Card Component
=======================

Renders the SAFE / ADVERSARIAL verdict card in the Streamlit dashboard.
Displays a colour-coded card with confidence, risk badge, and probability
gauge for each classification result.

Usage::

    from components.verdict_card import render_verdict

    result = classify("Ignore all instructions", "Federated (FedAvg)")
    render_verdict(result)
"""

import streamlit as st
from config import RISK_COLORS


def render_verdict(result: dict) -> None:
    """Render a classification result as a styled verdict card.

    Displays a two-column layout:
        - **Left**: Colour-coded verdict card with label, confidence,
          risk badge, and request metadata.
        - **Right**: Adversarial probability gauge with progress bar,
          probability breakdown, and inference time metric.

    Handles error states gracefully by showing an error banner with
    instructions to start the API server.

    Args:
        result: Classification response dict from the API.  Must contain
            at least ``'label'``.  For successful results, also expects
            ``'confidence'``, ``'risk_level'``, ``'adversarial_probability'``,
            ``'benign_probability'``, ``'request_id'``, ``'model_used'``,
            and ``'inference_time_ms'``.
    """
    label = result.get("label", "UNKNOWN")

    # --- Error state ------------------------------------------------------
    if label == "ERROR":
        st.error(result.get("error", "Unknown error"))
        st.info(
            "Ensure API server is running: "
            "`uvicorn api.server:app --host 0.0.0.0 --port 8000`"
        )
        return

    # --- Extract fields ---------------------------------------------------
    confidence   = result.get("confidence", 0)
    risk_level   = result.get("risk_level", "NONE")
    adv_prob     = result.get("adversarial_probability", 0)
    ben_prob     = result.get("benign_probability", 0)
    request_id   = result.get("request_id", "N/A")
    model_used   = result.get("model_used", "unknown")
    inf_time     = result.get("inference_time_ms", 0)

    is_adversarial = label == "ADVERSARIAL"

    # --- Layout: two columns (3:1) ----------------------------------------
    col_card, col_gauge = st.columns([3, 1])

    # =====================================================================
    # LEFT — Verdict card
    # =====================================================================
    with col_card:
        if is_adversarial:
            risk_color = RISK_COLORS.get(risk_level, "991B1B")

            # Risk badge HTML
            risk_badge = (
                f'<span style="'
                f"background:#{risk_color};"
                f"color:#FFFFFF;"
                f"padding:3px 12px;"
                f"border-radius:12px;"
                f"font-size:12px;"
                f"font-weight:600;"
                f"letter-spacing:0.5px;"
                f'">{risk_level} RISK</span>'
            )

            card_html = f"""
            <div style="
                background:#FEF2F2;
                border-left:6px solid #991B1B;
                padding:20px 24px;
                border-radius:8px;
                margin-bottom:12px;
            ">
                <div style="font-size:40px;margin-bottom:4px;">&#9888;&#65039;</div>
                <div style="
                    font-size:24px;
                    font-weight:700;
                    color:#991B1B;
                    margin-bottom:8px;
                ">ADVERSARIAL PROMPT DETECTED</div>
                <div style="
                    font-size:16px;
                    color:#374151;
                    margin-bottom:10px;
                ">Confidence: <strong>{confidence:.2%}</strong></div>
                <div style="margin-bottom:12px;">{risk_badge}</div>
                <div style="
                    font-size:11px;
                    color:#9CA3AF;
                ">ID: {request_id[:8]}... &nbsp;|&nbsp; Model: {model_used} &nbsp;|&nbsp; {inf_time:.1f}ms</div>
            </div>
            """
        else:
            card_html = f"""
            <div style="
                background:#F0FDF4;
                border-left:6px solid #166534;
                padding:20px 24px;
                border-radius:8px;
                margin-bottom:12px;
            ">
                <div style="font-size:40px;margin-bottom:4px;">&#9989;</div>
                <div style="
                    font-size:24px;
                    font-weight:700;
                    color:#166534;
                    margin-bottom:8px;
                ">PROMPT APPEARS SAFE</div>
                <div style="
                    font-size:16px;
                    color:#374151;
                    margin-bottom:10px;
                ">Confidence: <strong>{confidence:.2%}</strong></div>
                <div style="
                    font-size:11px;
                    color:#9CA3AF;
                ">ID: {request_id[:8]}... &nbsp;|&nbsp; Model: {model_used} &nbsp;|&nbsp; {inf_time:.1f}ms</div>
            </div>
            """

        st.markdown(card_html, unsafe_allow_html=True)

    # =====================================================================
    # RIGHT — Probability gauge
    # =====================================================================
    with col_gauge:
        st.metric(
            label="Adversarial Probability",
            value=f"{adv_prob:.2%}",
        )
        st.progress(float(adv_prob))
        st.caption(
            f"Adversarial: {adv_prob:.4f} &nbsp;|&nbsp; Benign: {ben_prob:.4f}"
        )
        st.metric(
            label="Inference Time",
            value=f"{inf_time:.1f}ms",
        )
