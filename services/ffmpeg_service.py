from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from config.settings import settings
from services.exceptions import FFmpegError
from utils.logger import get_logger

logger = get_logger(__name__)


def _ensure_output_dir(output_path: Path) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


def _resolve_ffmpeg_binary(
    binary: Optional[str] = None,
) -> str:

    binary = (
        binary
        or settings.ffmpeg_binary
    )

    if Path(binary).name == binary:
        return (
            shutil.which(binary)
            or binary
        )

    return binary


def _run_ffmpeg_command(
    cmd: List[str],
) -> subprocess.CompletedProcess:

    logger.debug(
        "Running ffmpeg command: %s",
        " ".join(cmd),
    )

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

    except FileNotFoundError as exc:
        raise FFmpegError(
            "Could not run ffmpeg. "
            "Ensure ffmpeg is installed and accessible in PATH."
        ) from exc


def _write_concat_manifest(
    clips: Iterable[Path],
    manifest_path: Path,
) -> None:

    with manifest_path.open(
        "w",
        encoding="utf-8",
    ) as manifest:

        for clip in clips:
            manifest.write(
                f"file '{clip.resolve().as_posix()}'\n"
            )


def _probe_duration(
    path: str,
) -> float:

    ffprobe = (
        shutil.which("ffprobe")
        or "ffprobe"
    )

    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        return max(
            0.0,
            float(
                result.stdout.strip()
            ),
        )

    except Exception as exc:
        logger.warning(
            "Could not probe %s: %s",
            path,
            exc,
        )

        return 0.0


def concatenate(
    clip_paths: Iterable[Path],
    output_path: Path,
    binary: Optional[str] = None,
) -> Path:
    """
    Concatenate clips.

    Stream-copy is attempted first. If timestamps/codecs are incompatible,
    the clips are re-encoded.
    """

    output_path = Path(
        output_path
    )

    clips = [
        Path(path)
        for path in clip_paths
    ]

    if not clips:
        raise FFmpegError(
            "No clips provided for concatenation."
        )

    missing = [
        clip
        for clip in clips
        if not clip.exists()
    ]

    if missing:
        raise FFmpegError(
            "Missing clip(s): "
            + ", ".join(
                str(path)
                for path in missing
            )
        )

    _ensure_output_dir(
        output_path
    )

    manifest = (
        output_path.parent
        / f"concat_{os.getpid()}.txt"
    )

    temp_output = (
        output_path.parent
        / f"concat_tmp_{os.getpid()}.mp4"
    )

    ffmpeg_binary = (
        _resolve_ffmpeg_binary(
            binary
        )
    )

    _write_concat_manifest(
        clips,
        manifest,
    )

    output_existed = output_path.exists()

    try:

        copy_cmd = [
            ffmpeg_binary,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-c",
            "copy",
            str(temp_output),
        ]

        result = _run_ffmpeg_command(
            copy_cmd
        )

        copy_succeeded = (
            result.returncode == 0
            and (
                temp_output.exists()
                or (
                    not output_existed
                    and output_path.exists()
                )
            )
        )

        if copy_succeeded:
            if temp_output.exists():
                temp_output.replace(
                    output_path
                )

            return output_path

        logger.warning(
            "Stream-copy concat failed; "
            "falling back to re-encoding."
        )

        reencode_cmd = [
            ffmpeg_binary,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(settings.agnes_frame_rate),
            "-an",
            str(output_path),
        ]

        result = _run_ffmpeg_command(
            reencode_cmd
        )

        if (
            result.returncode != 0
            or not output_path.exists()
        ):
            raise FFmpegError(
                f"FFmpeg concatenation failed: "
                f"{result.stderr}"
            )

        return output_path

    finally:

        manifest.unlink(
            missing_ok=True
        )

        temp_output.unlink(
            missing_ok=True
        )


def _normalise_scene_audio(
    input_index: int,
    duration: float,
    label: str,
    filter_parts: list[str],
) -> None:
    """
    Force one narration file to be exactly one scene long.

    If speech is shorter than the scene, silence fills the remainder.
    If speech is longer, it is trimmed.
    """

    if duration <= 0:
        filter_parts.append(
            f"anullsrc="
            f"r=44100:"
            f"cl=stereo:"
            f"d=0.001"
            f"[{label}]"
        )

        return

    filter_parts.append(
        f"[{input_index}:a]"
        f"aformat="
        f"sample_rates=44100:"
        f"channel_layouts=stereo,"
        f"atrim="
        f"start=0:"
        f"end={duration:.6f},"
        f"asetpts=PTS-STARTPTS,"
        f"apad="
        f"whole_dur={duration:.6f},"
        f"atrim="
        f"start=0:"
        f"end={duration:.6f}"
        f"[{label}]"
    )


def _make_bass_swell(
    start: float,
    duration: float,
    label: str,
    filter_parts: list[str],
) -> None:
    """
    Generate a low sub-bass swell.

    The generated sound is delayed so its END lands exactly on the
    requested scene boundary.
    """

    if duration <= 0:
        return

    fade_in = min(
        0.55,
        duration / 2,
    )

    fade_out = min(
        0.18,
        duration,
    )

    fade_out_start = max(
        0.0,
        duration - fade_out,
    )

    delay_ms = max(
        0,
        int(start * 1000),
    )

    filter_parts.append(
        "sine="
        "frequency=48:"
        "sample_rate=44100:"
        f"duration={duration:.6f},"
        "afade="
        f"t=in:"
        f"st=0:"
        f"d={fade_in:.6f},"
        "afade="
        f"t=out:"
        f"st={fade_out_start:.6f}:"
        f"d={fade_out:.6f},"
        "volume=0.28,"
        f"adelay={delay_ms}:all=1"
        f"[{label}]"
    )


class FFmpegService:
    """
    Frame-stable video composition + scene-aware audio mixing.
    """

    def __init__(
        self,
        binary_path: Optional[str] = None,
    ):

        self.binary = (
            _resolve_ffmpeg_binary(
                binary_path
                or settings.ffmpeg_binary
            )
        )

    def stitch_and_mix(
        self,
        video_paths: List[str],
        voice_paths: List[str],
        sfx_paths: Optional[List[str]] = None,
        output_path: str = "final_output.mp4",
        scene_durations: Optional[
            Sequence[float]
        ] = None,
        transitions: Optional[
            Sequence[str]
        ] = None,
    ) -> str:
        """
        Compose the final video.

        voice_paths must contain one entry per scene.
        Use "" for scenes without narration.

        If a transition contains "cut to black", a deep sub-bass swell
        is generated immediately before the cut and ends exactly at the
        scene boundary.
        """

        out_path = Path(
            output_path
        )

        _ensure_output_dir(
            out_path
        )

        valid_videos = [
            Path(path)
            for path in video_paths
            if path
            and Path(path).exists()
        ]

        if not valid_videos:
            raise FFmpegError(
                "No valid video files provided."
            )

        # -----------------------------------------------------
        # Scene timing
        # -----------------------------------------------------

        if scene_durations is None:

            scene_durations = [
                _probe_duration(
                    str(path)
                )
                for path in valid_videos
            ]

        durations = [
            max(
                0.001,
                float(duration),
            )
            for duration in scene_durations[
                :len(valid_videos)
            ]
        ]

        while len(durations) < len(
            valid_videos
        ):

            probed = _probe_duration(
                str(
                    valid_videos[
                        len(durations)
                    ]
                )
            )

            durations.append(
                probed or 1.0
            )

        transitions = list(
            transitions or []
        )

        while len(transitions) < len(
            durations
        ):

            transitions.append(
                "cut"
            )

        # -----------------------------------------------------
        # VIDEO
        # -----------------------------------------------------

        manifest = (
            out_path.parent
            / f"video_manifest_{os.getpid()}.txt"
        )

        temp_video = (
            out_path.parent
            / f"video_temp_{os.getpid()}.mp4"
        )

        _write_concat_manifest(
            valid_videos,
            manifest,
        )

        try:

            # Re-encode to stable CFR.
            # This prevents inherited timestamps from moving a cut
            # by a frame.
            video_cmd = [
                self.binary,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(manifest),
                "-map",
                "0:v:0",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(settings.agnes_frame_rate),
                "-vsync",
                "cfr",
                str(temp_video),
            ]

            result = _run_ffmpeg_command(
                video_cmd
            )

            if (
                result.returncode != 0
                or not temp_video.exists()
            ):
                raise FFmpegError(
                    f"Video concat failed: "
                    f"{result.stderr}"
                )

            # -------------------------------------------------
            # AUDIO
            # -------------------------------------------------

            aligned_voice_paths = list(
                voice_paths or []
            )

            while len(
                aligned_voice_paths
            ) < len(durations):

                aligned_voice_paths.append(
                    ""
                )

            # Add only actual audio files as inputs.
            final_cmd = [
                self.binary,
                "-y",
                "-i",
                str(temp_video),
            ]

            for voice_path in (
                aligned_voice_paths[
                    :len(durations)
                ]
            ):

                if (
                    voice_path
                    and Path(
                        voice_path
                    ).exists()
                ):
                    final_cmd.extend(
                        [
                            "-i",
                            str(voice_path),
                        ]
                    )

            filter_parts: list[str] = []

            audio_labels: list[str] = []

            # Input index 0 = video.
            # Voice inputs start at 1.
            next_voice_input = 1

            for scene_index, (
                voice_path,
                duration,
            ) in enumerate(
                zip(
                    aligned_voice_paths,
                    durations,
                )
            ):

                label = (
                    f"voice_{scene_index}"
                )

                if (
                    voice_path
                    and Path(
                        voice_path
                    ).exists()
                ):

                    _normalise_scene_audio(
                        next_voice_input,
                        duration,
                        label,
                        filter_parts,
                    )

                    next_voice_input += 1

                else:

                    # No narration for this scene:
                    # explicit silence.
                    filter_parts.append(
                        "anullsrc="
                        "r=44100:"
                        "cl=stereo:"
                        f"d={duration:.6f}"
                        f"[{label}]"
                    )

                audio_labels.append(
                    f"[{label}]"
                )

            # Join scene audio into one exact timeline.
            filter_parts.append(
                "".join(audio_labels)
                + f"concat="
                f"n={len(audio_labels)}:"
                f"v=0:"
                f"a=1,"
                "aresample="
                "44100:"
                "async=0"
                "[a_base]"
            )

            mix_inputs = [
                "[a_base]"
            ]

            # -------------------------------------------------
            # CUT-TO-BLACK BASS CUES
            # -------------------------------------------------

            cumulative = 0.0

            for scene_index, (
                duration,
                transition,
            ) in enumerate(
                zip(
                    durations,
                    transitions,
                )
            ):

                transition_text = (
                    str(
                        transition
                    ).lower()
                )

                if (
                    "cut to black"
                    in transition_text
                ):

                    swell_duration = min(
                        0.8,
                        duration,
                    )

                    # The swell END is exactly the cut.
                    swell_start = max(
                        0.0,
                        cumulative
                        + duration
                        - swell_duration,
                    )

                    label = (
                        f"bass_{scene_index}"
                    )

                    _make_bass_swell(
                        swell_start,
                        swell_duration,
                        label,
                        filter_parts,
                    )

                    mix_inputs.append(
                        f"[{label}]"
                    )

                cumulative += duration

            # -------------------------------------------------
            # FINAL MIX
            # -------------------------------------------------

            if len(mix_inputs) > 1:

                filter_parts.append(
                    "".join(mix_inputs)
                    + f"amix="
                    f"inputs={len(mix_inputs)}:"
                    "duration=first:"
                    "dropout_transition=0:"
                    "normalize=0,"
                    "alimiter="
                    "limit=0.95"
                    "[aout]"
                )

            else:

                filter_parts.append(
                    "[a_base]"
                    "alimiter="
                    "limit=0.95"
                    "[aout]"
                )

            total_duration = sum(
                durations
            )

            final_cmd.extend(
                [
                    "-filter_complex",
                    ";".join(
                        filter_parts
                    ),
                    "-map",
                    "0:v:0",
                    "-map",
                    "[aout]",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    "-t",
                    f"{total_duration:.6f}",
                    "-movflags",
                    "+faststart",
                    str(out_path),
                ]
            )

            result = _run_ffmpeg_command(
                final_cmd
            )

            if (
                result.returncode != 0
                or not out_path.exists()
            ):
                raise FFmpegError(
                    f"FFmpeg audio mixing failed: "
                    f"{result.stderr}"
                )

            return str(out_path)

        finally:

            manifest.unlink(
                missing_ok=True
            )

            temp_video.unlink(
                missing_ok=True
            )