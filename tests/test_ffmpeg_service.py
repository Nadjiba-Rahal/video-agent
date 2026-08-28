import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from services import ffmpeg_service
from services.exceptions import FFmpegError


def test_concatenate_raises_if_a_clip_is_missing(tmp_path):
    real_clip = tmp_path / "clip_01.mp4"
    real_clip.write_bytes(b"fake")
    missing_clip = tmp_path / "clip_02.mp4"

    with pytest.raises(FFmpegError):
        ffmpeg_service.concatenate([real_clip, missing_clip], tmp_path / "final_video.mp4")


def test_concatenate_raises_with_no_clips(tmp_path):
    with pytest.raises(FFmpegError):
        ffmpeg_service.concatenate([], tmp_path / "final_video.mp4")


def test_concatenate_uses_stream_copy_first_then_succeeds(tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"fake")
    output_path = tmp_path / "final_video.mp4"

    def fake_run(cmd, capture_output, text, check):
        # Simulate ffmpeg actually writing the output file.
        output_path.write_bytes(b"fake-final")
        return MagicMock(returncode=0, stderr="")

    with patch("services.ffmpeg_service.subprocess.run", side_effect=fake_run) as mock_run:
        result = ffmpeg_service.concatenate([clip], output_path)

    assert result == output_path
    assert output_path.exists()
    # First (and only, since it "succeeded") attempt uses -c copy.
    assert "-c" in mock_run.call_args.args[0]
    assert "copy" in mock_run.call_args.args[0]


def test_concatenate_falls_back_to_reencode_on_stream_copy_failure(tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"fake")
    output_path = tmp_path / "final_video.mp4"

    calls = []

    def fake_run(cmd, capture_output, text, check):
        calls.append(cmd)
        if "copy" in cmd:
            return MagicMock(returncode=1, stderr="codec mismatch")
        output_path.write_bytes(b"fake-final")
        return MagicMock(returncode=0, stderr="")

    with patch("services.ffmpeg_service.subprocess.run", side_effect=fake_run):
        result = ffmpeg_service.concatenate([clip], output_path)

    assert result == output_path
    assert len(calls) == 2
    assert "libx264" in calls[1]
