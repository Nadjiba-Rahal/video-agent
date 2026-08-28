import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.scene import Scene
from models.storyboard import Storyboard


def test_scene_from_dict_fills_defaults_and_normalizes_sfx():
    scene = Scene.from_dict(
        {
            "scene_id": "2",
            "title": "Arrival",
            "video_prompt": "an astronaut lands on an empty street",
            "duration_seconds": "6.5",
            "sound_effects": "wind, distant hum",
        }
    )
    assert scene.scene_id == 2
    assert scene.duration_seconds == 6.5
    assert scene.sound_effects == ["wind", "distant hum"]


def test_storyboard_from_dict_renumbers_scenes_and_computes_duration():
    data = {
        "title": "Lonely City",
        "logline": "An astronaut explores an abandoned city.",
        "style": "cinematic",
        "tone": "melancholic",
        "pacing": "slow",
        "narration_enabled": True,
        "music_enabled": True,
        "scenes": [
            {"scene_id": 5, "title": "A", "video_prompt": "p1", "duration_seconds": 4},
            {"scene_id": 9, "title": "B", "video_prompt": "p2", "duration_seconds": 6},
        ],
    }
    storyboard = Storyboard.from_dict(data, source_prompt="a lonely astronaut")

    assert [s.scene_id for s in storyboard.scenes] == [1, 2]
    assert storyboard.scene_count == 2
    assert storyboard.total_duration_seconds == 10
    assert storyboard.scene_prompts() == ["p1", "p2"]


def test_storyboard_to_markdown_contains_each_scene_title():
    data = {
        "title": "Lonely City",
        "scenes": [
            {"scene_id": 1, "title": "Landing", "video_prompt": "p1", "duration_seconds": 4},
        ],
    }
    storyboard = Storyboard.from_dict(data)
    markdown = storyboard.to_markdown()
    assert "Lonely City" in markdown
    assert "Landing" in markdown
