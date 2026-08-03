"""
Entry point. Run with:  python app.py

Keep this file tiny - it should only ever start the app, never
contain real logic (that belongs in agent/, tools/, services/, ui/).
"""

from config.settings import settings, validate_settings
from ui.gradio_app import demo
from utils.logger import get_logger

log = get_logger(__name__)

if __name__ == "__main__":
    problems = validate_settings()
    if problems:
        log.warning("Starting with missing configuration:")
        for p in problems:
            log.warning(" - %s", p)
        log.warning("The app will run but the agent will fail until .env is filled in.")

    demo.launch(
        server_name=settings.gradio_server_name,
        server_port=settings.gradio_server_port,
    )
