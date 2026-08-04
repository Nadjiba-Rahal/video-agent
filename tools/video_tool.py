"""
Video generation tool.

This is the thin "glue" layer between the agent and the services/
folder. It has almost no logic of its own on purpose: submitting the
job, polling, and downloading all live in services/, so they can be
tested and reused without needing smolagents at all.
"""

from smolagents import tool

from services import agnes
from services.exceptions import AgnesError
from services.polling import poll_until_finished
from utils.logger import get_logger

log = get_logger(__name__)


@tool
def generate_video(
    prompt: str,
    num_frames: int = 121,
    frame_rate: int = 24,
    num_inference_steps: int = 40,
    seed: int = -1,
) -> str:
    """
    Generates a video from a text prompt and saves it locally.

    Use this only once you already have a clear, detailed prompt
    (ideally improved using facts from search_web). Submitting a job
    takes time to render, so only call this once per user request.

    Args:
        prompt: A detailed description of the video. For best
            quality, describe subject + ONE simple action + scene +
            camera movement + lighting + style, and avoid multi-step
            choreography (it causes glitchy morphing). E.g. "..., slow
            cinematic dolly zoom, moody low-key lighting,
            photorealistic film style".
        num_frames: Total frames. Must follow the 8n+1 rule (81, 121,
            241, 441). Higher = longer video (max ~18s at 441/24).
        frame_rate: Frames per second (1-60). Duration = num_frames / frame_rate.
        num_inference_steps: Higher = better quality but slower to render.
        seed: Set a fixed positive number to reproduce the same result
            when testing prompt changes. Leave at -1 for a random seed.

    Returns:
        The local file path of the downloaded video, or an error
        message explaining what went wrong.
    """
    try:
        video_id = agnes.submit_video(
            prompt,
            num_frames=num_frames,
            frame_rate=frame_rate,
            num_inference_steps=num_inference_steps,
            seed=seed if seed >= 0 else None,
        )
        local_path = poll_until_finished(video_id)
        return f"Video ready: {local_path}"
    except AgnesError as exc:
        log.error("Video generation failed: %s", exc)
        return f"Video generation failed: {exc}"