"""Builds the LLM the agent will think with (via litellm, so any
provider litellm supports can be used just by changing MODEL_ID)."""

from smolagents import LiteLLMModel

from config.settings import settings


def get_model() -> LiteLLMModel:
    return LiteLLMModel(
        model_id=settings.model_id,
        api_key=settings.model_api_key,
    )
