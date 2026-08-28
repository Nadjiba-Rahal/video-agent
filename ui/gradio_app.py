"""
Gradio chat UI.

Cinematic requests are dispatched directly to the cinematic pipeline
instead of asking the chat LLM to reproduce a potentially huge prompt
inside a JSON tool-call argument.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import gradio as gr

from agent.agent import build_agent
from config.settings import validate_settings
from pipeline.cinematic_pipeline import run_cinematic_pipeline
from utils.logger import get_logger

log = get_logger(__name__)

_VIDEO_PATH_RE = re.compile(
    r"([\w./\\-]+\.mp4)"
)

_agent: Optional[Any] = None


def _get_agent() -> Any:
    """Return the shared general-purpose chat agent."""
    global _agent

    if _agent is None:
        _agent = build_agent()

    return _agent


def _looks_like_cinematic_request(
    message: str,
) -> bool:
    """
    Detect requests that clearly ask for a multi-scene cinematic video.

    This prevents a huge user prompt from being copied into a tool-call
    JSON argument by the chat model.
    """

    text = message.lower()

    cinematic_markers = (
        "scene 1",
        "scene 2",
        "scene 3",
        "scene 4",
        "scene 5",
        "scene 6",
        "multi-scene",
        "multiple scenes",
        "short film",
        "cinematic video",
        "cinematic film",
        "storyboard",
        "scene-by-scene",
        "liminal-space",
        "weirdcore",
        "analog horror",
    )

    explicit_video_words = (
        "create a video",
        "make a video",
        "generate a video",
        "create a cinematic",
        "make a cinematic",
        "generate a cinematic",
    )

    has_cinematic_marker = any(
        marker in text
        for marker in cinematic_markers
    )

    has_video_request = any(
        marker in text
        for marker in explicit_video_words
    )

    return (
        has_cinematic_marker
        or has_video_request
    )


def _run_cinematic_directly(
    message: str,
) -> Any:
    """
    Send the user's original prompt directly into the cinematic pipeline.

    The LLM does not have to reproduce the prompt as a tool-call argument.
    """

    log.info(
        "Direct cinematic dispatch. Prompt length=%s characters.",
        len(message),
    )

    result = run_cinematic_pipeline(
        message
    )

    return gr.Video(
        value=str(
            result.final_video_path
        )
    )


def chat_fn(
    message: str,
    history: list,
) -> Any:

    problems = validate_settings()

    if problems:
        return (
            "Configuration problem(s):\n- "
            + "\n- ".join(problems)
        )

    try:

        # -----------------------------------------------------
        # IMPORTANT:
        # Large cinematic prompts bypass the LLM tool-call layer.
        # -----------------------------------------------------

        if _looks_like_cinematic_request(
            message
        ):

            return _run_cinematic_directly(
                message
            )

        # -----------------------------------------------------
        # Normal requests still use the chat agent.
        # -----------------------------------------------------

        agent = _get_agent()

        is_new_conversation = (
            len(history) == 0
        )

        agent_output = agent.run(
            message,
            reset=is_new_conversation,
            max_steps=6,
        )

        result = str(
            agent_output
        )

        match = _VIDEO_PATH_RE.search(
            result
        )

        if match:
            return gr.Video(
                value=match.group(1),
                height=360,
                width=640,
                show_label=False,
            )

        return result

    except Exception as exc:

        log.exception(
            "Unhandled error while processing request"
        )

        return (
            "Something went wrong: "
            f"{type(exc).__name__}: {exc}"
        )


chatbot = gr.Chatbot(
    height=560,
    render_markdown=True,
    show_label=False,
)


demo = gr.ChatInterface(
    fn=chat_fn,
    title="Agentic Video Assistant",
    description=(
        "Describe a video you want. "
        "For detailed multi-scene cinematic prompts, "
        "the prompt is passed directly to the cinematic pipeline."
    ),
    chatbot=chatbot,
    examples=[
        "Create a 3-scene cinematic video about a night train arriving at a quiet coastal town, with a mysterious but hopeful tone.",
    ],
)
