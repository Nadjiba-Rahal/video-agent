"""Small reusable helper functions used across the project."""

import re
from datetime import datetime


def timestamped_filename(prefix: str = "video", extension: str = "mp4") -> str:
    """
    Builds a unique, sortable filename like:
        video_20260803_213501.mp4
    instead of always overwriting a single "video.mp4".
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.{extension}"


def slugify(text: str, max_length: int = 40) -> str:
    """Turns 'A video about Paris!' into 'a-video-about-paris' for safe filenames."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_length] or "untitled"
