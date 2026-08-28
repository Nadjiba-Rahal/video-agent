import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class ProductionBrief(BaseModel):
    genre: str = Field(default="Cinematic", description="Movie genre (e.g. Sci-Fi, Drama, Documentary)")
    tone: str = Field(default="Dramatic", description="Overall atmospheric tone")
    visual_style: str = Field(default="Photorealistic 8K, cinematic lighting", description="Visual style guidelines")
    target_duration: int = Field(default=15, description="Target total duration in seconds")
    pacing: str = Field(default="Moderate", description="Pacing rate (Fast, Moderate, Slow)")
    color_palette: str = Field(default="Teal and Orange", description="Dominant visual color scheme")
    aspect_ratio: str = Field(default="16:9", description="Video orientation: 16:9 or 9:16")
    voice_enabled: bool = Field(default=True, description="Whether narration/dialogue is enabled")
    music_enabled: bool = Field(default=True, description="Whether background music is enabled")
    sfx_enabled: bool = Field(default=True, description="Whether sound effects are enabled")
    negative_constraints: list[str] = Field(default_factory=list, description="Strict exclusion rules")

class ProducerAgent:
    """Producer Agent responsible for high-level creative vision and production parameters."""

    def __init__(self, model_client: Optional[Any] = None):
        self.model = model_client

    def create_brief(self, prompt: str, user_constraints: Optional[Dict[str, Any]] = None) -> ProductionBrief:
        """Parses the user prompt into a structured Production Brief."""
        logger.info(f"Producer Agent generating Production Brief for: {prompt[:60]}...")
        
        brief = ProductionBrief()
        
        # Apply prompt analysis rules & negative constraint checks
        prompt_lower = prompt.lower()
        if "no voice" in prompt_lower or "no narration" in prompt_lower:
            brief.voice_enabled = False
            brief.negative_constraints.append("no narration")
        if "no music" in prompt_lower:
            brief.music_enabled = False
            brief.negative_constraints.append("no background music")
        if "vertical" in prompt_lower or "tiktok" in prompt_lower or "9:16" in prompt_lower:
            brief.aspect_ratio = "9:16"
        if "sci-fi" in prompt_lower or "cyberpunk" in prompt_lower:
            brief.genre = "Sci-Fi"
            brief.color_palette = "Neon Cyberpunk, High Contrast Blue/Purple"

        if user_constraints:
            for key, val in user_constraints.items():
                if hasattr(brief, key) and val is not None:
                    setattr(brief, key, val)

        return brief