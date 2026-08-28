from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

from config.settings import settings
from utils.llm_client import complete_json
from utils.logger import get_logger

log = get_logger(__name__)


_SYSTEM_PROMPT = """You are a Director Agent for a cinematic video pipeline.

Return ONLY valid JSON.

Extract the user's requirements:
- style
- tone
- pacing
- scene count
- scene durations
- narration/music
- important visual or continuity notes

Preserve explicit scene counts and durations exactly.
If no durations are given, use equal durations.
Keep scenes connected when the user asks for continuity.

JSON:
{
  "style": "...",
  "tone": "...",
  "pacing": "slow|medium|fast",
  "scene_count": 1,
  "scene_duration_seconds": 10,
  "scene_durations_seconds": [],
  "narration_enabled": false,
  "music_enabled": false,
  "notes": "..."
}
"""

@dataclass
class DirectorBrief:
    style: str
    tone: str
    pacing: str
    scene_count: int
    scene_duration_seconds: float
    narration_enabled: bool
    music_enabled: bool

    scene_durations_seconds: list[float] | None = None

    notes: str = ""

    @property
    def total_duration_seconds(self) -> float:

        if self.scene_durations_seconds:
            return sum(
                self.scene_durations_seconds
            )

        return (
            self.scene_count
            * self.scene_duration_seconds
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return asdict(self)


class DirectorAgent:
    """Turns a raw user idea into a DirectorBrief."""

    def __init__(
        self,
        model_id: Optional[str] = None,
    ):

        self.model_id = (
            model_id
            or settings.director_model_id
        )

    def plan(
        self,
        user_prompt: str,
    ) -> DirectorBrief:

        log.info(
            "Director Agent planning for prompt: %r",
            user_prompt[:80],
        )

        system_prompt = _SYSTEM_PROMPT.replace(
            "{max_scenes}",
            str(settings.max_scenes)
        )

        data = complete_json(
            model_id=self.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=1000,
            agent_name="Director Agent",
        )

        return self._to_brief(data)

    @staticmethod
    def _to_brief(
        data: dict[str, Any],
    ) -> DirectorBrief:

        scene_count = int(
            data.get(
                "scene_count"
            )
            or settings.default_scene_count
        )

        scene_count = max(
            1,
            min(
                scene_count,
                settings.max_scenes,
            ),
        )

        try:

            scene_duration = float(
                data.get(
                    "scene_duration_seconds"
                )
                or settings.default_scene_duration_seconds
            )

        except (
            TypeError,
            ValueError,
        ):

            scene_duration = (
                settings.default_scene_duration_seconds
            )

        scene_duration = max(
            settings.min_scene_duration_seconds,
            min(
                scene_duration,
                settings.max_scene_duration_seconds,
            ),
        )

        # ---------------------------------------------------------
        # Explicit per-scene durations
        # ---------------------------------------------------------

        raw_durations = data.get(
            "scene_durations_seconds"
        )

        durations: list[float] = []

        if isinstance(
            raw_durations,
            list,
        ):

            for value in raw_durations:

                try:

                    duration = float(
                        value
                    )

                    duration = max(
                        settings.min_scene_duration_seconds,
                        min(
                            duration,
                            settings.max_scene_duration_seconds,
                        ),
                    )

                    durations.append(
                        duration
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

        # Only trust explicit durations if they match the scene count.
        if len(durations) != scene_count:

            durations = []

        return DirectorBrief(
            style=str(
                data.get(
                    "style"
                )
                or "cinematic"
            ),

            tone=str(
                data.get(
                    "tone"
                )
                or "neutral"
            ),

            pacing=str(
                data.get(
                    "pacing"
                )
                or "medium"
            ),

            scene_count=scene_count,

            scene_duration_seconds=scene_duration,

            scene_durations_seconds=(
                durations
                or None
            ),

            narration_enabled=bool(
                data.get(
                    "narration_enabled",
                    True,
                )
            ),

            music_enabled=bool(
                data.get(
                    "music_enabled",
                    True,
                )
            ),

            notes=str(
                data.get(
                    "notes"
                )
                or ""
            ),
        )