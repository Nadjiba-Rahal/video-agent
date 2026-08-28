import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from utils.json_utils import parse_llm_json


def test_parses_plain_json():
    assert parse_llm_json('{"a": 1}') == {"a": 1}


def test_strips_markdown_json_fence():
    text = '```json\n{"a": 1, "b": [1, 2]}\n```'
    assert parse_llm_json(text) == {"a": 1, "b": [1, 2]}


def test_strips_plain_markdown_fence():
    text = '```\n{"a": 1}\n```'
    assert parse_llm_json(text) == {"a": 1}


def test_finds_object_amid_leading_and_trailing_prose():
    text = 'Sure, here is the plan:\n{"a": 1}\nLet me know if that works!'
    assert parse_llm_json(text) == {"a": 1}


def test_handles_unescaped_newlines_inside_string_values():
    """This is the exact failure mode that used to crash the Director
    Agent: multi-line narration/notes text with a literal newline
    inside a JSON string value, which is invalid per the JSON spec."""
    raw = '{\n  "notes": "line one\nline two",\n  "scene_count": 3\n}'
    result = parse_llm_json(raw)
    assert result["scene_count"] == 3
    assert result["notes"] == "line one\nline two"


def test_handles_trailing_commas():
    text = '{"style": "cinematic", "tone": "dark",}'
    assert parse_llm_json(text) == {"style": "cinematic", "tone": "dark"}


def test_handles_smart_quotes():
    text = "{\u201cstyle\u201d: \u201ccinematic\u201d}"
    assert parse_llm_json(text) == {"style": "cinematic"}


def test_handles_nested_objects_and_arrays():
    text = '{"scenes": [{"id": 1, "notes": "a, b, c"}, {"id": 2}]}'
    result = parse_llm_json(text)
    assert result["scenes"][0]["id"] == 1
    assert result["scenes"][1]["id"] == 2


def test_raises_value_error_on_empty_response():
    with pytest.raises(ValueError):
        parse_llm_json("")


def test_raises_value_error_when_no_json_present():
    with pytest.raises(ValueError):
        parse_llm_json("no json here at all")


def test_raises_value_error_on_unbalanced_braces():
    with pytest.raises(ValueError):
        parse_llm_json('{"a": 1')
