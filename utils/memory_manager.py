import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class MemoryManager:
    """Tracks global entity state across scenes to maintain visual consistency."""

    def __init__(self):
        self.state: Dict[str, Any] = {
            "characters": {},
            "environment": {},
            "style_palette": ""
        }

    def register_character(self, name: str, visual_traits: str):
        """Registers a character with specific invariant visual traits."""
        self.state["characters"][name.lower()] = visual_traits

    def set_environment(self, lighting: str, weather: str, palette: str):
        """Sets constant environmental parameters."""
        self.state["environment"] = {
            "lighting": lighting,
            "weather": weather
        }
        self.state["style_palette"] = palette

    def enrich_prompt(self, base_prompt: str) -> str:
        """Injects preserved state into scene prompts to maintain continuity."""
        enrichments = []
        
        # Inject style/environment
        if self.state["style_palette"]:
            enrichments.append(f"color palette: {self.state['style_palette']}")
        if self.state["environment"].get("lighting"):
            enrichments.append(f"lighting: {self.state['environment']['lighting']}")

        # Inject character descriptors if mentioned in prompt
        for char_name, traits in self.state["characters"].items():
            if char_name in base_prompt.lower():
                enrichments.append(f"{char_name} ({traits})")

        if enrichments:
            return f"{base_prompt}, maintaining consistency with {', '.join(enrichments)}"
        return base_prompt