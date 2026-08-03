"""
Loads all configuration from environment variables / .env file.

Every other file in this project imports "settings" from here instead
of calling os.getenv() directly. That way there is only ONE place
that knows about secret names.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load variables from a local .env file (if it exists) into os.environ
load_dotenv()


def _get_int(name: str, default: int) -> int:
    """Read an env var as int, falling back to a default if missing/invalid."""
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # LLM
    model_id: str = os.getenv("MODEL_ID", "gpt-4o-mini")
    model_api_key: str = os.getenv("MODEL_API_KEY", "")

    # Video generation service ("agnes")
    agnes_api_url: str = os.getenv("AGNES_API_URL", "")
    agnes_api_key: str = os.getenv("AGNES_API_KEY", "")

    # Polling behaviour
    poll_interval_seconds: int = _get_int("POLL_INTERVAL_SECONDS", 3)
    poll_timeout_seconds: int = _get_int("POLL_TIMEOUT_SECONDS", 300)

    # Gradio server
    gradio_server_name: str = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
    gradio_server_port: int = _get_int("GRADIO_SERVER_PORT", 7860)

    # Paths
    output_dir: str = os.path.join("outputs", "videos")
    log_dir: str = "logs"


# Single shared instance imported everywhere else: `from config.settings import settings`
settings = Settings()


def validate_settings() -> list[str]:
    """
    Checks that the required secrets are actually set.
    Returns a list of problems (empty list = everything looks fine).
    Call this once at startup so missing keys fail loudly and early.
    """
    problems = []
    if not settings.model_api_key:
        problems.append("MODEL_API_KEY is missing (needed to call the LLM).")
    if not settings.agnes_api_url:
        problems.append("AGNES_API_URL is missing (needed for video generation).")
    if not settings.agnes_api_key:
        problems.append("AGNES_API_KEY is missing (needed for video generation).")
    return problems
