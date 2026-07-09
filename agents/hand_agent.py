# ============================================================
#  agents/hand_agent.py — The Executor (Tool Runner)
#  Runs the registered tools selected by MindAgent
# ============================================================
from __future__ import annotations
import logging
from typing import Optional

from agents import Agent, AgentState, Event
from tools import registry
# Import tools so they register themselves on startup
from tools import os_tools, system_tools, clipboard_tools, utility_tools

logger = logging.getLogger(__name__)

class HandAgent(Agent):
    """
    HandAgent executes OS automation tools.
    It receives tool execution instructions from MindAgent,
    runs the python function mapped in the tools registry, and
    sends the text result to VoiceAgent to be read aloud.
    """
    def __init__(self) -> None:
        super().__init__("hand")

    async def run(self, event: Event) -> Optional[Event]:
        payload = event.payload
        action = payload.get("action")
        
        if action != "execute_tool":
            logger.warning(f"HandAgent received unknown action: {action}")
            return Event(
                source="hand",
                target="voice",
                payload="I don't know how to execute that action.",
                metadata={"intent": "unknown", "success": False}
            )

        tool_name = payload.get("tool_name", "")
        tool_args = payload.get("arguments", {})
        
        logger.info(f"HandAgent executing tool '{tool_name}' with args: {tool_args}")
        self.set_state(AgentState.RUNNING)
        
        try:
            # Run the tool from the registry (supports async/sync execution)
            message = await registry.execute(tool_name, tool_args)
            success = not message.startswith("Error")
            
            logger.info(f"HandAgent execution result: {message}")
            self.set_state(AgentState.SUCCESS)
            
        except Exception as e:
            logger.error(f"HandAgent failed to execute tool '{tool_name}': {e}", exc_info=True)
            message = f"I failed to execute the {tool_name.replace('_', ' ')} action."
            success = False
            self.set_state(AgentState.ERROR)
            
        # Send confirmation event to VoiceAgent (TTS)
        return Event(
            source="hand",
            target="voice",
            payload=message,
            metadata={"intent": tool_name, "success": success}
        )
