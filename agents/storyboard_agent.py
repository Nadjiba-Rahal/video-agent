"""
Compact and fault-tolerant Storyboard Agent.

The Director processes the original user prompt.
The Storyboard Agent converts the Director brief into a small
scene list suitable for the video-generation pipeline.
"""

from __future__ import annotations

from typing import Optional

from agents.director_agent import DirectorBrief
from config.settings import settings
from models.storyboard import Storyboard
from services.exceptions import PlanningError
from utils.llm_client import complete_json
from utils.logger import get_logger


log = get_logger(__name__)


_SYSTEM_PROMPT = """
You are a cinematic storyboard planner.

The Director has already analyzed the user's original request.

Create a compact storyboard.

RULES:

- Return exactly the requested number of scenes.
- Each scene must be 60 seconds or less.
- Follow the Director's scene order and concept.
- Preserve visual continuity.
- Preserve important camera movement.
- Preserve important sound effects.
- Preserve important transitions.
- No narration when narration is disabled.
- Do not invent dialogue, text, logos, or people if prohibited.
- Keep video_prompt between 35 and 65 words.
- Keep sound effects very short.
- Keep transition very short.
- Do not explain anything.
- Return ONLY valid JSON.

IMPORTANT:
Keep the JSON extremely small so the response always finishes.

JSON:

{
  "title": "short title",
  "logline": "short sentence",
  "scenes": [
    {
      "scene_id": 1,
      "title": "short title",
      "video_prompt": "35-65 words",
      "duration_seconds": 60,
      "sound_effects": ["sound", "sound"],
      "transition": "short transition"
    }
  ]
}
"""


class StoryboardAgent:
    """Create a compact storyboard from a Director brief."""

    def __init__(
        self,
        model_id: Optional[str] = None,
    ):
        self.model_id = (
            model_id
            or settings.storyboard_model_id
        )

    def generate(
        self,
        user_prompt: str,
        brief: DirectorBrief,
    ) -> Storyboard:

        expected_count = int(
            brief.scene_count
        )

        log.info(
            "Storyboard Agent generating %s scene(s).",
            expected_count,
        )

        durations = (
            brief.scene_durations_seconds
            or []
        )

        if durations:
            duration_text = ", ".join(
                str(min(int(float(x)), 60))
                for x in durations
            )
        else:
            duration_text = str(
                min(
                    int(
                        float(
                            brief.scene_duration_seconds
                        )
                    ),
                    60,
                )
            )

        compact_prompt = f"""
Create exactly {expected_count} scenes.

STYLE:
{brief.style}

TONE:
{brief.tone}

PACING:
{brief.pacing}

DURATIONS:
{duration_text} seconds

NARRATION:
{"OFF" if not brief.narration_enabled else "ON"}

MUSIC:
{"OFF" if not brief.music_enabled else "ON"}

DIRECTOR NOTES:
{brief.notes}

REMEMBER:
Exactly {expected_count} scene objects.
Keep every video_prompt short.
Return only JSON.
"""

        try:

            data = complete_json(
                model_id=self.model_id,
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=compact_prompt,
                temperature=0.1,
                max_tokens=1600,
                agent_name="Storyboard Agent",
            )

        except Exception as exc:

            raise PlanningError(
                f"Storyboard Agent LLM call failed: {exc}"
            ) from exc

        try:

            return self._build_storyboard(
                data=data,
                brief=brief,
                source_prompt=user_prompt,
            )

        except PlanningError:
            raise

        except Exception as exc:

            raise PlanningError(
                "Could not build storyboard: "
                f"{exc}"
            ) from exc

    @staticmethod
    def _build_storyboard(
        data: dict,
        brief: DirectorBrief,
        source_prompt: str,
    ) -> Storyboard:

        scenes = data.get(
            "scenes",
            [],
        )

        if not isinstance(
            scenes,
            list,
        ):
            scenes = []

        expected_count = int(
            brief.scene_count
        )

        if len(scenes) < expected_count:

            missing = (
                expected_count
                - len(scenes)
            )

            log.warning(
                "Storyboard Agent returned %s scene(s), "
                "expected %s. Filling %s missing scene(s) locally.",
                len(scenes),
                expected_count,
                missing,
            )

            for index in range(
                len(scenes),
                expected_count,
            ):

                scenes.append(
                    {
                        "scene_id": index + 1,
                        "title": (
                            f"Continuation {index + 1}"
                        ),
                        "video_prompt": (
                            "Continue seamlessly from the "
                            "previous scene with the same "
                            "visual style, camera direction, "
                            "lighting language, atmosphere, "
                            "and physical environment. "
                            "Maintain continuous forward "
                            "camera movement and gradually "
                            "increase the unsettling feeling. "
                            "Do not introduce unrelated "
                            "characters or objects."
                        ),
                        "duration_seconds": 60,
                        "sound_effects": [
                            "deep ambient drone",
                            "subtle environmental noise",
                        ],
                        "transition": (
                            "Seamless continuous transition "
                            "from the previous scene."
                        ),
                    }
                )

        if len(scenes) > expected_count:

            log.warning(
                "Storyboard Agent returned %s scenes, "
                "expected %s. Trimming extras.",
                len(scenes),
                expected_count,
            )

            scenes = scenes[
                :expected_count
            ]

        explicit_durations = (
            brief.scene_durations_seconds
            or []
        )

        normalized = []

        for index, raw_scene in enumerate(
            scenes
        ):

            if not isinstance(
                raw_scene,
                dict,
            ):
                raw_scene = {}

            scene = dict(
                raw_scene
            )

            scene[
                "scene_id"
            ] = index + 1

            scene.setdefault(
                "title",
                f"Scene {index + 1}",
            )

            scene.setdefault(
                "video_prompt",
                "Continue the cinematic sequence "
                "seamlessly while preserving the "
                "established visual style and camera movement.",
            )

            # -----------------------------------------------------
            # Duration
            # -----------------------------------------------------

            if explicit_durations and index < len(
                explicit_durations
            ):

                duration = float(
                    explicit_durations[index]
                )

            else:

                duration = float(
                    brief.scene_duration_seconds
                )

            duration = min(
                duration,
                60.0,
            )

            scene[
                "duration_seconds"
            ] = duration

            # -----------------------------------------------------
            # Required fields
            # -----------------------------------------------------

            scene.setdefault(
                "camera_shot",
                "continuous cinematic shot",
            )

            scene.setdefault(
                "camera_motion",
                "steady forward movement",
            )

            scene.setdefault(
                "narration",
                "",
            )

            scene.setdefault(
                "music_suggestion",
                "",
            )

            scene.setdefault(
                "sound_effects",
                [],
            )

            scene.setdefault(
                "transition",
                "",
            )

            scene.setdefault(
                "mood",
                brief.tone,
            )

            scene.setdefault(
                "visual_style",
                brief.style,
            )

            scene.setdefault(
                "color_palette",
                "",
            )

            scene.setdefault(
                "negative_prompt",
                "",
            )

            normalized.append(
                scene
            )

        normalized_data = dict(
            data
        )

        normalized_data[
            "scenes"
        ] = normalized

        normalized_data[
            "narration_enabled"
        ] = brief.narration_enabled

        normalized_data[
            "music_enabled"
        ] = brief.music_enabled

        storyboard = Storyboard.from_dict(
            normalized_data,
            source_prompt=source_prompt,
        )

        if len(
            storyboard.scenes
        ) != expected_count:

            raise PlanningError(
                "Internal storyboard normalization failed: "
                f"got {len(storyboard.scenes)} scenes, "
                f"expected {expected_count}."
            )

        if not brief.narration_enabled:

            for scene in storyboard.scenes:
                scene.narration = ""

        storyboard.narration_enabled = (
            brief.narration_enabled
        )

        # ---------------------------------------------------------
        # Enforce exact durations, maximum 60 seconds.
        # ---------------------------------------------------------

        if explicit_durations:

            for scene, duration in zip(
                storyboard.scenes,
                explicit_durations,
            ):

                scene.duration_seconds = min(
                    float(duration),
                    60.0,
                )

        else:

            duration = min(
                float(
                    brief.scene_duration_seconds
                ),
                60.0,
            )

            for scene in storyboard.scenes:
                scene.duration_seconds = duration

        storyboard.music_enabled = (
            brief.music_enabled
        )

        if not brief.music_enabled:

            for scene in storyboard.scenes:
                scene.music_suggestion = ""

        log.info(
            "Storyboard created successfully: %s scenes.",
            len(storyboard.scenes),
        )

        return storyboard