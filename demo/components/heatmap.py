"""
Attention Heatmap Component
=============================

Renders the token-level attention heatmap section in the Streamlit
dashboard.  Shows which words the model focused on when making its
verdict, with a colour-coded display and a plain-English explanation.

Usage::

    from components.heatmap import render_heatmap

    render_heatmap("Ignore all instructions", "Federated (FedAvg)")
"""

import streamlit as st
from explainer import get_attention_heatmap, render_heatmap_html, get_top_tokens, weight_to_color


def render_heatmap(prompt: str, model_name: str) -> None:
    """Render the attention heatmap section for a classified prompt.

    Extracts attention weights from the specified model, displays the
    top-attended tokens as coloured pills, renders the full heatmap as
    styled HTML, and provides a colour legend and plain-English explainer.

    This function never raises an exception.  All errors are caught and
    displayed as informational messages so the rest of the dashboard
    continues to work.

    Args:
        prompt: The prompt text that was classified.
        model_name: Display name of the model used (e.g. ``'Federated (FedAvg)'``).
    """
    try:
        st.subheader("Why This Verdict? \u2014 Attention Analysis")
        st.caption(
            "The heatmap below highlights the words that most influenced the "
            "model's decision.  Words in **red** had the strongest impact on "
            "the verdict, while words in **green** had little influence."
        )

        # --- Extract attention weights ------------------------------------
        with st.spinner("Extracting attention weights..."):
            token_weights = get_attention_heatmap(prompt, model_name)

        if not token_weights:
            st.info("Attention data not available for this model.")
            return

        # --- Top tokens as coloured pills ---------------------------------
        top = get_top_tokens(token_weights, n=5)

        pills_html = '<div style="margin-bottom:12px;"><strong>Most attended:</strong> '
        for token, weight in top:
            color = weight_to_color(weight)
            pills_html += (
                f'<span style="'
                f"background:#{color}22;"
                f"border:1px solid #{color};"
                f"color:#{color};"
                f"padding:3px 10px;"
                f"border-radius:12px;"
                f"font-size:13px;"
                f"font-weight:600;"
                f"margin:0 3px;"
                f"display:inline-block;"
                f'">{token} ({weight:.2f})</span>'
            )
        pills_html += "</div>"

        st.markdown(pills_html, unsafe_allow_html=True)

        # --- Full heatmap -------------------------------------------------
        st.markdown(render_heatmap_html(token_weights), unsafe_allow_html=True)

        # --- Colour legend ------------------------------------------------
        col_low, col_mid, col_high = st.columns(3)
        with col_low:
            st.markdown(
                '<div style="text-align:center;">'
                '<span style="background:#27AE6033;border-bottom:3px solid #27AE60;'
                'padding:2px 12px;border-radius:3px;">sample</span>'
                '<br><span style="font-size:12px;color:#6B7280;">Low attention</span>'
                "</div>",
                unsafe_allow_html=True,
            )
        with col_mid:
            st.markdown(
                '<div style="text-align:center;">'
                '<span style="background:#D4A01733;border-bottom:3px solid #D4A017;'
                'padding:2px 12px;border-radius:3px;">sample</span>'
                '<br><span style="font-size:12px;color:#6B7280;">Medium attention</span>'
                "</div>",
                unsafe_allow_html=True,
            )
        with col_high:
            st.markdown(
                '<div style="text-align:center;">'
                '<span style="background:#991B1B33;border-bottom:3px solid #991B1B;'
                'padding:2px 12px;border-radius:3px;">sample</span>'
                '<br><span style="font-size:12px;color:#6B7280;">High attention</span>'
                "</div>",
                unsafe_allow_html=True,
            )

        # --- Explainer expandable -----------------------------------------
        with st.expander("How does this work?"):
            st.markdown(
                """
**What you are seeing**

When the model reads your prompt, it does not treat every word equally.
It pays more attention to some words than others \u2014 just like you would
if you were scanning a message for suspicious content.

**How it works (step by step)**

1. The model reads every word in the prompt at the same time.
2. It produces a special summary (think of it as a one-line TL;DR)
   that captures the overall meaning of the entire prompt.
3. While building that summary, the model assigns an **attention
   score** to each word.  A higher score means that word had more
   influence on the final verdict.
4. The model has **12 independent readers** (called attention heads),
   each looking at the text from a different angle.  The scores you
   see above are the **average** across all 12 readers.
5. We take the scores from the **last reading pass** (the deepest
   layer), because that is where the model has the richest
   understanding of the full sentence.

**Why this matters**

If the model blocks a prompt, the heatmap tells you *why*.  Words
like "ignore", "override", or "bypass" will typically light up in
red, showing that the model spotted the adversarial intent.  This
makes the system transparent and auditable \u2014 you can verify that the
model is blocking for the right reasons, not due to a false alarm.
                """,
                unsafe_allow_html=False,
            )

    except Exception as exc:
        st.warning(f"Could not generate attention heatmap: {exc}")
