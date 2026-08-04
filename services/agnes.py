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

def submit_video(
    prompt: str,
    negative_prompt: str = (
        "blurry, low quality, distorted, watermark, text, glitch, "
        "warped face, extra limbs, morphing, flickering, jump cuts, "
        "objects appearing or disappearing, inconsistent details, "
        "unnatural movement, jittery motion"
    ),
    num_frames: int = 121,
    frame_rate: int = 24,
    width: int = 1152,
    height: int = 768,
    num_inference_steps: int = 40,
    seed: int | None = None,
) -> str:
    """Submits a video generation job. Returns a video_id for status checks."""
    log.info("Submitting video job: %r", prompt[:80])
    payload = {
        "model": settings.agnes_model,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
        "width": width,
        "height": height,
        "num_inference_steps": num_inference_steps,
    }
    if seed is not None:
        payload["seed"] = seed

    try:
        response = requests.post(
            f"{settings.agnes_api_url}/v1/videos",
            json=payload,
            headers=_headers(),
            timeout=_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        raise AgnesError(f"Could not reach video API: {exc}") from exc

    _raise_for_status(response)
    video_id = response.json()["video_id"]
    log.info("Video job submitted, video_id=%s", video_id)
    return video_id

def get_status(video_id: str) -> dict:
    """
    Checks status. Returns a dict normalized to always have "status"
    and, once completed, "video_url".
    """
    try:
        response = requests.get(
            f"{settings.agnes_api_url}/agnesapi",
            params={"video_id": video_id},
            headers=_headers(),
            timeout=_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        raise AgnesError(f"Could not reach video API: {exc}") from exc

    _raise_for_status(response)
    data = response.json()
    status = data.get("status")
    result = {"status": status}

    if status == "completed":
        metadata = data.get("metadata") or {}
        video_url = metadata.get("url") or data.get("url")
        if not video_url:
            log.error("Completed job but no video URL found. Raw response: %s", data)
            raise AgnesError(f"Job completed but no video URL in response: {data}")
        result["video_url"] = video_url

    if status == "failed":
        error_info = data.get("error") or {}
        result["error"] = error_info.get("message", "unknown error")

    return result

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
