"""
Custom exceptions.

Instead of catching everything with a bare `except:`, the rest of the
code catches these specific, meaningful errors.
"""


class AgnesError(Exception):
    """Base class for anything that goes wrong talking to the video API."""


class AgnesAuthError(AgnesError):
    """The API key was rejected (HTTP 401 / 403)."""


class AgnesRateLimitError(AgnesError):
    """We are calling the API too fast (HTTP 429)."""


class AgnesTimeoutError(AgnesError):
    """The request took too long, or the video never finished rendering in time."""


class AgnesJobFailedError(AgnesError):
    """The video provider accepted the job but it failed while rendering."""


class FFmpegError(Exception):
    """Something went wrong invoking ffmpeg (missing binary, bad input, non-zero exit)."""


class PlanningError(Exception):
    """The Director or Storyboard agent could not produce a usable plan
    (LLM call failed, or returned JSON that couldn't be parsed/validated
    even after fallback attempts)."""
