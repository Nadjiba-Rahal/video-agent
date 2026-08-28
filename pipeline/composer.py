import os
import asyncio
import logging
from typing import List, Optional
from models.storyboard import Storyboard
from services.ffmpeg_service import FFmpegService
from services.voice_service import BaseVoiceProvider, EdgeTTSVoiceProvider
from services.music_service import BaseMusicProvider

logger = logging.getLogger(__name__)


class MasterComposerPipeline:
    """Orchestrates Video, Voiceover, and Music mixing into a final Master Video."""

    def __init__(
        self, 
        ffmpeg_service: FFmpegService,
        voice_provider: Optional[BaseVoiceProvider] = None,
        music_provider: Optional[BaseMusicProvider] = None
    ):
        self.ffmpeg = ffmpeg_service
        self.voice_provider = voice_provider or EdgeTTSVoiceProvider()
        self.music_provider = music_provider 

    async def prepare_voiceovers_and_sync_durations(
        self, 
        storyboard: Storyboard, 
        audio_dir: str
    ) -> List[str]:
        """
        PRE-PASS STEP: Generates TTS voiceover files FIRST, measures exact speech lengths,
        and automatically updates each scene.duration_seconds in the storyboard.
        
        Call this BEFORE sending the storyboard to the video generation pipeline!
        """
        logger.info("Pre-generating voiceovers to lock scene durations for exact audio-visual sync...")
        os.makedirs(audio_dir, exist_ok=True)
        voice_paths = []

        for scene in storyboard.scenes:
            if scene.narration and scene.narration.strip():
                voice_file = os.path.join(audio_dir, f"voice_scene_{scene.scene_id}.mp3")
                _, duration = await self.voice_provider.generate_speech_async(
                    scene.narration, 
                    voice_file
                )
                
                # Add 0.5s padding margin after speech finishes so scene transition feels natural
                synchronized_scene_duration = round(duration + 0.5, 2)
                
                # Keep scene duration at least 4.0 seconds for visual clarity
                scene.duration_seconds = max(4.0, synchronized_scene_duration)
                voice_paths.append(voice_file)
                logger.info(
                    f"Scene {scene.scene_id} speech length: {duration:.2f}s "
                    f"-> Set scene video duration to: {scene.duration_seconds}s"
                )
            else:
                voice_paths.append("")

        return voice_paths

    async def assemble_master_movie(
        self, 
        storyboard: Storyboard, 
        video_paths: List[str], 
        output_path: str,
        pregenerated_voice_paths: Optional[List[str]] = None
    ) -> str:
        """Processes voiceover tracks, background audio, and merges everything into output_path."""
        logger.info("Master Composer initializing audio-visual synchronization...")
        audio_dir = os.path.join(os.path.dirname(output_path), "temp_audio")
        os.makedirs(audio_dir, exist_ok=True)

        # 1. Use pre-generated voice paths if available, otherwise generate them now
        if pregenerated_voice_paths:
            voice_paths = pregenerated_voice_paths
        else:
            voice_paths = await self.prepare_voiceovers_and_sync_durations(storyboard, audio_dir)

        # 2. Total duration of final composition
        total_duration = sum(s.duration_seconds for s in storyboard.scenes)
        
        # 3. Generate or retrieve Background Music
        music_file: Optional[str] = None
        if self.music_provider:
            music_file = os.path.join(audio_dir, "background_music.wav")
            music_prompt = storyboard.scenes[0].music_suggestion if storyboard.scenes else "Cinematic score"
            try:
                self.music_provider.generate_music(music_prompt, total_duration, music_file)
            except Exception as e:
                logger.error(f"Failed to generate background music: {e}")
                music_file = None

        sfx_paths = [music_file] if music_file and os.path.exists(music_file) else None

        # 4. Delegate execution to baseline FFmpeg service
        final_video = self.ffmpeg.stitch_and_mix(
            video_paths=video_paths,
            voice_paths=voice_paths,
            sfx_paths=sfx_paths,
            output_path=output_path
        )

        return final_video