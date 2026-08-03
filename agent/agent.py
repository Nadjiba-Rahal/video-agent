"""
Builds the agent: wires together the model, the tools, and the
system prompt. This is the only file that needs to change if you
add or remove a tool.
"""

import importlib.resources

import yaml
from smolagents import CodeAgent

from agent.model import get_model
from agent.prompts import CUSTOM_INSTRUCTIONS
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
        # planning_interval=1 forces the agent to write an explicit plan
        # BEFORE its first action, every run. With a higher interval the
        # planning step never fired on short video tasks (they finish in
        # under 3 steps), so the "planner" was invisible in practice.
        planning_interval=1,
    )
    return agent
