"""
Simple unit test for the time tool.

Run all tests with:  python -m pytest tests/
"""

import re
import sys
from pathlib import Path

# Allow running "python -m pytest tests/" from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.time_tool import get_current_time


def test_get_current_time_format():
    result = get_current_time()
    # Expected format: "2026-08-03 21:35:01"
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", result)
