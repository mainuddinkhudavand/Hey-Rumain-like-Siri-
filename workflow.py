# ============================================================
#  workflow.py — Central Pipeline Orchestrator
#  Routes events and logs history to SQLite memory
# ============================================================
from __future__ import annotations
import asyncio
import logging
import time
from typing import Any, Callable, Optional, Dict
from agents import Agent, AgentState, Event
from memory import AssistantMemory

logger = logging.getLogger(__name__)

class RumainWorkflow:
    """
    Routes events through the pipeline:
      EarAgent (Listener) -> MindAgent (Brain) -> HandAgent (Executor) -> VoiceAgent (TTS)
    Logs conversation to SQLite memory and broadcasts status to WebSockets.
    """
    PIPELINE = ["ear", "mind", "hand", "voice"]

    def __init__(self, agents: Dict[str, Agent]) -> None:
        self._agents = agents
        self._queue: asyncio.Queue = asyncio.Queue()
        self._broadcast_cbs: list[Callable] = []
        self._running = False
        self.memory = AssistantMemory()

        # Connect state changes of each agent to the workflow broadcast
        for agent in agents.values():
            agent.on_state_change(self._on_state_change)

    # ── Enqueue ───────────────────────────────────────────────
    async def enqueue(self, event: Event) -> None:
        await self._queue.put(event)

    def enqueue_sync(self, event: Event) -> None:
        """Thread-safe enqueue from background threads (EarAgent)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(asyncio.ensure_future, self.enqueue(event))
            else:
                asyncio.run(self.enqueue(event))
        except RuntimeError:
            pass

    # ── Registration & Broadcast ──────────────────────────────
    def register_broadcast(self, cb: Callable) -> None:
        self._broadcast_cbs.append(cb)

    def _on_state_change(self, name: str, state: str) -> None:
        # Update PyQt UI if active
        try:
            from ui.overlay import ui_bridge
            ui_bridge.state_changed.emit(name, state)
        except Exception:
            pass

        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                asyncio.ensure_future,
                self._broadcast({"type": "agent_state", "agent": name, "state": state})
            )
        except RuntimeError:
            pass

    async def _broadcast(self, data: dict) -> None:
        for cb in self._broadcast_cbs:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(data)
                else:
                    cb(data)
            except Exception as e:
                logger.debug(f"Broadcast error: {e}")

    # ── Main Loop ─────────────────────────────────────────────
    async def start(self) -> None:
        self._running = True
        logger.info("RumainWorkflow started.")
        await self._broadcast({"type": "workflow", "status": "started", "pipeline": self.PIPELINE})

        while self._running:
            try:
                # Wait for an event in the pipeline
                event: Event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Workflow loop error: {e}", exc_info=True)

    async def _process(self, event: Event) -> None:
        agent = self._agents.get(event.target)
        if not agent:
            logger.warning(f"Unknown target: {event.target!r}")
            return

        # Broadcast event info to UI
        event_data = {
            "type":    "pipeline_event",
            "source":  event.source,
            "target":  event.target,
            "payload": str(event.payload)[:500],
            "metadata": event.metadata,
            "ts":      time.time(),
        }
        await self._broadcast(event_data)

        # Log conversation to SQLite Memory and notify PyQt UI
        if event.source == "ear" and event.target == "mind":
            self.memory.add_message("user", str(event.payload))
            try:
                from ui.overlay import ui_bridge
                ui_bridge.speech_received.emit(str(event.payload), "user")
            except Exception:
                pass
        elif event.source == "hand" and event.target == "voice":
            self.memory.add_message("assistant", str(event.payload))
            try:
                from ui.overlay import ui_bridge
                ui_bridge.speech_received.emit(str(event.payload), "assistant")
            except Exception:
                pass
        elif event.source == "mind" and event.target == "voice":
            self.memory.add_message("assistant", str(event.payload))
            try:
                from ui.overlay import ui_bridge
                ui_bridge.speech_received.emit(str(event.payload), "assistant")
            except Exception:
                pass

        try:
            result: Optional[Event] = await agent.run(event)
            if result:
                await self._queue.put(result)
        except Exception as e:
            logger.error(f"Agent {agent.name} error: {e}", exc_info=True)
            agent.set_state(AgentState.ERROR)
            
            err_data = {"type": "error", "agent": agent.name, "message": str(e), "ts": time.time()}
            await self._broadcast(err_data)

    async def stop(self) -> None:
        self._running = False
        await self._broadcast({"type": "workflow", "status": "stopped"})
        logger.info("RumainWorkflow stopped.")
