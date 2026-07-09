# ============================================================
#  agents/voice_agent.py — The Speaker (TTS & Barge-In)
#  Converts response text → audio via edge-tts or pyttsx3
# ============================================================
from __future__ import annotations
import asyncio
import logging
import os
import tempfile
from typing import Optional

# Pygame for async-friendly audio playback and interruption
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame

from agents import Agent, AgentState, Event
from config import (
    TTS_ENGINE, EDGE_TTS_VOICE, TTS_RATE, TTS_VOLUME, TTS_VOICE_INDEX
)

logger = logging.getLogger(__name__)

class VoiceAgent(Agent):
    """
    VoiceAgent speaks the text response to the user.
    It supports Edge-TTS (high quality cloud streaming) and pyttsx3 (local fallback).
    It implements barge-in support, allowing playback to be interrupted instantly.
    """
    def __init__(self) -> None:
        super().__init__("voice")
        self._broadcast_cb = None
        self._is_speaking = False
        
        # Initialize pygame audio mixer
        try:
            pygame.mixer.init()
        except Exception as e:
            logger.error(f"Failed to initialize pygame mixer: {e}")

    def set_broadcast(self, cb) -> None:
        self._broadcast_cb = cb

    def stop_speaking(self) -> None:
        """Interrupts and stops any currently playing audio (barge-in)."""
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                logger.info("VoiceAgent playback interrupted by user (barge-in).")
        except Exception as e:
            logger.debug(f"Error stopping pygame music: {e}")
        self._is_speaking = False

    async def run(self, event: Event) -> Optional[Event]:
        message: str = str(event.payload)
        logger.info(f"VoiceAgent speaking: '{message}'")
        self.set_state(AgentState.RUNNING)
        self._is_speaking = True

        # Broadcast response to UI WebSocket
        if self._broadcast_cb:
            try:
                await self._broadcast_cb({
                    "type":    "speech",
                    "message": message,
                    "intent":  event.metadata.get("intent", ""),
                    "success": event.metadata.get("success", True),
                })
            except Exception:
                pass

        # Interrupt any current playback before starting new speech
        self.stop_speaking()

        if TTS_ENGINE == "edge-tts":
            await self._speak_edge(message)
        else:
            await self._speak_local(message)

        self._is_speaking = False
        self.set_state(AgentState.SUCCESS)
        return None  # End of pipeline

    async def _speak_edge(self, text: str) -> None:
        """Stream high quality natural soft girl voice using edge-tts."""
        temp_file = None
        try:
            import edge_tts
            
            # Create a secure temporary file to write speech audio
            fd, temp_file = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            
            communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
            await communicate.save(temp_file)
            
            # Play MP3 using pygame
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            
            # Non-blocking wait while audio plays, checking for interruption
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.05)
                
        except Exception as e:
            logger.warning(f"Edge-TTS failed: {e}. Falling back to pyttsx3 offline TTS.")
            await self._speak_local(text)
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    pygame.mixer.music.unload() # Unlock file
                    os.remove(temp_file)
                except Exception:
                    pass

    async def _speak_local(self, text: str) -> None:
        """Fallback to local pyttsx3 offline system voice."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._speak_local_sync, text)

    def _speak_local_sync(self, text: str) -> None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", TTS_RATE)
            engine.setProperty("volume", TTS_VOLUME)
            voices = engine.getProperty("voices")
            if voices and TTS_VOICE_INDEX < len(voices):
                engine.setProperty("voice", voices[TTS_VOICE_INDEX].id)
            engine.say(text)
            engine.runAndWait()
            del engine
        except Exception as e:
            logger.error(f"Local pyttsx3 speaking failed: {e}")
