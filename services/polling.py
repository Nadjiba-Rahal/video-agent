"""
Polling logic: waits for a video job to finish WITHOUT a blind
`sleep(30)`. Checks progress every few seconds and gives up cleanly
after a timeout, instead of hanging forever.
"""

import os
import time

from config.settings import settings
from services import agnes
from services.exceptions import AgnesJobFailedError, AgnesTimeoutError
from utils.helpers import timestamped_filename
from utils.logger import get_logger

log = get_logger(__name__)


def poll_until_finished(task_id: str) -> str:
    """
    Polls the video API every `poll_interval_seconds` until the job is
    "completed" or "failed", or until `poll_timeout_seconds` is reached.

    Returns the local file path of the downloaded video.
    """
    started_at = time.monotonic()

    while True:
        elapsed = time.monotonic() - started_at
        if elapsed > settings.poll_timeout_seconds:
            raise AgnesTimeoutError(
                f"Video job {task_id} did not finish within "
                f"{settings.poll_timeout_seconds} seconds."
            )

        status_data = agnes.get_status(task_id)
        status = status_data.get("status")
        log.info("Job %s status=%s (elapsed=%.0fs)", task_id, status, elapsed)

        if status == "completed":
            video_url = status_data["video_url"]
            os.makedirs(settings.output_dir, exist_ok=True)
            local_path = os.path.join(settings.output_dir, timestamped_filename())
            return agnes.download_video(video_url, local_path)

        if status == "failed":
            raise AgnesJobFailedError(
                f"Video job {task_id} failed on the provider's side: "
                f"{status_data.get('error', 'no reason given')}"
            )

        # still pending / processing -> wait a bit before checking again
        time.sleep(settings.poll_interval_seconds)
