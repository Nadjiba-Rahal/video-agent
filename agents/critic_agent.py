import logging
from typing import List
from models.storyboard import Storyboard
from models.scene import Scene

logger = logging.getLogger(__name__)

class CriticAgent:
    """Inspects and optimizes storyboards for visual continuity and narrative flow."""

    def __init__(self, model_client: Optional[Any] = None):
        self.model = model_client

    def Review_storyboard(self, storyboard: Storyboard) -> Storyboard:
        """Reviews storyboard scenes, fixes scene continuity errors, and optimizes prompts."""
        logger.info(f"Critic Agent reviewing {len(storyboard.scenes)} scenes...")
        
        seen_prompts = set()
        for idx, scene in enumerate(storyboard.scenes):
            # Check prompt duplication
            if scene.agnes_video_prompt in seen_prompts:
                logger.warning(f"Duplicate prompt detected in scene {scene.scene_id}. Enhancing description...")
                scene.agnes_video_prompt += f", angle variation {idx + 1}"
            seen_prompts.add(scene.agnes_video_prompt)

            # Enforce minimum scene duration sanity
            if scene.duration < 2.0:
                scene.duration = 3.0
            elif scene.duration > 10.0:
                scene.duration = 8.0

            # Ensure camera motion continuity
            if not scene.camera_motion or scene.camera_motion.strip() == "":
                scene.camera_motion = "Slow forward dolly shot"

        return storyboard