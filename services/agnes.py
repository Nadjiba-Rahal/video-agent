"""
Client for the video-generation provider ("Agnes").

Provides both:
  - low-level functions (`submit_video`, `get_status`, `download_video`)
    used by `services/polling.py` for the single-clip `generate_video` tool
  - the higher-level `AgnesService` class used by the per-scene cinematic
    renderer (`pipeline/video_pipeline.py`)

Both paths share the same `poll_until_finished()` polling/backoff logic
from `services/polling.py` (imported lazily below to avoid a circular
import), so there is only one implementation of "wait for a video job
to finish" in the whole project.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

import requests
import time

from config.settings import settings
from services.exceptions import AgnesAuthError, AgnesError, AgnesRateLimitError
from utils.helpers import nearest_valid_frame_count
from utils.logger import get_logger

log = get_logger(__name__)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.agnes_api_key}",
        "Content-Type": "application/json",
    }


def _raise_for_status(response: requests.Response) -> None:
    """Turns HTTP error codes into clear, typed exceptions."""
    if response.status_code in (401, 403):
        raise AgnesAuthError("Video API rejected the API key. Check AGNES_API_KEY.")
    if response.status_code == 429:
        raise AgnesRateLimitError("Video API rate limit hit. Slow down requests.")
    if response.status_code >= 400:
        raise AgnesError(f"Video API error {response.status_code}: {response.text[:300]}")


def submit_video(
    prompt: str,
    negative_prompt: Optional[str] = None,
    num_frames: int = 121,
    frame_rate: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    num_inference_steps: Optional[int] = None,
    seed: Optional[int] = None,
) -> str:
    """Submits a video generation job. Returns a `video_id` for status checks."""
    negative_prompt = negative_prompt if negative_prompt is not None else settings.agnes_negative_prompt
    frame_rate = frame_rate or settings.agnes_frame_rate
    width = width or settings.agnes_landscape_width
    height = height or settings.agnes_landscape_height
    num_inference_steps = num_inference_steps or settings.agnes_num_inference_steps

    log.info("Submitting video job (%d frames): %r", num_frames, prompt[:80])
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
            timeout=settings.agnes_http_timeout_seconds,
        )
    except requests.exceptions.RequestException as exc:
        raise AgnesError(f"Could not reach video API: {exc}") from exc

    _raise_for_status(response)
    video_id = response.json()["video_id"]
    log.info("Video job submitted, video_id=%s", video_id)
    return video_id


def get_status(video_id: str) -> dict:
    """Checks status. Returns a dict normalized with 'status' and 'video_url' when completed."""
    try:
        response = requests.get(
            f"{settings.agnes_api_url}/agnesapi",
            params={"video_id": video_id},
            headers=_headers(),
            timeout=settings.agnes_http_timeout_seconds,
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

    partial_path = f"{destination_path}.part"
    max_attempts = max(1, settings.agnes_download_max_retries)

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                video_url,
                timeout=settings.agnes_download_timeout_seconds,
                stream=True,
            )
            _raise_for_status(response)

            with open(partial_path, "wb") as output_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        output_file.write(chunk)

            os.replace(partial_path, destination_path)
            log.info("Video saved to %s", destination_path)
            return destination_path

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            try:
                os.remove(partial_path)
            except FileNotFoundError:
                pass

            if attempt == max_attempts:
                raise AgnesError(
                    f"Could not download video after {max_attempts} attempts: {exc}"
                ) from exc

            wait_seconds = min(15, 2 ** (attempt - 1))
            log.warning(
                "Temporary video download failure (attempt %s/%s); retrying in %ss.",
                attempt,
                max_attempts,
                wait_seconds,
            )
            time.sleep(wait_seconds)

        except requests.exceptions.RequestException as exc:
            try:
                os.remove(partial_path)
            except FileNotFoundError:
                pass
            raise AgnesError(f"Could not download video: {exc}") from exc

    raise AgnesError("Could not download video.")


class AgnesService:
    """High-level "submit, wait, download" wrapper used by the per-scene
    cinematic video pipeline.

    Delegates the actual waiting to `services.polling.poll_until_finished`
    (imported lazily to avoid a circular import) so there is a single,
    shared implementation of polling/backoff behaviour, configured via
    `settings.poll_interval_seconds` / `settings.poll_timeout_seconds`,
    across both the single-clip tool and the multi-scene cinematic
    pipeline.
    """

    def generate_video(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        output_path: str = "output.mp4",
        duration_seconds: float = 5.0,
        progress_callback: Callable[[float], None] | None = None,
    ) -> str:
        """Full cycle: submit -> poll until finished -> download.

        `duration_seconds` is snapped to the nearest Agnes-supported
        frame count via `utils.helpers.nearest_valid_frame_count`.
        """
        from services.polling import poll_until_finished  # local import: avoids circular import

        width, height = settings.resolution_for(aspect_ratio)
        num_frames = max(
            nearest_valid_frame_count(duration_seconds, settings.agnes_frame_rate),
            settings.agnes_min_frame_count,
        )

        video_id = submit_video(
            prompt=prompt,
            width=width,
            height=height,
            num_frames=num_frames,
            frame_rate=settings.agnes_frame_rate,
        )

        return poll_until_finished(
            video_id,
            destination_path=output_path,
            progress_callback=progress_callback,
            estimated_seconds=max(30.0, duration_seconds * 12.0),
        )
