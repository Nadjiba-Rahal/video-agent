"""
Builds the LLM used by the main chat agent.
"""

from __future__ import annotations

from smolagents import LiteLLMModel

from config.settings import settings


def get_model() -> LiteLLMModel:
    """Return the configured LiteLLM model."""

    model_id = settings.model_id.strip()

    # Protect against old .env files containing a bare model name.
    # LiteLLM needs the provider prefix.
    if "/" not in model_id:
        model_id = f"groq/{model_id}"

    return LiteLLMModel(
        model_id=model_id,
        api_key=settings.model_api_key,
        temperature=0.2,
        max_tokens=1024,
    )