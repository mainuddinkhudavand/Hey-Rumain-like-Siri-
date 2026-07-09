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
                self.set_state(AgentState.ERROR)
                return Event(
                    source="mind",
                    target="voice",
                    payload="Please configure your Anthropic API Key in the dot env file to use my brain.",
                    metadata={"intent": "configuration_needed", "success": False}
                )
            
            # 4. Call the configured LLM Provider
            if LLM_PROVIDER == "claude":
                response = await self._call_claude(user_input, context, tool_schemas)
            else:
                response = await self._call_ollama(user_input, context, tool_schemas)
                
            self.set_state(AgentState.SUCCESS)
            return self._route_response(response, user_input)
            
        except Exception as e:
            logger.error(f"MindAgent error: {e}", exc_info=True)
            self.set_state(AgentState.ERROR)
            # Fallback direct response
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
