import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from utils.helpers import nearest_valid_frame_count


@pytest.mark.parametrize(
    "duration,expected",
    [
        (3.0, 81),
        (5.0, 121),
        (10.0, 241),
        (20.0, 441),
    ],
)
def test_nearest_valid_frame_count(duration, expected):
    assert nearest_valid_frame_count(duration, frame_rate=24) == expected
