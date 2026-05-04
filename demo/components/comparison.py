"""
Model Comparison Component
============================

Renders the "Compare All 6 Models" section in the Streamlit dashboard.
Classifies the same prompt through every model simultaneously and
highlights domain blind spots where local models disagree with the
federated model.

Usage::

    from components.comparison import render_comparison

    render_comparison("Ignore all instructions", "Federated (FedAvg)")
"""

import streamlit as st
import pandas as pd
from api_client import classify_all_models
from config import MODEL_INFO, MODEL_ORDER


def render_comparison(prompt: str, current_model: str) -> None:
    """Render a side-by-side comparison of all 6 models on a single prompt.

    Classifies the prompt through every registered model, displays the
    results in a styled table, highlights disagreements as domain blind
    spots, and shows a bar chart of adversarial confidence.

    Args:
        prompt: The prompt text to classify across all models.
        current_model: Display name of the model selected in the main
            classifier tab (used for reference but not for filtering).
    """
    st.subheader("Compare All 6 Models")

    st.info(
        "Classifying the same prompt through all 6 models simultaneously. "
        "This reveals **domain blind spots** \u2014 models trained on only one "
        "domain miss attacks from others."
    )

    # --- Run all models ---------------------------------------------------
    with st.spinner("Running all 6 models..."):
        all_results = classify_all_models(prompt)

    # --- Reference: federated verdict ------------------------------------
    fed_result = all_results.get("Federated (FedAvg)", {})
    fed_label = fed_result.get("label", "UNKNOWN")

    # --- Build DataFrame --------------------------------------------------
    rows = []
    chart_data = []
    disagreements = []

    for model_name in MODEL_ORDER:
        result = all_results.get(model_name, {})
        info = MODEL_INFO.get(model_name, {})

        label = result.get("label", "ERROR")
        confidence = result.get("confidence", 0)
        adv_prob = result.get("adversarial_probability", 0)

        # Emoji verdict
        if label == "ADVERSARIAL":
            verdict_display = "\u26a0\ufe0f ADVERSARIAL"
        elif label == "BENIGN":
            verdict_display = "\u2705 BENIGN"
        else:
            verdict_display = "\u274c ERROR"

        rows.append({
            "Model": model_name,
            "Domain": info.get("domain", "Unknown"),
            "Verdict": verdict_display,
            "Confidence": f"{confidence:.1%}",
            "F1 Score": info.get("f1", 0.0),
        })

        chart_data.append({
            "Model": model_name,
            "Adversarial Confidence": adv_prob,
            "Color": f"#{info.get('color', '888888')}",
        })

        # Track disagreements (skip errors and the federated model itself)
        if (
            label not in ("ERROR", "UNKNOWN")
            and model_name != "Federated (FedAvg)"
            and label != fed_label
        ):
            disagreements.append({
                "name": model_name,
                "domain": info.get("domain", "Unknown"),
                "label": label,
            })

    # --- Results table ----------------------------------------------------
    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Model": st.column_config.TextColumn("Model", width="medium"),
            "Domain": st.column_config.TextColumn("Domain", width="small"),
            "Verdict": st.column_config.TextColumn("Verdict", width="medium"),
            "Confidence": st.column_config.TextColumn("Confidence", width="small"),
            "F1 Score": st.column_config.ProgressColumn(
                "F1 Score",
                min_value=0.0,
                max_value=1.0,
                format="%.2f",
            ),
        },
    )

    # --- Disagreement analysis --------------------------------------------
    if disagreements:
        disagreeing_names = ", ".join(
            f"**{d['name']}** ({d['domain']})" for d in disagreements
        )
        disagreeing_labels = set(d["label"] for d in disagreements)

        # Determine the type of attack the local models missed/misjudged
        if fed_label == "ADVERSARIAL":
            miss_explanation = (
                f"missed this attack. They were trained only on their own "
                f"domain data and have never seen this type of adversarial "
                f"pattern. The federated model has cross-domain knowledge "
                f"from all 4 clients, allowing it to recognise threats that "
                f"no single local model can detect alone."
            )
        else:
            miss_explanation = (
                f"flagged this as adversarial while the federated model "
                f"considers it safe. Local models with narrow training data "
                f"tend to over-block prompts from unfamiliar domains. The "
                f"federated model's broader training helps it distinguish "
                f"legitimate queries from genuine attacks."
            )

        st.warning(
            f"**Domain Blind Spot Detected!** "
            f"{disagreeing_names} {miss_explanation}"
        )
    else:
        st.success("All models agree on this verdict.")

    # --- Bar chart --------------------------------------------------------
    st.markdown("#### Adversarial Confidence by Model")

    chart_df = pd.DataFrame(chart_data)
    chart_df = chart_df.set_index("Model")

    st.bar_chart(
        chart_df["Adversarial Confidence"],
        use_container_width=True,
    )

    st.caption(
        "Higher bars indicate stronger adversarial signal. "
        "Look for models with low bars \u2014 those are the domain blind spots."
    )

    # --- Research context expander ----------------------------------------
    if disagreements:
        with st.expander("Research Context"):
            st.markdown(
                """
**Experiment E1 (Local Models)**

Each of the 4 local models was trained on a single organisation's data
in complete isolation.  Their F1 scores range widely:

| Model | Domain | F1 Score |
|-------|--------|----------|
| Healthcare | Clinical questions | 0.74 |
| Financial | Banking queries | 0.57 |
| Security | Threat analysis | 0.48 |
| General | Broad enterprise | 0.86 |

The Security model (F1=0.48) struggles the most because security analysts
legitimately discuss exploits, making the adversarial boundary extremely
thin.  The Financial model (F1=0.57) has similar issues with transaction
fraud phrasing.

**Experiment E2 (Federated FedAvg)**

By training a single model collaboratively across all 4 clients using
Federated Averaging \u2014 without sharing any raw data \u2014 the F1 score
jumps to **0.9478**.  This is 97% of what a centralised model achieves
when given access to all data directly.

**Why local models miss cross-domain attacks**

A model trained only on healthcare data has never seen a financial fraud
prompt.  When it encounters one, it has no basis for recognition.  The
federated model has learned attack patterns from *all* domains, so it
recognises structural similarities: authority impersonation in healthcare
("I am Dr. Mehta...") looks remarkably similar to authority impersonation
in banking ("This is the RBI Compliance Division...").

This is the central contribution of FedPromptGuard: **closing domain
blind spots while preserving data privacy**.
                """
            )
