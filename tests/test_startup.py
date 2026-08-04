import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ui.gradio_app as gradio_app


def test_chat_fn_returns_friendly_error_when_agent_init_fails():
    gradio_app._agent = None

    with patch.object(gradio_app, "validate_settings", return_value=[]), patch.object(
        gradio_app, "build_agent", side_effect=RuntimeError("boom")
    ):
        result = gradio_app.chat_fn("hello", [])

    assert "failed to initialize" in result.lower() or "something went wrong" in result.lower()
