"""
Builds the general-purpose chat agent.

ToolCallingAgent is used instead of CodeAgent because this application
primarily dispatches tools and should not require the LLM to generate
arbitrary Python code.
"""

from __future__ import annotations

from smolagents import ToolCallingAgent

from agent.model import get_model
from agent.prompts import CUSTOM_INSTRUCTIONS
from tools.cinematic_tool import generate_cinematic_video
from tools.search_tool import search_web
from tools.video_tool import generate_video


def build_agent() -> ToolCallingAgent:
    """Create the general-purpose tool-calling assistant."""

    return ToolCallingAgent(
        tools=[
            search_web,
            generate_video,
            generate_cinematic_video,
        ],
        model=get_model(),
        instructions=CUSTOM_INSTRUCTIONS,
        max_steps=6,
        planning_interval=None,
    )

