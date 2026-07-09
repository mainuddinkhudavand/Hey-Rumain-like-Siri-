# ============================================================
#  agents/ear_agent.py — The Listener (Wake Word & STT)
#  Monitors mic, detects wake word / hotkey, captures speech
# ============================================================
from __future__ import annotations
import asyncio
import logging
import threading
import time
import io
import wave
import sys
from typing import Optional

import pyaudio
import speech_recognition as sr
from agents import Agent, AgentState, Event
from config import (
    WAKE_WORD, WAKE_WORD_ENGINE, STT_ENGINE, 
    MIC_ENERGY_THRESHOLD, MIC_PAUSE_THRESHOLD, MIC_PHRASE_LIMIT,
    TOGGLE_HOTKEY
)

logger = logging.getLogger(__name__)

class EarAgent(Agent):
    """
    EarAgent listens to the user.
    It sits in SLEEPING state, listening offline for the wake word ('Hey Rumain')
    or waiting for a manual hotkey trigger. Once triggered, it transitions to
    RUNNING, records the user's spoken command until silence, transcribes it,
    and passes it down to the MindAgent (LLM Brain).
    """
    def __init__(self) -> None:
        super().__init__("ear")
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = MIC_ENERGY_THRESHOLD
        self._recognizer.pause_threshold  = MIC_PAUSE_THRESHOLD
        self._recognizer.non_speaking_duration = 0.5
        
        self._mic = None
        self._workflow = None
        self._stop_evt = threading.Event()
        self._is_active = False # True when actively recording a command
        
        # Hotkey state
        self._last_hotkey_time = 0
        self._hotkey_hooked = False
        
        # Vosk offline model (optional lazy loading)
        self._vosk_model = None
        self._vosk_recognizer = None

    def start_listening(self, workflow) -> None:
        """Initialize and start background threads for listening and hotkeys."""
        self._workflow = workflow
        
        # Start microphone listen thread
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True, name="EarAgent-Listen")
        self._listen_thread.start()
        
        # Start keyboard hotkey thread
        self._hotkey_thread = threading.Thread(target=self._hotkey_loop, daemon=True, name="EarAgent-Hotkey")
        self._hotkey_thread.start()
        
        logger.info("EarAgent background listener & hotkey threads initialized.")

    def stop_listening(self) -> None:
        self._stop_evt.set()

    # ── Hotkey Loop ──────────────────────────────────────────
    def _hotkey_loop(self) -> None:
        """Listens for keyboard hotkey (e.g. double-tapping Ctrl) to trigger listening."""
        try:
            import keyboard
            
            def on_key_event(event):
                # We target the key specified in config (default 'ctrl')
                if event.name == TOGGLE_HOTKEY and event.event_type == 'down':
                    current_time = time.time()
                    # Check for double tap within 0.4 seconds
                    if current_time - self._last_hotkey_time < 0.4:
                        logger.info("Hotkey double-tap detected! Triggering assistant.")
                        self._trigger_wake()
                    self._last_hotkey_time = current_time
            
            keyboard.hook(on_key_event)
            self._hotkey_hooked = True
            logger.info(f"Global hotkey listener bound to: Double-tap [{TOGGLE_HOTKEY}]")
            
            while not self._stop_evt.is_set():
                time.sleep(1)
        except Exception as e:
            logger.warning(f"Failed to bind global hotkey (requires admin privileges on some systems): {e}")

    # ── STT Transcriptions ───────────────────────────────────
    def _speech_to_text(self, audio: sr.AudioData) -> Optional[str]:
        if STT_ENGINE == "google":
            return self._transcribe_google(audio)
        elif STT_ENGINE == "vosk":
            return self._transcribe_vosk(audio)
        return self._transcribe_google(audio)

    def _transcribe_google(self, audio: sr.AudioData) -> Optional[str]:
        try:
            text = self._recognizer.recognize_google(audio)
            return text.strip()
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.error(f"Google STT service error: {e}")
            return None

    def _transcribe_vosk(self, audio: sr.AudioData) -> Optional[str]:
        try:
            import json
            from vosk import Model, KaldiRecognizer
            
            # Lazily load Vosk model
            if self._vosk_model is None:
                model_path = os.path.join(os.getcwd(), "model")
                if not os.path.exists(model_path):
                    logger.warning("Vosk model folder not found at './model'. Falling back to Google STT.")
                    return self._transcribe_google(audio)
                logger.info("Loading Vosk Model from ./model...")
                self._vosk_model = Model(model_path)
                
            wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
            rec = KaldiRecognizer(self._vosk_model, 16000)
            rec.AcceptWaveform(wav_data)
            res = json.loads(rec.Result())
            text = res.get("text", "")
            return text if text else None
        except Exception as e:
            logger.error(f"Vosk STT error: {e}")
            return None

    # ── Active Wake Trigger ──────────────────────────────────
    def _trigger_wake(self) -> None:
        """Trigger the assistant to immediately wake up and listen for a command."""
        self._is_active = True

    # ── Background Listen Loop ────────────────────────────────
    def _listen_loop(self) -> None:
        self.set_state(AgentState.SLEEPING)
        
        try:
            self._mic = sr.Microphone()
            with self._mic as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=1.0)
            logger.info("Microphone noise calibration complete.")
        except Exception as e:
            logger.error(f"No microphone detected or error accessing input device: {e}")
            self.set_state(AgentState.ERROR)
            return

        while not self._stop_evt.is_set():
            try:
                # If we are in SLEEPING state, check if wake word trigger or hotkey was hit
                if not self._is_active:
                    self.set_state(AgentState.SLEEPING)
                    
                    # Capture a short audio slice to check for wake word
                    with self._mic as source:
                        audio = self._recognizer.listen(source, phrase_time_limit=3.0)
                    
                    # Transcribe and look for wake word
                    transcript = self._speech_to_text(audio)
                    if transcript and WAKE_WORD in transcript.lower():
                        logger.info(f"Wake word detected! Heard: '{transcript}'")
                        self._trigger_wake()
                    else:
                        continue

                # If triggered, record the command
                if self._is_active:
                    logger.info("Listening for command...")
                    self.set_state(AgentState.RUNNING)
                    
                    with self._mic as source:
                        audio = self._recognizer.listen(
                            source, 
                            phrase_time_limit=MIC_PHRASE_LIMIT
                        )
                    
                    self._is_active = False # Reset trigger
                    
                    # Transcribe the active command
                    self.set_state(AgentState.IDLE)
                    command = self._speech_to_text(audio)
                    
                    if not command:
                        logger.info("Did not hear a clear command. Returning to sleep.")
                        continue
                        
                    logger.info(f"Captured command: '{command}'")
                    self.set_state(AgentState.SUCCESS)
                    
                    # Package event and push to MindAgent (Brain)
                    self._workflow.enqueue_sync(Event(
                        source="ear",
                        target="mind",
                        payload=command,
                        metadata={"raw_transcript": command}
                    ))
                    
            except Exception as e:
                logger.error(f"Error in EarAgent listening loop: {e}", exc_info=True)
                self.set_state(AgentState.ERROR)
                time.sleep(1.0)

    async def run(self, event: Event) -> Optional[Event]:
        # EarAgent is passive, does not receive pipeline events
        return None
