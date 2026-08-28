"""
Entry point. Run with: python app.py
"""

import os
import socket

from dotenv import load_dotenv

# Load .env before importing settings or modules that depend on it.
load_dotenv()

from config.settings import settings, validate_settings
from ui.gradio_app import demo
from utils.logger import get_logger

log = get_logger(__name__)


def _resolve_launch_port(preferred_port: int) -> int:
    """Return the requested port when it is free, otherwise choose a free one."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("0.0.0.0", preferred_port))
            sock.listen(1)
            return preferred_port
    except OSError:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("0.0.0.0", 0))
            sock.listen(1)
            return sock.getsockname()[1]


if __name__ == "__main__":
    problems = validate_settings()

    if problems:
        log.warning("Starting with missing configuration:")
        for problem in problems:
            log.warning(" - %s", problem)

    target_port = int(
        os.environ.get(
            "PORT",
            settings.gradio_server_port,
        )
    )

    launch_port = _resolve_launch_port(target_port)

    if launch_port != target_port:
        log.info(
            "Port %s is busy; using %s instead.",
            target_port,
            launch_port,
        )

    server_name = os.environ.get(
        "GRADIO_SERVER_NAME",
        settings.gradio_server_name,
    )

    demo.launch(
        server_name=server_name,
        server_port=launch_port,
    )