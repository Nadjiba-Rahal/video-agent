"""
Robust parsing of JSON that an LLM claims to have produced.

Even when a prompt says "respond with ONLY a JSON object", real models
still sometimes:
  - wrap the object in ```json ... ``` (or plain ``` ... ```) fences
  - add a sentence of prose before or after the object
  - leave literal newlines inside string values (technically invalid
    JSON, but very common in narration/prompt text)
  - leave a trailing comma before a closing ``}`` or ``]``
  - use smart/curly quotes copy-pasted from elsewhere

`parse_llm_json()` is the single place this project handles all of
that, so the Director and Storyboard agents (and anything else that
asks an LLM for structured output) don't each reinvent - and get
wrong - their own ad-hoc cleanup.
"""

from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")
_SMART_QUOTES = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"})


def _strip_code_fences(text: str) -> str:
    """Removes a leading/trailing ```json ... ``` or ``` ... ``` fence."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = _FENCE_RE.sub("", stripped).strip()
    return stripped


def _extract_outermost_object(text: str) -> str:
    """Returns the outermost ``{...}`` block in `text`, ignoring braces
    that appear inside string literals, via a simple depth counter.

    Raises ValueError if no balanced JSON object can be found.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in model output: {text[:200]!r}")

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise ValueError(f"Unbalanced JSON braces in model output: {text[:200]!r}")


def _escape_bare_newlines_in_strings(text: str) -> str:
    """Turns literal newlines/tabs that appear *inside* JSON string
    values into their escaped ``\\n`` / ``\\t`` form, without touching
    whitespace that separates JSON tokens (outside of strings).

    LLMs frequently emit multi-line narration text as a raw newline
    inside a string, which is invalid per the JSON spec and is the
    single most common cause of Director Agent crashes.
    """
    out: list[str] = []
    in_string = False
    escape_next = False

    for char in text:
        if escape_next:
            out.append(char)
            escape_next = False
            continue
        if char == "\\":
            out.append(char)
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            out.append(char)
            continue
        if in_string and char == "\n":
            out.append("\\n")
            continue
        if in_string and char == "\t":
            out.append("\\t")
            continue
        out.append(char)

    return "".join(out)


def parse_llm_json(text: str) -> dict:
    """Best-effort extraction + parsing of a JSON object from raw LLM text.

    Tries progressively more forgiving strategies and returns the first
    one that parses cleanly:
      1. The whole (fence-stripped) response, as-is.
      2. The same text with bare newlines/tabs inside strings escaped.
      3. Just the outermost ``{...}`` block (in case of leading/trailing
         prose), with the same newline-escaping applied.
      4. Any of the above with trailing commas before ``}``/``]`` removed
         and smart quotes normalized to straight quotes.

    Raises:
        ValueError: if no strategy produces valid JSON. The message
            includes a preview of the original text to aid debugging.
    """
    if not text or not text.strip():
        raise ValueError("Empty response from model - nothing to parse as JSON.")

    cleaned = _strip_code_fences(text)

    candidates = [cleaned]

    escaped = _escape_bare_newlines_in_strings(cleaned)
    if escaped != cleaned:
        candidates.append(escaped)

    try:
        object_block = _extract_outermost_object(escaped)
        candidates.append(object_block)
    except ValueError:
        object_block = None

    # Also try a maximally-sanitized version of whichever candidate is
    # most likely to be the real payload (trailing commas + smart quotes).
    base_for_sanitizing = object_block if object_block is not None else escaped
    sanitized = _TRAILING_COMMA_RE.sub(r"\1", base_for_sanitizing).translate(_SMART_QUOTES)
    candidates.append(sanitized)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue

    raise ValueError(
        f"Could not parse JSON from model output after all fallback strategies "
        f"({last_error}). Raw output preview: {text[:300]!r}"
    )
