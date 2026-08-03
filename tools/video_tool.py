"""
Video generation tool.

This is the thin "glue" layer between the agent and the services/
folder. It has almost no logic of its own on purpose: submitting the
job, polling, and downloading all live in services/, so they can be
tested and reused without needing smolagents at all.
"""

from smolagents import tool

from services import agnes
from services.exceptions import AgnesError
from services.polling import poll_until_finished
from utils.logger import get_logger

log = get_logger(__name__)


@tool
def generate_video(prompt: str) -> str:
    """
    Generates a video from a text prompt and saves it locally.

    Use this only once you already have a clear, detailed prompt
    (ideally improved using facts from search_web). Submitting a job
    takes time to render, so only call this once per user request.

    Args:
        prompt: A detailed description of the video to generate.

    Returns:
        The local file path of the downloaded video, or an error
        message explaining what went wrong.
    """
    try:
        task_id = agnes.submit_video(prompt)
        local_path = poll_until_finished(task_id)
        return f"Video ready: {local_path}"
    except AgnesError as exc:
        log.error("Video generation failed: %s", exc)
        return f"Video generation failed: {exc}"
