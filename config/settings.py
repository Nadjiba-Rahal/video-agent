"""
Centralized configuration - the single source of truth for this project.

Every environment variable, API key, model name/fallback, timeout, retry
setting, path, and other tunable constant lives HERE and only here. Every
other module (agents/, agent/, tools/, pipeline/, services/, ui/) imports
the shared `settings` instance instead of calling `os.getenv()` or hardcoding
a literal itself:

    from config.settings import settings
    print(settings.model_id)

Changing a model string, an API key, a timeout, or a retry/backoff value
here immediately takes effect everywhere in the pipeline - no other file
needs to be touched.

Built on `pydantic-settings`, which gives us:
- automatic loading from a local `.env` file (see `.env.example`)
- type coercion + validation with clear errors on startup
- a frozen, import-once, share-everywhere settings object
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file (config/settings.py -> project/)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All configuration for the agentic video assistant, loaded from the
    environment / a `.env` file, with sane defaults for everything that
    isn't a secret.
    """

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **values):
        if "_env_file" in values and values["_env_file"] is None:
            values["_env_file"] = ()
            import os

            from dotenv import dotenv_values

            masked: dict[str, str] = {}
            for key, dotenv_value in dotenv_values(BASE_DIR / ".env").items():
                if dotenv_value is not None and os.environ.get(key) == dotenv_value:
                    masked[key] = os.environ.pop(key)
            try:
                super().__init__(**values)
            finally:
                os.environ.update(masked)
            return
        super().__init__(**values)

    # ------------------------------------------------------------------
    # LLM (chat agent + planning agents), via LiteLLM
    # ------------------------------------------------------------------
    model_id: str = Field(
        default="groq/openai/gpt-oss-20b",
        description="Default LiteLLM model id used by the chat agent and, "
        "unless overridden, the Director/Storyboard planning agents.",
    )
    model_api_key: str = Field(default="", description="API key for `model_id`.")
    # Accepted as alternate env-var names for the same secret (see
    # `_bridge_api_keys` below) so existing .env files keep working
    # regardless of which name they used.
    groq_api_key: str = Field(default="", exclude=True)
    gemini_api_key: str = Field(default="", exclude=True)

    # Director / Storyboard agents default to `model_id`, but can be
    # pointed at a different (e.g. cheaper/faster) model independently,
    # purely via environment variables - no code changes required.
    director_model_id: str = Field(default="")
    storyboard_model_id: str = Field(default="")

    llm_request_timeout_seconds: int = Field(
        default=60, description="Per-request timeout for planning LLM calls."
    )

    # ------------------------------------------------------------------
    # Video generation service ("Agnes")
    # ------------------------------------------------------------------
    agnes_api_url: str = Field(default="")
    agnes_api_key: str = Field(default="")
    agnes_model: str = Field(default="agnes-video-v2.0")
    agnes_http_timeout_seconds: int = Field(default=30, description="Timeout for a single Agnes HTTP call.")
    agnes_download_timeout_seconds: int = Field(default=120, description="Timeout for downloading a finished video.")

    agnes_negative_prompt: str = Field(
        default=(
            "blurry, low quality, distorted, watermark, text, glitch, "
            "warped face, extra limbs, morphing, flickering, jump cuts, "
            "objects appearing or disappearing, inconsistent details, "
            "unnatural movement, jittery motion"
        )
    )
    agnes_frame_rate: int = Field(default=24, description="Frames per second used for all Agnes render requests.")
    agnes_num_inference_steps: int = Field(default=40)
    # Agnes only accepts frame counts following the (8n + 1) rule. These
    # are the values known to work reliably.
    agnes_valid_frame_counts: tuple[int, ...] = Field(default=(81, 121, 241, 441))
    agnes_min_frame_count: int = Field(default=49, description="Safety floor (~2s) when snapping a requested duration to (8n+1).")

    agnes_landscape_width: int = Field(default=1152)
    agnes_landscape_height: int = Field(default=768)
    agnes_portrait_width: int = Field(default=768)
    agnes_portrait_height: int = Field(default=1152)

    # Polling behaviour (single-clip `generate_video` tool AND the
    # per-scene cinematic renderer both share these values).
    poll_interval_seconds: int = Field(default=3)
    poll_timeout_seconds: int = Field(default=300)

    # Retry/backoff for transient Agnes failures (rate limits, 503s)
    # inside the multi-scene cinematic renderer.
    scene_render_max_retries: int = Field(default=5)
    scene_render_backoff_base_seconds: float = Field(default=10.0)
    scene_dispatch_pacing_seconds: float = Field(
        default=6.0, description="Delay between dispatching consecutive scene render jobs, to avoid bursting the Agnes API."
    )

    # ------------------------------------------------------------------
    # Cinematic (multi-agent) pipeline
    # ------------------------------------------------------------------
    max_scenes: int = Field(default=8, description="Safety cap on scenes per cinematic video.")
    default_scene_count: int = Field(default=3)
    default_scene_duration_seconds: float = Field(default=6.0)
    min_scene_duration_seconds: float = Field(default=2.0)
    max_scene_duration_seconds: float = Field(default=18.0)

    tts_voice: str = Field(default="en-US-ChristopherNeural", description="edge-tts voice used for scene narration.")
    tts_lead_in_padding_seconds: float = Field(
        default=0.3, description="Silence prepended to narration audio to avoid clipped first syllables."
    )

    # ------------------------------------------------------------------
    # Gradio server
    # ------------------------------------------------------------------
    gradio_server_name: str = Field(default="0.0.0.0")
    gradio_server_port: int = Field(default=7860)

    # ------------------------------------------------------------------
    # Paths (kept as pathlib.Path so callers never string-concat manually)
    # ------------------------------------------------------------------
    output_dir: Path = Field(default=BASE_DIR / "outputs" / "videos")
    scripts_dir: Path = Field(default=BASE_DIR / "outputs" / "scripts")
    log_dir: Path = Field(default=BASE_DIR / "logs")

    ffmpeg_binary: str = Field(default="ffmpeg", description="Override if ffmpeg isn't on PATH.")

    # ------------------------------------------------------------------
    # Derived / bridged values
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _bridge_api_keys(self) -> "Settings":
        """Lets MODEL_API_KEY, GROQ_API_KEY, and GEMINI_API_KEY all work as
        the LLM credential, and makes sure downstream libraries (LiteLLM,
        smolagents) that read GROQ_API_KEY / GEMINI_API_KEY straight from
        the environment still see the right value regardless of which
        variable name the user actually set in their `.env`.
        """
        import os

        resolved_key = self.model_api_key or self.groq_api_key or self.gemini_api_key
        if resolved_key:
            object.__setattr__(self, "model_api_key", resolved_key)
            os.environ.setdefault("GROQ_API_KEY", resolved_key)
            os.environ.setdefault("MODEL_API_KEY", resolved_key)

        if not self.director_model_id:
            object.__setattr__(self, "director_model_id", self.model_id)
        if not self.storyboard_model_id:
            object.__setattr__(self, "storyboard_model_id", self.model_id)

        return self

    def resolution_for(self, aspect_ratio: str) -> tuple[int, int]:
        """Maps an aspect ratio string ("16:9" / "9:16") to (width, height)."""
        if aspect_ratio == "9:16":
            return self.agnes_portrait_width, self.agnes_portrait_height
        return self.agnes_landscape_width, self.agnes_landscape_height


# Single shared instance imported everywhere else:
#   from config.settings import settings
settings = Settings()


def validate_settings() -> list[str]:
    """Checks that the required secrets are actually set.

    Returns a list of human-readable problems (empty list = all good).
    Call this once at startup so missing keys fail loudly and early,
    instead of surfacing as a confusing error deep inside a tool call.
    """
    problems: list[str] = []
    if not settings.model_api_key:
        problems.append("MODEL_API_KEY (or GROQ_API_KEY) is missing (needed to call the LLM).")
    if not settings.agnes_api_url:
        problems.append("AGNES_API_URL is missing (needed for video generation).")
    if not settings.agnes_api_key:
        problems.append("AGNES_API_KEY is missing (needed for video generation).")
    return problems
