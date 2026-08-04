"""
Entry point. Run with:  python app.py

Keep this file tiny - it should only ever start the app, never
contain real logic (that belongs in agent/, tools/, services/, ui/).
"""

import socket

from config.settings import settings, validate_settings
from ui.gradio_app import demo
from utils.logger import get_logger

log = get_logger(__name__)


def _resolve_launch_port(preferred_port: int) -> int:
    """Return the requested port when it is free, otherwise pick a free one."""
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
        for p in problems:
            log.warning(" - %s", p)
        log.warning("The app will run but the agent will fail until .env is filled in.")

    launch_port = _resolve_launch_port(settings.gradio_server_port)
    if launch_port != settings.gradio_server_port:
        log.info("Port %s is busy; using %s instead.", settings.gradio_server_port, launch_port)

    demo.launch(
        server_name=settings.gradio_server_name,
        server_port=launch_port,
    )
