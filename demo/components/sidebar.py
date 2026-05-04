"""
Sidebar Component
==================

Renders the complete Streamlit sidebar including branding, API status,
model selector with info card, privacy panel, and example prompt loader.

Usage::

    from components.sidebar import render_sidebar

    render_sidebar()
    # Then read st.session_state.selected_model, st.session_state.input_text
"""

import streamlit as st
import random
from config import MODEL_INFO, MODEL_ORDER
from api_client import check_api_running
from example_prompts import EXAMPLES, ALL_EXAMPLES
from components.privacy_panel import render_privacy_panel


def render_sidebar() -> None:
    """Render the full sidebar with all six sections.

    Manages the following session state keys:
        - ``selected_model``: Currently selected model display name
        - ``input_text``: Prompt text loaded from examples
        - ``result``: Classification result (cleared on example load)
        - ``show_compare``: Whether comparison panel is visible

    All session state reads use ``.get()`` with defaults to handle the
    very first run safely.
    """

    # =================================================================
    # Section 1 — Branding
    # =================================================================
    st.sidebar.markdown(
        '<div style="text-align:center;padding:8px 0;">'
        '<div style="font-size:48px;">&#128737;&#65039;</div>'
        '<div style="font-size:20px;font-weight:700;margin-top:4px;">'
        "FedPromptGuard</div>"
        '<div style="font-size:12px;color:#6B7280;">'
        "Adversarial Prompt Detection<br>via Federated Learning</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()

    # =================================================================
    # Section 2 — API Status
    # =================================================================
    running = check_api_running()
    if running:
        st.sidebar.success("API Server Online")
    else:
        st.sidebar.error("API Server Offline")
        st.sidebar.code(
            "uvicorn api.server:app --host 0.0.0.0 --port 8000",
            language="bash",
        )

    # =================================================================
    # Section 3 — Model Selector
    # =================================================================
    st.sidebar.subheader("Select Model")

    # Determine default index
    current = st.session_state.get("selected_model", "Federated (FedAvg)")
    default_idx = MODEL_ORDER.index(current) if current in MODEL_ORDER else 4

    selected = st.sidebar.radio(
        "Choose a model",
        options=MODEL_ORDER,
        index=default_idx,
        key="selected_model",
        label_visibility="collapsed",
    )

    info = MODEL_INFO.get(selected, {})

    # Metric cards for selected model
    mc1, mc2 = st.sidebar.columns(2)
    mc1.metric("F1 Score", f"{info.get('f1', 0):.4f}")
    mc2.metric("ROC-AUC", f"{info.get('auc', 0):.4f}")

    # =================================================================
    # Section 4 — Model Info Card
    # =================================================================
    color = info.get("color", "888888")
    domain = info.get("domain", "Unknown")
    trained_on = info.get("trained_on", "N/A")
    privacy = info.get("privacy", "N/A")
    description = info.get("description", "")
    blind_spots = info.get("blind_spots", "")

    # Build blind spots line (hide for federated models)
    blind_html = ""
    if blind_spots and "Federated" not in selected:
        blind_html = (
            f'<div style="font-size:12px;color:#991B1B;margin-top:6px;">'
            f"<strong>Blind spots:</strong> {blind_spots}</div>"
        )

    card_html = f"""
    <div style="
        border-left:4px solid #{color};
        background:#F8FAFC;
        padding:12px;
        border-radius:8px;
        margin-top:8px;
    ">
        <div style="font-size:12px;color:#6B7280;margin-bottom:4px;">
            <strong>Domain:</strong> {domain}</div>
        <div style="font-size:12px;color:#6B7280;margin-bottom:4px;">
            <strong>Trained on:</strong> {trained_on}</div>
        <div style="font-size:12px;color:#6B7280;margin-bottom:4px;">
            <strong>Privacy:</strong> {privacy}</div>
        <div style="font-size:12px;color:#374151;font-style:italic;margin-top:6px;">
            {description}</div>
        {blind_html}
    </div>
    """
    st.sidebar.markdown(card_html, unsafe_allow_html=True)

    # =================================================================
    # Section 5 — Privacy Panel (DP models only)
    # =================================================================
    render_privacy_panel(selected)

    # =================================================================
    # Section 6 — Example Prompts
    # =================================================================
    st.sidebar.divider()
    st.sidebar.subheader("Example Prompts")

    # Build flat list of options with category prefix
    option_labels = []
    option_map = {}
    for category, prompts in EXAMPLES.items():
        for prompt in prompts:
            note = prompt["note"]
            label_text = f"{category}: {note[:40]}..."
            option_labels.append(label_text)
            option_map[label_text] = prompt

    selected_label = st.sidebar.selectbox(
        "Choose an example",
        options=option_labels,
        key="example_selector",
        label_visibility="collapsed",
    )

    selected_example = option_map.get(selected_label, ALL_EXAMPLES[0])

    # Preview
    st.sidebar.text_area(
        "Preview",
        value=selected_example["text"],
        height=80,
        disabled=True,
        key="example_preview",
        label_visibility="collapsed",
    )

    # Action buttons
    btn_col1, btn_col2 = st.sidebar.columns(2)

    with btn_col1:
        if st.button("Load Example", use_container_width=True, key="btn_load"):
            st.session_state["input_text"] = selected_example["text"]
            st.session_state["result"] = None
            st.session_state["show_compare"] = False
            st.rerun()

    with btn_col2:
        if st.button("Random", use_container_width=True, key="btn_random"):
            rand_prompt = random.choice(ALL_EXAMPLES)
            st.session_state["input_text"] = rand_prompt["text"]
            st.session_state["result"] = None
            st.session_state["show_compare"] = False
            st.rerun()
