# ============================================================
#  agents/__init__.py — Voice Assistant Framework Primitives
#  Base Agent, Event, and Workflow classes
# ============================================================
from __future__ import annotations
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Agent States ─────────────────────────────────────────────
class AgentState(str, Enum):
    IDLE      = "idle"
    RUNNING   = "running"
    SUCCESS   = "success"
    ERROR     = "error"
    SLEEPING  = "sleeping"

# ── Event dataclass ──────────────────────────────────────────
@dataclass
class Event:
    """A message passed between agents in the pipeline."""
    source:    str
    target:    str
    payload:   Any
    timestamp: float = field(default_factory=time.time)
    metadata:  dict  = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source":    self.source,
            "target":    self.target,
            "payload":   self.payload,
            "timestamp": self.timestamp,
            "metadata":  self.metadata,
        }

# ── Base Agent ───────────────────────────────────────────────
class Agent(ABC):
    """
    Base class for every agent in the assistant.
    Subclasses must implement:
      - async run(event: Event) -> Event | None
    """
    def __init__(self, name: str) -> None:
        self.name  = name
        self.state = AgentState.IDLE
        self._state_callbacks: list[Callable] = []

    @abstractmethod
    async def run(self, event: Event) -> Optional[Event]:
        """Process an incoming event and optionally return a new event."""
        ...

    def set_state(self, state: AgentState) -> None:
        self.state = state
        for cb in self._state_callbacks:
            try:
                cb(self.name, state.value)
            except Exception as e:
                logger.debug(f"Error in state callback: {e}")

    def on_state_change(self, callback: Callable) -> None:
        """Register a callback: callback(agent_name: str, state: str)"""
        self._state_callbacks.append(callback)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} state={self.state.value!r}>"
