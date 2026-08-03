"""
Web search tool.

This is what turns the project from "one tool call" into real
multi-tool orchestration: the agent can look up facts about a topic
BEFORE writing the video prompt, instead of guessing.

Uses duckduckgo-search, which needs no API key - good for a student
project where you don't want to manage yet another secret.
"""

try:
    from ddgs import DDGS  # newer package name
except ImportError:
    from duckduckgo_search import DDGS  # older package name (still works)

from smolagents import tool
from utils.logger import get_logger

log = get_logger(__name__)


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """
    Searches the web and returns short text snippets about the query.

    Use this to gather real facts about a topic (a place, an event, a
    person...) before writing a video generation prompt, so the video
    is based on accurate information instead of a guess.

    Args:
        query: What to search for, e.g. "Eiffel Tower history facts".
        max_results: How many search results to return (default 5).
    """
    log.info("Searching web for: %r", query)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:  # search provider hiccups shouldn't crash the agent
        log.warning("Search failed: %s", exc)
        return f"Search failed ({exc}). Continue using your own knowledge instead."

    if not results:
        return "No search results found."

    formatted = "\n\n".join(
        f"- {r.get('title', '')}: {r.get('body', '')}" for r in results
    )
    return formatted
