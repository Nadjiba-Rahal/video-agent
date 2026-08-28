"""
Shared helper for LLM calls that must return JSON.

The planning agents use this helper. It requests JSON directly from
providers that support it and gives the model enough output budget for
multi-scene storyboards.
"""

from __future__ import annotations

import litellm

from config.settings import settings
from services.exceptions import PlanningError
from utils.json_utils import parse_llm_json
from utils.logger import get_logger

log = get_logger(__name__)


def complete_json(
    *,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.5,
    agent_name: str = "Agent",
    max_tokens: int = 1500,
) -> dict:
    """
    Call an LLM and return one JSON object.

    max_tokens is deliberately generous because Storyboard Agent responses
    can contain several detailed scene prompts.
    """

    try:
        kwargs = dict(
            model=model_id,
            api_key=settings.model_api_key,
            timeout=settings.llm_request_timeout_seconds,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Ask providers that support it to constrain the response to JSON.
        # If a provider rejects this option, retry once without it.
        try:
            response = litellm.completion(
                **kwargs,
                response_format={
                    "type": "json_object"
                },
            )

        except Exception as json_mode_error:

            log.warning(
                "%s JSON response_format was rejected; "
                "retrying without response_format: %s",
                agent_name,
                json_mode_error,
            )

            response = litellm.completion(
                **kwargs
            )

        raw_text = (
            response["choices"][0]["message"]["content"]
        )

        if not raw_text:
            raise PlanningError(
                f"{agent_name} returned an empty response."
            )

        log.info(
            "%s returned %s characters.",
            agent_name,
            len(raw_text),
        )

    except PlanningError:
        raise

    except Exception as exc:
        raise PlanningError(
            f"{agent_name} LLM call failed: {exc}"
        ) from exc

    try:
        return parse_llm_json(
            raw_text
        )

    except ValueError as exc:

        log.error(
            "%s returned unparseable JSON: %s",
            agent_name,
            exc,
        )

        # This is especially useful when the provider stops at its output
        # limit. The log tells us whether the response was suspiciously long.
        log.error(
            "%s raw response length=%s",
            agent_name,
            len(raw_text),
        )

        raise PlanningError(
            f"{agent_name} returned invalid JSON: {exc}"
        ) from exc