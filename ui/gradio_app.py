"""
Gradio chat UI.

On purpose this file contains ONLY interface code - it builds the
agent once, then just forwards user messages to it. All the "real"
logic lives in agent/ , tools/ and services/.

NOTE on memory: this demo uses ONE shared agent for every visitor,
which is fine for a solo portfolio demo but mixes up memory if two
people use it at the same time. See README "Level it up" section for
how to give each visitor their own agent using gr.State.
"""

import gradio as gr

from agent.agent import build_agent
from config.settings import validate_settings
from utils.logger import get_logger

log = get_logger(__name__)

# Build the agent once when the app starts (not on every message).
_agent = build_agent()


def chat_fn(message: str, history):
    """
    Called by Gradio each time the user sends a message.
    `history` is the chat history Gradio itself keeps. When it's
    empty, we're at the start of a fresh conversation, so we reset
    the agent's own internal memory too. Otherwise we keep it
    (reset=False) so the agent remembers earlier turns.
    """
    problems = validate_settings()
    if problems:
        return "Configuration problem(s):\n- " + "\n- ".join(problems)

    is_new_conversation = len(history) == 0
    try:
        result = _agent.run(message, reset=is_new_conversation)
        return str(result)
    except Exception as exc:  # last-resort safety net for the UI layer
        log.exception("Unhandled error while running the agent")
        return f"Something went wrong: {exc}"


demo = gr.ChatInterface(
    fn=chat_fn,
    title="Agentic Video Assistant",
    description=(
        "Describe a video you want (e.g. 'Make a short video about the "
        "Eiffel Tower's history'). The agent will research facts, write "
        "a detailed prompt, and generate the video."
    ),
    examples=[
        "Make a short video introducing the Colosseum in Rome.",
        "Create a video about the history of coffee.",
    ],
)
