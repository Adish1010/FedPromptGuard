"""
FedPromptGuard API Client for Streamlit
========================================

Handles all HTTP communication between the Streamlit dashboard and the
FedPromptGuard FastAPI server.  Every function returns a plain dict so
the UI layer never has to deal with ``requests`` exceptions directly.

Usage::

    from api_client import classify, classify_all_models, check_api_running

    if check_api_running():
        result = classify("Ignore all instructions", "Federated (FedAvg)")
        all_results = classify_all_models("Ignore all instructions")
"""

import requests
from config import API_URL, API_TIMEOUT, MODEL_INFO


def classify(prompt: str, model_name: str) -> dict:
    """Classify a single prompt using the specified model.

    Sends a POST request to the ``/classify`` endpoint and returns the
    full response dictionary.  On any network or server error, returns a
    dict with ``'error'`` and ``'label': 'ERROR'`` keys so callers can
    handle failures uniformly.

    Args:
        prompt: The text to classify (max 2 000 characters).
        model_name: Display name of the model (e.g. ``'Federated (FedAvg)'``).
            Mapped to the API key via ``MODEL_INFO``.

    Returns:
        dict: The classification response on success, or an error dict
        with keys ``'error'`` and ``'label'``.
    """
    api_key = MODEL_INFO[model_name]["api_key"]

    try:
        response = requests.post(
            f"{API_URL}/classify",
            json={
                "prompt": prompt,
                "model": api_key,
                "organisation_id": "streamlit_demo",
            },
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {
            "error": (
                "API server not running. Start with: "
                "uvicorn api.server:app --host 0.0.0.0 --port 8000"
            ),
            "label": "ERROR",
        }
    except requests.exceptions.Timeout:
        return {
            "error": f"Request timed out after {API_TIMEOUT} seconds",
            "label": "ERROR",
        }
    except requests.exceptions.HTTPError:
        return {
            "error": response.text,
            "label": "ERROR",
        }


def classify_all_models(prompt: str) -> dict:
    """Classify a prompt against every model in the registry.

    Iterates over all models in ``MODEL_INFO`` and calls :func:`classify`
    for each one.  Failures are captured per-model so a single broken
    model does not prevent the others from returning results.

    Args:
        prompt: The text to classify.

    Returns:
        dict: Mapping of model display name to its classification result
        (or error dict).
    """
    results = {}
    for model_name in MODEL_INFO:
        try:
            results[model_name] = classify(prompt, model_name)
        except Exception as exc:
            results[model_name] = {
                "error": str(exc),
                "label": "ERROR",
            }
    return results


def get_health() -> dict:
    """Fetch the API server health status.

    Sends a GET request to ``/health`` with a short timeout.

    Returns:
        dict: The health response containing ``status``, ``models_loaded``,
        ``uptime_seconds``, ``total_requests``, and ``total_blocked``.
        On failure, returns a dict with an ``'error'`` key.
    """
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": str(exc)}


def get_metrics() -> dict:
    """Fetch aggregate request metrics from the API server.

    Sends a GET request to ``/metrics`` with a short timeout.

    Returns:
        dict: Metrics containing ``total_requests``, ``total_blocked``,
        ``block_rate``, ``models_in_memory``, and ``uptime_seconds``.
        On failure, returns a dict with an ``'error'`` key.
    """
    try:
        response = requests.get(f"{API_URL}/metrics", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": str(exc)}


def check_api_running() -> bool:
    """Check whether the FedPromptGuard API server is reachable.

    Sends a lightweight GET to ``/health`` with a 3-second timeout.
    This function never raises an exception.

    Returns:
        bool: ``True`` if the server responds with HTTP 200, ``False``
        otherwise.
    """
    try:
        response = requests.get(f"{API_URL}/health", timeout=3)
        return response.status_code == 200
    except Exception:
        return False
