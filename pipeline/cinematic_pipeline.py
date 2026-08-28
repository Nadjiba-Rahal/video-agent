"""
End-to-end cinematic pipeline.

Director -> Storyboard -> Agnes clips -> exact clip durations -> TTS ->
FFmpeg scene-aligned composition.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from config.settings import settings
from models.storyboard import Storyboard
from pipeline.storyboard_pipeline import build_storyboard, save_script
from pipeline.video_pipeline import generate_clips
from services.ffmpeg_service import FFmpegService
from services.voice_service import EdgeTTSVoiceProvider
from utils.helpers import timestamped_run_id
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class CinematicResult:
    run_id: str
    storyboard: Storyboard
    script_path: Path
    clip_paths: list[Path]
    final_video_path: Path


async def _synthesize_all_narration(
    storyboard: Storyboard,
    audio_dir: Path,
) -> list[str]:
    """
    Return exactly one audio entry per scene.

    Scenes without narration receive an empty string instead of being
    omitted. This preserves scene/audio alignment.
    """

    audio_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    provider = EdgeTTSVoiceProvider()

    voice_paths: list[str] = []

    for scene in storyboard.scenes:

        if not scene.narration or not scene.narration.strip():
            voice_paths.append("")
            continue

        audio_path = (
            audio_dir
            / f"scene_{scene.scene_id}_narration.mp3"
        )

        try:
            log.info(
                "Synthesizing voiceover for scene %s...",
                scene.scene_id,
            )

            path, _ = await provider.generate_speech_async(
                scene.narration,
                str(audio_path),
            )

            voice_paths.append(path)

        except Exception as exc:
            log.error(
                "TTS failed for scene %s; using silence: %s",
                scene.scene_id,
                exc,
            )

            voice_paths.append("")

    return voice_paths


def run_cinematic_pipeline(
    user_prompt: str,
) -> CinematicResult:

    run_id = timestamped_run_id()

    run_dir = (
        Path(settings.output_dir)
        / run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    log.info(
        "Starting cinematic pipeline run=%s prompt=%r",
        run_id,
        user_prompt[:80],
    )

    # ---------------------------------------------------------
    # 1. PLAN
    # ---------------------------------------------------------

    storyboard = build_storyboard(
        user_prompt
    )

    script_path = save_script(
        storyboard,
        run_id,
    )

    # ---------------------------------------------------------
    # 2. RENDER VIDEO
    # ---------------------------------------------------------

    clip_paths = generate_clips(
        storyboard,
        run_dir,
    )

    if len(clip_paths) != len(storyboard.scenes):
        raise RuntimeError(
            "Not all storyboard scenes were rendered. "
            f"Expected {len(storyboard.scenes)}, "
            f"got {len(clip_paths)}. "
            "Stopping instead of silently shifting "
            "scene/audio alignment."
        )

    # ---------------------------------------------------------
    # 3. GENERATE NARRATION
    # ---------------------------------------------------------

    voice_paths = asyncio.run(
        _synthesize_all_narration(
            storyboard,
            run_dir / "audio",
        )
    )

    # ---------------------------------------------------------
    # 4. COMPOSE
    # ---------------------------------------------------------

    output_video_path = (
        run_dir / "final_movie.mp4"
    )

    ffmpeg_service = FFmpegService(
        binary_path=settings.ffmpeg_binary
    )

    final_video_str = (
        ffmpeg_service.stitch_and_mix(
            video_paths=[
                str(path)
                for path in clip_paths
            ],
            voice_paths=voice_paths,
            output_path=str(
                output_video_path
            ),
            scene_durations=[
                scene.duration_seconds
                for scene in storyboard.scenes
            ],
            transitions=[
                scene.transition
                for scene in storyboard.scenes
            ],
        )
    )

    final_video_path = Path(
        final_video_str
    )

    log.info(
        "Cinematic pipeline run=%s complete -> %s",
        run_id,
        final_video_path,
    )

    return CinematicResult(
        run_id=run_id,
        storyboard=storyboard,
        script_path=script_path,
        clip_paths=clip_paths,
        final_video_path=final_video_path,
    )