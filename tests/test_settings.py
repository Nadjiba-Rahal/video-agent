import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import Settings


def test_director_and_storyboard_model_default_to_model_id(monkeypatch):
    monkeypatch.delenv("DIRECTOR_MODEL_ID", raising=False)
    monkeypatch.delenv("STORYBOARD_MODEL_ID", raising=False)
    monkeypatch.setenv("MODEL_ID", "groq/some-model")

    s = Settings(_env_file=None)
    assert s.director_model_id == "groq/some-model"
    assert s.storyboard_model_id == "groq/some-model"


def test_explicit_director_model_id_overrides_default(monkeypatch):
    monkeypatch.setenv("MODEL_ID", "groq/some-model")
    monkeypatch.setenv("DIRECTOR_MODEL_ID", "groq/cheaper-model")

    s = Settings(_env_file=None)
    assert s.director_model_id == "groq/cheaper-model"
    assert s.storyboard_model_id == "groq/some-model"


def test_groq_api_key_bridges_to_model_api_key(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key-123")

    s = Settings(_env_file=None)
    assert s.model_api_key == "test-key-123"


def test_resolution_for_aspect_ratio():
    s = Settings(_env_file=None)
    assert s.resolution_for("9:16") == (s.agnes_portrait_width, s.agnes_portrait_height)
    assert s.resolution_for("16:9") == (s.agnes_landscape_width, s.agnes_landscape_height)
