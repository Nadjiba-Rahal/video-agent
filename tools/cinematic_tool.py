"""
Cinematic video generation tool.

Same philosophy as tools/video_tool.py: thin glue with almost no logic
of its own. The real orchestration lives in pipeline/cinematic_pipeline.py
(Agent -> Tool -> Pipeline -> Agents/Services -> Agnes/ffmpeg), so it can
be tested and reused without smolagents.

Use this instead of generate_video when the user describes a story,
short film, or anything implying multiple scenes/shots - generate_video
stays the right choice for a single quick clip.
"""

from smolagents import tool

from pipeline.cinematic_pipeline import run_cinematic_pipeline
from services.exceptions import AgnesError, FFmpegError, PlanningError
from utils.logger import get_logger

log = get_logger(__name__)

@tool
def generate_cinematic_video(user_idea: str) -> str:
    """
    Generate a multi-scene cinematic video from a user's idea.

    Args:
        user_idea: The user's complete video idea and requirements.

    Returns:
        A summary containing the generated video paths and script path.
    """
    try:
        result = run_cinematic_pipeline(user_idea)

    except PlanningError as exc:
        log.error(
            "Cinematic pipeline failed during planning: %s",
            exc,
        )
        return f"Cinematic video planning failed: {exc}"

    except AgnesError as exc:
        log.error(
            "Cinematic pipeline failed during rendering: %s",
            exc,
        )
        return f"Cinematic video rendering failed: {exc}"

    except FFmpegError as exc:
        log.error(
            "Cinematic pipeline failed during composition: %s",
            exc,
        )
        return f"Cinematic video composition failed: {exc}"

    storyboard = result.storyboard

    clip_list = "\n".join(
        f"  - {p}"
        for p in result.clip_paths
    )

    return (
        f"Cinematic video ready: {result.final_video_path}\n"
        f"Title: {storyboard.title}\n"
        f"Scenes: {storyboard.scene_count} "
        f"(~{storyboard.total_duration_seconds:.1f}s total)\n"
        f"Script: {result.script_path}\n"
        f"Clips:\n{clip_list}"
    )