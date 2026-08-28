from typing import Dict, Any
from models.storyboard import Storyboard

class ProductionEstimator:
    """Estimates render time, API calls, and resource consumption."""

    @staticmethod
    def estimate_storyboard(storyboard: Storyboard) -> Dict[str, Any]:
        num_scenes = len(storyboard.scenes)
        total_duration = sum(s.duration for s in storyboard.scenes)
        
        # Parallel estimation factors
        estimated_video_gen_time = num_scenes * 12.0  # Approx seconds per Agnes video call in parallel
        estimated_audio_gen_time = num_scenes * 2.0
        estimated_total_seconds = estimated_video_gen_time + estimated_audio_gen_time + 5.0

        return {
            "total_scenes": num_scenes,
            "total_video_duration_sec": total_duration,
            "agnes_api_calls": num_scenes,
            "estimated_wait_time_sec": round(estimated_total_seconds, 1)
        }