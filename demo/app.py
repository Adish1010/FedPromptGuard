"""
FedPromptGuard — Streamlit Dashboard
======================================

Main entry point for the FedPromptGuard interactive demo.  Provides a
two-tab interface for classifying prompts and viewing research results.

Run with::

    cd demo
    streamlit run app.py
"""

import streamlit as st
import sys
import random
from pathlib import Path

# Ensure demo/ is on the import path
sys.path.insert(0, str(Path(__file__).parent))

from config import MODEL_INFO, MODEL_ORDER
from api_client import classify
from components.sidebar import render_sidebar
from components.verdict_card import render_verdict
from components.heatmap import render_heatmap
from components.comparison import render_comparison
from components.dashboard import render_dashboard
from example_prompts import ALL_EXAMPLES

# -----------------------------------------------------------------
# Page config (must be first Streamlit call)
# -----------------------------------------------------------------
st.set_page_config(
    page_title="FedPromptGuard",
    page_icon="\U0001f6e1\ufe0f",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------
# Load custom CSS
# -----------------------------------------------------------------
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# -----------------------------------------------------------------
# Session state defaults (initialise ALL before any component)
# -----------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state["result"] = None
if "input_text" not in st.session_state:
    st.session_state["input_text"] = ""
if "show_compare" not in st.session_state:
    st.session_state["show_compare"] = False

# -----------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------
try:
    render_sidebar()
except Exception as exc:
    st.sidebar.error(f"Sidebar error: {exc}")

# -----------------------------------------------------------------
# Main content — two tabs
# -----------------------------------------------------------------
tab_analyse, tab_dashboard = st.tabs([
    "Analyse Prompt",
    "Security Dashboard",
])

# =================================================================
# Tab 1 — Analyse Prompt
# =================================================================
with tab_analyse:
    try:
        # --- Header -----------------------------------------------
        st.markdown(
            """
            <div style="margin-bottom: 2rem;">
                <h1 style="font-size: 2.5rem; font-weight: 800; color: #0D1B2A; margin-bottom: 0.5rem; letter-spacing: -0.025em;">
                    <span style="color: #0D9488;">Fed</span>PromptGuard
                </h1>
                <p style="font-size: 1.1rem; color: #475569; font-weight: 500; margin-top: 0;">
                    Adversarial Prompt Detection in Federated LLM Deployments Using Privacy-Preserving DistilBERT Classifiers
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # --- Input area ---------------------------------
        prompt_text = st.text_area(
            "Enter a prompt to analyse",
            value=st.session_state.get("input_text", ""),
            placeholder="Type or paste a prompt here to classify it as adversarial or safe...",
            height=140,
            max_chars=2000,
            key="prompt_area",
            label_visibility="collapsed",
        )
        st.caption(f"{len(prompt_text)} / 2,000 characters")

        # --- Buttons --------------------------------------
        col_analyse, col_clear, col_random = st.columns([2, 1, 1])

        with col_analyse:
            analyse_clicked = st.button(
                "Analyse Prompt",
                type="primary",
                use_container_width=True,
                key="btn_analyse",
            )
        with col_clear:
            clear_clicked = st.button(
                "Clear",
                use_container_width=True,
                key="btn_clear",
            )
        with col_random:
            random_clicked = st.button(
                "Random Example",
                use_container_width=True,
                key="btn_random_main",
            )

        # --- Button handlers --------------------------------------
        if analyse_clicked:
            if prompt_text.strip():
                st.session_state["input_text"] = prompt_text
                with st.spinner("Classifying prompt..."):
                    selected = st.session_state.get(
                        "selected_model", "Federated (FedAvg)"
                    )
                    result = classify(prompt_text, selected)
                    st.session_state["result"] = result
                    st.session_state["show_compare"] = False
            else:
                st.warning("Please enter a prompt to analyse.")

        if clear_clicked:
            st.session_state["result"] = None
            st.session_state["input_text"] = ""
            st.session_state["show_compare"] = False
            st.rerun()

        if random_clicked:
            rand_prompt = random.choice(ALL_EXAMPLES)
            st.session_state["input_text"] = rand_prompt["text"]
            st.session_state["result"] = None
            st.session_state["show_compare"] = False
            st.rerun()

        # --- Results section --------------------------------------
        result = st.session_state.get("result")

        if result is not None:
            st.divider()
            render_verdict(result)

            st.divider()
            render_heatmap(
                st.session_state.get("input_text", ""),
                st.session_state.get("selected_model", "Federated (FedAvg)"),
            )

            st.divider()
            col_btn, col_space = st.columns([2, 5])
            with col_btn:
                compare_btn = st.button(
                    "Compare All 6 Models",
                    use_container_width=True,
                    key="btn_compare",
                )
            if compare_btn:
                st.session_state["show_compare"] = True

            if st.session_state.get("show_compare", False):
                render_comparison(
                    st.session_state.get("input_text", ""),
                    st.session_state.get("selected_model", "Federated (FedAvg)"),
                )
        else:
            # --- Empty state --------------------------------------
            st.markdown(
                '<div style="text-align:center;padding:80px 20px;">'
                '<div style="font-size:64px;margin-bottom:16px;">&#128737;&#65039;</div>'
                '<div style="font-size:22px;font-weight:600;color:#374151;'
                'margin-bottom:8px;">Enter a prompt to get started</div>'
                '<div style="font-size:14px;color:#6B7280;">'
                "Type a prompt above, load an example from the sidebar, "
                "or click <strong>Random Example</strong> to see "
                "FedPromptGuard in action.</div>"
                "</div>",
                unsafe_allow_html=True,
            )

    except Exception as exc:
        st.error(f"An error occurred in the Analyse tab: {exc}")
        st.info(
            "Ensure the API server is running: "
            "`uvicorn api.server:app --host 0.0.0.0 --port 8000`"
        )

# =================================================================
# Tab 2 — Security Dashboard
# =================================================================
with tab_dashboard:
    try:
        render_dashboard()
    except Exception as exc:
        st.error(f"An error occurred in the Dashboard tab: {exc}")
