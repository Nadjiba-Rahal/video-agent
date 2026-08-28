"""Small reusable helper functions used across the project.

Note: LLM JSON parsing lives in `utils/json_utils.py` (`parse_llm_json`),
not here - keeping it separate makes it easy to find and unit-test in
isolation.
"""

from __future__ import annotations

import re
from datetime import datetime

from config.settings import settings


def timestamped_filename(prefix: str = "video", extension: str = "mp4") -> str:
    """
    Builds a unique, sortable filename like:
        video_20260803_213501.mp4
    instead of always overwriting a single "video.mp4".
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.{extension}"


def timestamped_run_id(prefix: str = "run") -> str:
    """Builds an id like 'run_20260803_213501' used to namespace one
    cinematic pipeline execution (its clips, script, and final video)."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}"


def slugify(text: str, max_length: int = 40) -> str:
    """Turns 'A video about Paris!' into 'a-video-about-paris' for safe filenames."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_length] or "untitled"


def nearest_valid_frame_count(duration_seconds: float, frame_rate: int | None = None) -> int:
    """Maps a desired scene duration to the closest Agnes-supported
    num_frames value, so each Scene's `duration_seconds` (chosen by the
    Storyboard Agent) can be turned into a valid video-generation call.

    Valid frame counts and the default frame rate both come from
    `config.settings`, so they only need to be changed in one place.
    """
    frame_rate = frame_rate or settings.agnes_frame_rate
    target_frames = max(duration_seconds, 0.1) * frame_rate
    return min(settings.agnes_valid_frame_counts, key=lambda n: abs(n - target_frames))
