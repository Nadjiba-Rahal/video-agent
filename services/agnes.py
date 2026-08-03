"""
Pure API client for the video-generation provider ("agnes").

IMPORTANT: this file knows NOTHING about smolagents or the agent.
It only knows how to talk HTTP to the video provider. Keeping it
"pure" like this makes it easy to unit test and to swap providers
later without touching the agent code.

NOTE: The exact endpoint paths / JSON fields below are placeholders.
Replace them with your real provider's API docs (submit / status /
download). Everything else (polling, retries, error handling) will
keep working as-is.
"""

import requests

from config.settings import settings
from services.exceptions import (
    AgnesAuthError,
    AgnesError,
    AgnesRateLimitError,
)
from utils.logger import get_logger

log = get_logger(__name__)

_TIMEOUT = 30  # seconds, for a single HTTP request (not the whole render)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.agnes_api_key}",
        "Content-Type": "application/json",
    }


def _raise_for_status(response: requests.Response) -> None:
    """Turns HTTP error codes into our own clear exceptions."""
    if response.status_code in (401, 403):
        raise AgnesAuthError("Video API rejected the API key. Check AGNES_API_KEY.")
    if response.status_code == 429:
        raise AgnesRateLimitError("Video API rate limit hit. Slow down requests.")
    if response.status_code >= 400:
        raise AgnesError(f"Video API error {response.status_code}: {response.text[:300]}")


def submit_video(prompt: str) -> str:
    """
    Submits a video generation job.
    Returns a task_id that can be checked later with get_status().
    """
    log.info("Submitting video job: %r", prompt[:80])
    try:
        response = requests.post(
            f"{settings.agnes_api_url}/v1/videos",
            json={"prompt": prompt},
            headers=_headers(),
            timeout=_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        raise AgnesError(f"Could not reach video API: {exc}") from exc

    _raise_for_status(response)
    task_id = response.json()["task_id"]
    log.info("Video job submitted, task_id=%s", task_id)
    return task_id


def get_status(task_id: str) -> dict:
    """
    Checks the status of a video job.
    Expected return shape from the provider (adapt to the real API):
        {"status": "pending" | "processing" | "completed" | "failed",
         "video_url": "https://..." (only present when completed)}
    """
    try:
        response = requests.get(
            f"{settings.agnes_api_url}/v1/videos/{task_id}",
            headers=_headers(),
            timeout=_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        raise AgnesError(f"Could not reach video API: {exc}") from exc

    _raise_for_status(response)
    return response.json()


def download_video(video_url: str, destination_path: str) -> str:
    """Downloads the finished video to a local file. Returns the local path."""
    log.info("Downloading video to %s", destination_path)
    try:
        response = requests.get(video_url, timeout=120, stream=True)
    except requests.exceptions.RequestException as exc:
        raise AgnesError(f"Could not download video: {exc}") from exc

    _raise_for_status(response)

    with open(destination_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    log.info("Video saved to %s", destination_path)
    return destination_path
