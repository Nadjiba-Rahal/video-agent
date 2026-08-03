"""
Tests the polling logic WITHOUT calling any real API.

We fake ("mock") agnes.get_status and agnes.download_video so the
test runs instantly and needs no internet connection or API keys.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import polling
from services.exceptions import AgnesJobFailedError, AgnesTimeoutError


def test_poll_until_finished_success():
    # First check says "processing", second check says "completed".
    fake_statuses = [
        {"status": "processing"},
        {"status": "completed", "video_url": "https://example.com/video.mp4"},
    ]

    with patch("services.polling.agnes.get_status", side_effect=fake_statuses), \
         patch("services.polling.agnes.download_video", return_value="outputs/videos/fake.mp4"), \
         patch("services.polling.time.sleep"):  # skip the real wait during tests
        result = polling.poll_until_finished("fake-task-id")

    assert result == "outputs/videos/fake.mp4"


def test_poll_until_finished_job_failed():
    fake_statuses = [{"status": "failed", "error": "provider ran out of credits"}]

    with patch("services.polling.agnes.get_status", side_effect=fake_statuses), \
         patch("services.polling.time.sleep"):
        try:
            polling.poll_until_finished("fake-task-id")
            assert False, "expected AgnesJobFailedError"
        except AgnesJobFailedError:
            pass


def test_poll_until_finished_timeout():
    # Always "processing" -> should eventually raise a timeout.
    # `settings` is an immutable (frozen) dataclass, so we swap in a
    # whole replacement object for the test instead of mutating a field.
    from dataclasses import replace

    fast_timeout_settings = replace(polling.settings, poll_timeout_seconds=0)

    with patch("services.polling.agnes.get_status", return_value={"status": "processing"}), \
         patch("services.polling.time.sleep"), \
         patch("services.polling.settings", fast_timeout_settings):
        try:
            polling.poll_until_finished("fake-task-id")
            assert False, "expected AgnesTimeoutError"
        except AgnesTimeoutError:
            pass
