"""
Builds the agent: wires together the model, the tools, and the
system prompt. This is the only file that needs to change if you
add or remove a tool.
"""

import importlib.resources

import yaml

try:
    from smolagents import CodeAgent
except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing
    raise RuntimeError(
        "smolagents is not installed. Install the project dependencies with 'pip install -r requirements.txt'."
    ) from exc

from agent.model import get_model
from agent.prompts import CUSTOM_INSTRUCTIONS
from config.settings import settings
from tools.search_tool import search_web
from tools.time_tool import get_current_time
from tools.video_tool import generate_video


def _build_prompt_templates() -> dict:
    """
    Starts from smolagents' own default prompt templates (they contain
    important instructions on HOW to write valid tool-call code) and
    appends our own workflow instructions on top, instead of throwing
    the defaults away.
    """
    templates = yaml.safe_load(
        importlib.resources.files("smolagents.prompts").joinpath("code_agent.yaml").read_text()
    )
    templates["system_prompt"] = templates["system_prompt"] + "\n\n" + CUSTOM_INSTRUCTIONS
    return templates


def build_agent() -> CodeAgent:
    """Creates a ready-to-use agent instance."""
    model = get_model()

    agent = CodeAgent(
        tools=[get_current_time, search_web, generate_video],
        model=model,
        prompt_templates=_build_prompt_templates(),
        planning_interval=None,
        # Default sandbox timeout is 30s - too short for a blocking
        # generate_video() call that polls until the video finishes
        # rendering. Raise it to cover a full render + poll cycle.
        executor_kwargs={"timeout_seconds": settings.poll_timeout_seconds + 30},
    )
    return agent