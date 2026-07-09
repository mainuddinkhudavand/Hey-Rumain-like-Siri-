# ============================================================
#  agents/mind_agent.py — The Brain (LLM Client & Tool Router)
#  Sends user prompt + context to Claude/Ollama and parses intent
# ============================================================
from __future__ import annotations
import json
import logging
import urllib.request
import urllib.error
import asyncio
from typing import Optional, Dict, Any, List

from agents import Agent, AgentState, Event
from config import (
    LLM_PROVIDER, ANTHROPIC_API_KEY, CLAUDE_MODEL,
    OLLAMA_HOST, OLLAMA_MODEL
)
from tools import registry
from memory import AssistantMemory

logger = logging.getLogger(__name__)

class MindAgent(Agent):
    """
    MindAgent processes incoming text commands.
    It grabs the recent chat logs from SQLite, combines it with the
    available tool schemas, calls the LLM (Claude or Ollama), and routes
    the result. If the LLM wants to run a tool, it outputs a payload for HandAgent.
    If the LLM just wants to speak, it outputs a payload for VoiceAgent.
    """
    def __init__(self) -> None:
        super().__init__("mind")
        self.memory = AssistantMemory()

    async def run(self, event: Event) -> Optional[Event]:
        user_input: str = str(event.payload).strip()
        logger.info(f"MindAgent processing user prompt: '{user_input}'")
        self.set_state(AgentState.RUNNING)

        try:
            # 1. Fetch recent conversation context from SQLite memory
            context = self.memory.get_recent_context(limit=10)
            
            # 2. Get tool schemas from the registry
            tool_schemas = registry.schemas
            
            # 3. Check for API key configuration
            if LLM_PROVIDER == "claude" and not ANTHROPIC_API_KEY:
                logger.warning("Anthropic key missing; falling back to rule-based parser.")
                fallback_event = self._rule_based_fallback(user_input)
                self.set_state(AgentState.SUCCESS)
                return fallback_event
            
            # 4. Call the configured LLM Provider
            if LLM_PROVIDER == "claude":
                response = await self._call_claude(user_input, context, tool_schemas)
            else:
                response = await self._call_ollama(user_input, context, tool_schemas)
                
            self.set_state(AgentState.SUCCESS)
            return self._route_response(response, user_input)
            
        except Exception as e:
            logger.error(f"MindAgent error: {e}", exc_info=True)
            try:
                fallback_event = self._rule_based_fallback(user_input)
                self.set_state(AgentState.SUCCESS)
                return fallback_event
            except Exception as fe:
                logger.error(f"Fallback brain failed: {fe}")
                self.set_state(AgentState.ERROR)
                return Event(
                    source="mind",
                    target="voice",
                    payload="I encountered an issue processing that request with my brain.",
                    metadata={"intent": "error", "success": False}
                )

    # ── Claude API Caller ────────────────────────────────────
    async def _call_claude(self, prompt: str, context: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call Anthropic Claude Messages API using urllib to avoid heavy SDK dependencies."""
        if not ANTHROPIC_API_KEY:
            raise ValueError("Anthropic API key (ANTHROPIC_API_KEY) is missing in environment/config.")

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Build messages payload from history
        messages = []
        for msg in context:
            messages.append({"role": msg["role"], "content": msg["content"]})
            
        # Append the new user prompt (if not already logged by workflow)
        if not messages or messages[-1]["content"] != prompt:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "system": "You are a helpful Siri-like desktop voice assistant named Rumain. You can control the user's computer via tools. Keep your verbal responses concise and natural for speech.",
            "messages": messages
        }
        
        if tools:
            payload["tools"] = tools

        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        
        try:
            # Run blocking request in a thread pool executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self._send_request, req)
            return json.loads(response.decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            logger.error(f"Claude API HTTP Error: {error_body}")
            raise Exception(f"Claude API returned status {e.code}: {error_body}")

    def _send_request(self, req: urllib.request.Request) -> bytes:
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.read()

    # ── Ollama Local Caller ──────────────────────────────────
    async def _call_ollama(self, prompt: str, context: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call local Ollama server using a highly structured JSON system prompt."""
        url = f"{OLLAMA_HOST}/api/chat"
        
        # Build messages list
        messages = []
        for msg in context:
            messages.append({"role": msg["role"], "content": msg["content"]})
        if not messages or messages[-1]["content"] != prompt:
            messages.append({"role": "user", "content": prompt})

        # Inject tool schemas as JSON into system prompt to enforce structured calling
        system_instructions = (
            "You are a helpful Siri-like desktop voice assistant named Rumain. "
            "You can execute actions on the user's computer.\n"
            f"Here are the available tools you can call: {json.dumps(tools)}\n\n"
            "You MUST respond ONLY with a JSON object in one of these two formats:\n"
            "1. To run a tool:\n"
            '{"tool_call": {"name": "TOOL_NAME", "arguments": { ... }}}\n'
            "2. To speak directly to the user (no tools needed):\n"
            '{"assistant_response": "YOUR_NATURAL_SPEAKING_RESPONSE"}\n\n'
            "Do not output anything else except valid JSON. Keep verbal responses short."
        )
        
        full_messages = [{"role": "system", "content": system_instructions}] + messages
        
        payload = {
            "model": OLLAMA_MODEL,
            "messages": full_messages,
            "stream": False,
            "format": "json" # Force Ollama model to output valid JSON
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST"
        )
        
        try:
            loop = asyncio.get_event_loop()
            res_bytes = await loop.run_in_executor(None, self._send_request, req)
            res_json = json.loads(res_bytes.decode("utf-8"))
            
            # Parse the model text into our mock Claude response format
            text_response = res_json["message"]["content"].strip()
            parsed = json.loads(text_response)
            
            # Formulate mock Anthropic response object
            if "tool_call" in parsed:
                return {
                    "stop_reason": "tool_use",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": parsed["tool_call"]["name"],
                            "input": parsed["tool_call"]["arguments"],
                            "id": "ollama_tool"
                        }
                    ]
                }
            else:
                return {
                    "stop_reason": "end_turn",
                    "content": [
                        {"type": "text", "text": parsed.get("assistant_response", "Yes, I am here.")}
                    ]
                }
        except Exception as e:
            logger.error(f"Ollama local client failed: {e}")
            raise Exception(f"Local Ollama connection failed. Is Ollama running on {OLLAMA_HOST}?")

    # ── Intent Router ────────────────────────────────────────
    def _route_response(self, response: Dict[str, Any], prompt: str) -> Event:
        """Route LLM response: either to HandAgent for tool execution, or VoiceAgent for TTS."""
        content_blocks = response.get("content", [])
        
        # Check if the stop reason is tool execution
        if response.get("stop_reason") == "tool_use":
            # Extract tool use block
            tool_block = next((b for b in content_blocks if b.get("type") == "tool_use"), None)
            if tool_block:
                tool_name = tool_block["name"]
                tool_args = tool_block.get("input", {})
                tool_id = tool_block.get("id", "tool_id")
                
                logger.info(f"LLM Brain selected tool: {tool_name} with args: {tool_args}")
                return Event(
                    source="mind",
                    target="hand",
                    payload={
                        "action": "execute_tool",
                        "tool_name": tool_name,
                        "arguments": tool_args,
                        "tool_id": tool_id
                    },
                    metadata={"intent": tool_name}
                )
                
        # Conversational Response (just text output)
        text_block = next((b for b in content_blocks if b.get("type") == "text"), None)
        text_content = text_block.get("text", "I'm not sure how to respond.") if text_block else "Yes?"
        
        logger.info(f"LLM Brain conversational response: '{text_content}'")
        return Event(
            source="mind",
            target="voice",
            payload=text_content,
            metadata={"intent": "conversation", "success": True}
        )

    # ── Rule-Based Fallback Brain ────────────────────────────
    def _rule_based_fallback(self, user_input: str) -> Event:
        user_input_lower = user_input.lower()
        import time
        
        # Open Application
        if "open" in user_input_lower:
            app_name = "notepad"
            if "code" in user_input_lower or "vs" in user_input_lower:
                app_name = "vscode"
            elif "chrome" in user_input_lower or "browser" in user_input_lower:
                app_name = "chrome"
            elif "calculator" in user_input_lower or "calc" in user_input_lower:
                app_name = "calc"
            
            # Simple word extractor
            words = user_input_lower.split()
            try:
                open_idx = words.index("open")
                if open_idx + 1 < len(words):
                    app_name = words[open_idx + 1]
            except ValueError:
                pass
                
            return Event(
                source="mind",
                target="hand",
                payload={
                    "action": "execute_tool",
                    "tool_name": "open_application",
                    "arguments": {"app_name": app_name},
                    "tool_id": "fallback_tool"
                },
                metadata={"intent": "open_application"}
            )
            
        # Close Application
        if "close" in user_input_lower or "kill" in user_input_lower:
            app_name = "notepad"
            if "code" in user_input_lower or "vs" in user_input_lower:
                app_name = "code"
            elif "chrome" in user_input_lower or "browser" in user_input_lower:
                app_name = "chrome"
                
            return Event(
                source="mind",
                target="hand",
                payload={
                    "action": "execute_tool",
                    "tool_name": "close_application",
                    "arguments": {"app_name": app_name},
                    "tool_id": "fallback_tool"
                },
                metadata={"intent": "close_application"}
            )

        # Launch URL / Search
        if "google" in user_input_lower or "search" in user_input_lower:
            query = user_input
            if "search for" in user_input_lower:
                query = user_input.split("search for", 1)[1].strip()
            elif "search" in user_input_lower:
                query = user_input.split("search", 1)[1].strip()
            elif "google" in user_input_lower:
                query = user_input.split("google", 1)[1].strip()
                
            return Event(
                source="mind",
                target="hand",
                payload={
                    "action": "execute_tool",
                    "tool_name": "search_web",
                    "arguments": {"query": query},
                    "tool_id": "fallback_tool"
                },
                metadata={"intent": "search_web"}
            )

        # Volume Controls
        if "volume" in user_input_lower:
            level = 50
            if "up" in user_input_lower or "increase" in user_input_lower:
                level = 70
            elif "down" in user_input_lower or "decrease" in user_input_lower:
                level = 20
            elif "mute" in user_input_lower:
                level = 0
                
            return Event(
                source="mind",
                target="hand",
                payload={
                    "action": "execute_tool",
                    "tool_name": "set_volume",
                    "arguments": {"level": level},
                    "tool_id": "fallback_tool"
                },
                metadata={"intent": "set_volume"}
            )
            
        # Brightness Controls
        if "brightness" in user_input_lower:
            level = 50
            if "up" in user_input_lower or "increase" in user_input_lower:
                level = 80
            elif "down" in user_input_lower or "decrease" in user_input_lower:
                level = 30
                
            return Event(
                source="mind",
                target="hand",
                payload={
                    "action": "execute_tool",
                    "tool_name": "set_brightness",
                    "arguments": {"level": level},
                    "tool_id": "fallback_tool"
                },
                metadata={"intent": "set_brightness"}
            )

        # Screenshot
        if "screenshot" in user_input_lower or "screen shot" in user_input_lower:
            return Event(
                source="mind",
                target="hand",
                payload={
                    "action": "execute_tool",
                    "tool_name": "take_screenshot",
                    "arguments": {},
                    "tool_id": "fallback_tool"
                },
                metadata={"intent": "take_screenshot"}
            )

        # System Status
        if "status" in user_input_lower or "cpu" in user_input_lower or "ram" in user_input_lower or "battery" in user_input_lower or "specs" in user_input_lower:
            return Event(
                source="mind",
                target="hand",
                payload={
                    "action": "execute_tool",
                    "tool_name": "get_system_status",
                    "arguments": {},
                    "tool_id": "fallback_tool"
                },
                metadata={"intent": "get_system_status"}
            )

        # Clipboard
        if "clipboard" in user_input_lower or "paste" in user_input_lower:
            return Event(
                source="mind",
                target="hand",
                payload={
                    "action": "execute_tool",
                    "tool_name": "read_clipboard",
                    "arguments": {},
                    "tool_id": "fallback_tool"
                },
                metadata={"intent": "read_clipboard"}
            )

        # Time
        if "time" in user_input_lower or "date" in user_input_lower:
            from datetime import datetime
            now_str = datetime.now().strftime("%I:%M %p")
            return Event(
                source="mind",
                target="voice",
                payload=f"The current local time is {now_str}.",
                metadata={"intent": "response", "success": True}
            )

        # Hello / Greetings
        if "hello" in user_input_lower or "hi" in user_input_lower or "hey" in user_input_lower:
            return Event(
                source="mind",
                target="voice",
                payload="Hello! I am running in local backup mode. Ask me to open notepad, check system status, or run system tools!",
                metadata={"intent": "response", "success": True}
            )

        # Default conversational response
        return Event(
            source="mind",
            target="voice",
            payload=f"I heard you say '{user_input}'. My full brain is currently offline. You can configure your Anthropic API Key in the .env file, or ask me to open apps like notepad or check system status in backup mode.",
            metadata={"intent": "response", "success": True}
        )
