"""A tiny example tool: lets the agent know the current date/time."""

from datetime import datetime

from smolagents import tool


@tool
def get_current_time() -> str:
    """
    Returns the current date and time.

    Use this whenever the user's request depends on "today", "now",
    or needs a timestamp (for example, naming a file).
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
