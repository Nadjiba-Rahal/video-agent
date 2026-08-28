"""
Storyboard model.

Holds the full creative plan for a video: the overall direction plus
the ordered list of Scenes. This is the hand-off object between the
planning side of the pipeline (Director Agent + Storyboard Agent) and
the execution side (video pipeline + composer).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from models.scene import Scene


@dataclass
class Storyboard:
    """A complete, ordered plan for a multi-scene video."""

    title: str
    logline: str
    style: str
    tone: str
    pacing: str
    narration_enabled: bool
    music_enabled: bool
    scenes: list[Scene] = field(default_factory=list)

    # Persistent visual anchors to eliminate AI hallucinations across scenes
    character_anchor: str = ""
    environment_anchor: str = ""

    source_prompt: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def scene_count(self) -> int:
        return len(self.scenes)

    @property
    def total_duration_seconds(self) -> float:
        return sum(scene.duration_seconds for scene in self.scenes)

    def scene_prompts(self) -> list[str]:
        """The list of prompts to send to the video generation service, in order."""
        return [scene.video_prompt for scene in self.scenes]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any], source_prompt: str = "") -> "Storyboard":
        raw_scenes = data.get("scenes", [])
        scenes = [Scene.from_dict(s) for s in raw_scenes if isinstance(s, dict)]
        
        # Re-number scenes sequentially so scene_id is always reliable
        for i, scene in enumerate(scenes, start=1):
            scene.scene_id = i

        return cls(
            title=str(data.get("title") or "Untitled video"),
            logline=str(data.get("logline") or ""),
            style=str(data.get("style") or ""),
            tone=str(data.get("tone") or ""),
            pacing=str(data.get("pacing") or "medium"),
            narration_enabled=bool(data.get("narration_enabled", True)),
            music_enabled=bool(data.get("music_enabled", True)),
            scenes=scenes,
            character_anchor=str(data.get("character_anchor") or ""),
            environment_anchor=str(data.get("environment_anchor") or ""),
            source_prompt=source_prompt,
        )

    def to_markdown(self) -> str:
        """Renders the full human-readable Markdown script for this storyboard."""
        header = [
            f"# {self.title}",
            "",
            f"*{self.logline}*" if self.logline else "",
            "",
            f"**Style:** {self.style or '-'}  ",
            f"**Tone:** {self.tone or '-'}  ",
            f"**Pacing:** {self.pacing or '-'}  ",
            f"**Narration:** {'enabled' if self.narration_enabled else 'disabled'}  ",
            f"**Music:** {'suggested per scene' if self.music_enabled else 'disabled'}  ",
            f"**Character Anchor:** {self.character_anchor or 'None'}  ",
            f"**Environment Anchor:** {self.environment_anchor or 'None'}  ",
            f"**Scenes:** {self.scene_count}  ",
            f"**Total duration:** ~{self.total_duration_seconds:.1f}s  ",
            f"**Generated:** {self.created_at}",
            "",
            "---",
            "",
        ]
        body = [scene.to_markdown() for scene in self.scenes]
        return "\n".join(header) + "\n---\n\n".join(body)