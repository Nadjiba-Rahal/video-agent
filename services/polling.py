"""
Polling logic: waits for a video job to finish WITHOUT a blind
`sleep(30)`. Checks progress every few seconds and gives up cleanly
after a timeout, instead of hanging forever.
"""

import os
import time

from config.settings import settings
from services import agnes
from services.exceptions import AgnesJobFailedError, AgnesRateLimitError, AgnesTimeoutError
from utils.helpers import timestamped_filename
from utils.logger import get_logger

log = get_logger(__name__)


def poll_until_finished(video_id: str, destination_path: str | None = None) -> str:
    """Waits for `video_id` to finish rendering, then downloads it.

    By default the file is saved under settings.output_dir with an
    auto-generated timestamped name (original behaviour). Pass an
    explicit `destination_path` to control exactly where it lands -
    used by pipeline/video_pipeline.py to save each scene as
    clip_01.mp4, clip_02.mp4, ... inside a per-run folder.
    """
    started_at = time.monotonic()
    wait_seconds = settings.poll_interval_seconds

    while True:
        elapsed = time.monotonic() - started_at
        if elapsed > settings.poll_timeout_seconds:
            raise AgnesTimeoutError(
                f"Video job {video_id} did not finish within "
                f"{settings.poll_timeout_seconds} seconds."
            )

        try:
            status_data = agnes.get_status(video_id)
        except AgnesRateLimitError:
            # Back off instead of failing the whole job: double the wait
            # (capped at 30s) and try again.
            wait_seconds = min(wait_seconds * 2, 30)
            log.warning("Rate limited while polling, backing off to %ss", wait_seconds)
            time.sleep(wait_seconds)
            continue

        status = status_data.get("status")
        log.info("Job %s status=%s (elapsed=%.0fs)", video_id, status, elapsed)

        if status == "completed":
            video_url = status_data["video_url"]
            if destination_path is None:
                os.makedirs(settings.output_dir, exist_ok=True)
                destination_path = os.path.join(settings.output_dir, timestamped_filename())
            else:
                os.makedirs(os.path.dirname(destination_path) or ".", exist_ok=True)
            return agnes.download_video(video_url, destination_path)

        if status == "failed":
            raise AgnesJobFailedError(
                f"Video job {video_id} failed on the provider's side: "
                f"{status_data.get('error', 'no reason given')}"
            )

        # reset backoff once a normal (non-429) response comes back
        wait_seconds = settings.poll_interval_seconds
        time.sleep(wait_seconds)