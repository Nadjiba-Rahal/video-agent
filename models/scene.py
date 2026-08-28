"""
Scene model.

A Scene is the atomic unit produced by the Storyboard Agent and consumed
by the video pipeline. Keeping it as a plain dataclass (mirroring the
style already used in config/settings.py) means it has zero framework
dependencies: it doesn't know about smolagents, litellm, or Agnes.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Scene:
    """One shot/beat of the final video."""

    scene_id: int
    title: str
    video_prompt: str
    duration_seconds: float

    camera_shot: str = ""
    camera_motion: str = ""

    narration: str = ""
    music_suggestion: str = ""
    sound_effects: list[str] = field(default_factory=list)

    transition: str = "cut"
    mood: str = ""
    visual_style: str = ""
    color_palette: str = ""

    negative_prompt: str | None = None

    # Filled in later by the video pipeline once the clip is rendered.
    clip_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scene":
        """Builds a Scene from a (possibly messy) LLM-generated dict.

        Only keeps known fields and applies sane fallbacks, so a slightly
        malformed JSON response from the Storyboard Agent doesn't crash
        the whole pipeline.
        """
        known_fields = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in data.items() if k in known_fields}

        clean.setdefault("scene_id", 0)
        clean.setdefault("title", "Untitled scene")
        clean.setdefault("video_prompt", "")
        clean.setdefault("duration_seconds", 5.0)

        sfx = clean.get("sound_effects", [])
        if isinstance(sfx, str):
            sfx = [s.strip() for s in sfx.split(",") if s.strip()]
        clean["sound_effects"] = sfx or []

        try:
            clean["duration_seconds"] = float(clean["duration_seconds"])
        except (TypeError, ValueError):
            clean["duration_seconds"] = 5.0

        try:
            clean["scene_id"] = int(clean["scene_id"])
        except (TypeError, ValueError):
            clean["scene_id"] = 0

        return cls(**clean)

    def to_markdown(self) -> str:
        """Renders this scene as a section of the human-readable script."""
        lines = [
            f"## Scene {self.scene_id}: {self.title}",
            "",
            f"**Duration:** {self.duration_seconds:.1f}s  ",
            f"**Mood:** {self.mood or '-'}  ",
            f"**Visual style:** {self.visual_style or '-'}  ",
            f"**Color palette:** {self.color_palette or '-'}  ",
            f"**Camera:** {self.camera_shot or '-'} / {self.camera_motion or '-'}  ",
            f"**Transition out:** {self.transition or '-'}",
            "",
            "**Video prompt**",
            f"> {self.video_prompt}",
            "",
        ]
        if self.negative_prompt:
            lines += ["**Negative prompt**", f"> {self.negative_prompt}", ""]

        lines += ["**Narration**"]
        lines += [self.narration if self.narration else "_(no narration)_", ""]

        lines += ["**Music**", self.music_suggestion or "_(none suggested)_", ""]

        lines += ["**SFX**"]
        lines += [", ".join(self.sound_effects) if self.sound_effects else "_(none)_", ""]

        return "\n".join(lines)
