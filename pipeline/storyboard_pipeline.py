"""
Storyboard pipeline: the "planning" half of the cinematic pipeline.

    user_prompt -> DirectorAgent -> DirectorBrief
                -> StoryboardAgent -> Storyboard
                -> Markdown script saved to outputs/scripts/

This is deliberately just orchestration - all the actual thinking
happens inside agents/, all the actual I/O happens inside services/.
"""

from __future__ import annotations

from pathlib import Path

from agents.director_agent import DirectorAgent
from agents.storyboard_agent import StoryboardAgent
from config.settings import settings
from models.storyboard import Storyboard
from utils.logger import get_logger

log = get_logger(__name__)


def build_storyboard(user_prompt: str) -> Storyboard:
    """Runs Director -> Storyboard and returns the finished plan."""
    director = DirectorAgent()
    brief = director.plan(user_prompt)
    log.info(
        "Director brief: style=%r pacing=%r scenes=%s narration=%s music=%s",
        brief.style,
        brief.pacing,
        brief.scene_count,
        brief.narration_enabled,
        brief.music_enabled,
    )

    storyboard_agent = StoryboardAgent()
    storyboard = storyboard_agent.generate(user_prompt, brief)
    log.info(
        "Storyboard ready: %r with %s scene(s), ~%.1fs total",
        storyboard.title,
        storyboard.scene_count,
        storyboard.total_duration_seconds,
    )
    return storyboard


def save_script(storyboard: Storyboard, run_id: str) -> Path:
    """Writes the storyboard's Markdown script to outputs/scripts/{run_id}.md."""
    settings.scripts_dir.mkdir(parents=True, exist_ok=True)
    script_path = settings.scripts_dir / f"{run_id}.md"
    script_path.write_text(storyboard.to_markdown(), encoding="utf-8")
    log.info("Saved script to %s", script_path)
    return script_path
