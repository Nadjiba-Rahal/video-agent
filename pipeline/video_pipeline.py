"""
Per-scene video rendering through Agnes.

The rendered file is the source of truth for duration. Agnes may snap
requested durations to supported frame counts, so we probe every completed
clip and update the Scene with its actual duration before composition.
"""

from __future__ import annotations

import random
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Union

from config.settings import settings
from models.scene import Scene
from models.storyboard import Storyboard
from services.agnes import AgnesService
from utils.logger import get_logger

log = get_logger(__name__)


def _show_render_progress(
    completed: int,
    total: int,
    scene_id: str = "",
) -> None:
    """Show one compact terminal line for scene-render progress."""
    percent = int(completed / total * 100) if total else 100
    filled = int(percent / 5)
    bar = "=" * filled + "." * (20 - filled)
    finished = f" | scene {scene_id} done" if scene_id else ""
    sys.stdout.write(
        f"\rScenes [{bar}] {percent:3d}% ({completed}/{total}){finished}"
    )
    sys.stdout.flush()
    if completed >= total:
        sys.stdout.write("\n")


def _probe_video_duration(path: str) -> float:
    """Return the exact duration reported by ffprobe."""
    ffprobe = shutil.which("ffprobe") or "ffprobe"

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        return max(0.001, float(result.stdout.strip()))

    except Exception as exc:
        log.warning(
            "Could not probe rendered clip duration %s: %s",
            path,
            exc,
        )
        return 0.0


class ParallelVideoPipeline:
    """Render scenes sequentially to respect the video API rate limit."""

    def __init__(self, agnes_service: Optional[AgnesService] = None):
        self.agnes_service = agnes_service or AgnesService()
        self.max_workers = 1

    def _build_anchor_prompt(
        self,
        scene: Scene,
        storyboard: Storyboard,
    ) -> str:
        base_prompt = scene.video_prompt

        anchors = []

        if storyboard.character_anchor:
            anchors.append(
                f"Subject: {storyboard.character_anchor}"
            )

        if storyboard.environment_anchor:
            anchors.append(
                f"Environment: {storyboard.environment_anchor}"
            )

        if anchors:
            context = " | ".join(anchors)

            return (
                f"[{context}] {base_prompt}, "
                "maintaining strict visual continuity with prior scene."
            )

        return base_prompt

    def render_scene(
        self,
        scene: Scene,
        storyboard: Storyboard,
        aspect_ratio: str,
        output_dir: Path,
    ) -> dict[str, str]:

        scene_id = str(scene.scene_id)
        out_path = output_dir / f"scene_{scene_id}.mp4"

        prompt = self._build_anchor_prompt(
            scene,
            storyboard,
        )

        log.info(
            "Rendering scene %s (requested %.1fs)...",
            scene_id,
            scene.duration_seconds,
        )

        max_retries = settings.scene_render_max_retries
        base_backoff = settings.scene_render_backoff_base_seconds

        for attempt in range(1, max_retries + 1):
            try:
                video_file = self.agnes_service.generate_video(
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    output_path=str(out_path),
                    duration_seconds=scene.duration_seconds,
                )

                actual_duration = _probe_video_duration(video_file)

                if actual_duration > 0:
                    scene.duration_seconds = actual_duration

                    log.info(
                        "Scene %s actual duration = %.6fs",
                        scene_id,
                        actual_duration,
                    )

                return {
                    "scene_id": scene_id,
                    "path": video_file,
                }

            except Exception as exc:
                error_text = str(exc).lower()

                transient = (
                    "rate limit" in error_text
                    or "429" in error_text
                    or "503" in error_text
                )

                if transient and attempt < max_retries:
                    wait_time = round(
                        base_backoff * attempt
                        + random.uniform(1.0, 3.0),
                        2,
                    )

                    log.warning(
                        "Transient Agnes error on scene %s "
                        "(attempt %s/%s). Retrying in %ss...",
                        scene_id,
                        attempt,
                        max_retries,
                        wait_time,
                    )

                    time.sleep(wait_time)
                    continue

                log.error(
                    "Failed rendering scene %s: %s",
                    scene_id,
                    exc,
                )

                raise

        raise RuntimeError(
            f"Scene {scene_id} could not be rendered."
        )

    def render_storyboard_parallel(
        self,
        storyboard: Storyboard,
        output_dir: Path,
        aspect_ratio: str = "16:9",
    ) -> list[str]:

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        results: dict[str, str] = {}
        total_scenes = len(storyboard.scenes)
        completed_scenes = 0

        _show_render_progress(0, total_scenes)

        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:

            future_to_scene = {}

            for idx, scene in enumerate(storyboard.scenes):

                future = executor.submit(
                    self.render_scene,
                    scene,
                    storyboard,
                    aspect_ratio,
                    output_dir,
                )

                future_to_scene[future] = scene

                if idx < len(storyboard.scenes) - 1:
                    time.sleep(
                        settings.scene_dispatch_pacing_seconds
                    )

            for future in as_completed(future_to_scene):

                scene = future_to_scene[future]

                try:
                    result = future.result()

                    results[
                        str(result["scene_id"])
                    ] = result["path"]

                except Exception as exc:
                    log.error(
                        "Scene %s failed after all retries: %s",
                        scene.scene_id,
                        exc,
                    )

                    results[
                        str(scene.scene_id)
                    ] = ""

                completed_scenes += 1
                _show_render_progress(
                    completed_scenes,
                    total_scenes,
                    str(scene.scene_id),
                )

        return [
            results[str(scene.scene_id)]
            for scene in storyboard.scenes
            if results.get(str(scene.scene_id))
        ]


def generate_clips(
    storyboard: Storyboard,
    run_dir: Union[str, Path],
    aspect_ratio: str = "16:9",
) -> list[Path]:

    pipeline = ParallelVideoPipeline()

    clip_paths = pipeline.render_storyboard_parallel(
        storyboard,
        Path(run_dir),
        aspect_ratio,
    )

    return [
        Path(path)
        for path in clip_paths
        if path
    ]