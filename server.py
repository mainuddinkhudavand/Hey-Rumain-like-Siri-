# ============================================================
#  server.py — FastAPI Web Server & WebSocket endpoints
# ============================================================
from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import Event
from config import SERVER_HOST, SERVER_PORT

logger = logging.getLogger(__name__)

# Locate the frontend directory relative to this file
FRONTEND_DIR = Path(__file__).parent / "frontend"

app = FastAPI(title="Rumain Desktop Voice Assistant", version="1.1.0")

# Enable CORS for all origins (useful during frontend development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (HTML, CSS, JS, Images)
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# ── Connection Manager for WebSockets ─────────────────────────
class ConnectionManager:
    def __init__(self) -> None:
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)
        logger.info(f"UI WebSocket client connected. Active connections: {len(self.active)}")

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)
        logger.info(f"UI WebSocket client disconnected. Active connections: {len(self.active)}")

    async def broadcast(self, data: dict) -> None:
        dead = set()
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.add(ws)
        self.active -= dead

manager = ConnectionManager()
_workflow_ref = None  # Reference to the running workflow (set in main.py)

# ── API Routes ────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = FRONTEND_DIR / "index.html"
    if html_path.exists():
        return FileResponse(str(html_path))
    return HTMLResponse("<h1>Rumain Voice Assistant — Frontend Not Found</h1>")

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        while True:
            # Simple keepalive loop
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        manager.disconnect(ws)

class CommandRequest(BaseModel):
    command: str

@app.post("/command")
async def inject_command(req: CommandRequest) -> dict:
    """Manually inject a text command to MindAgent (for text fallback/debugging)."""
    global _workflow_ref
    if _workflow_ref is None:
        return {"error": "Assistant workflow not started"}
    
    # Create event targeting MindAgent (the LLM brain)
    event = Event(source="api", target="mind", payload=req.command)
    await _workflow_ref.enqueue(event)
    
    # Broadcast command entry to UI WebSocket
    await manager.broadcast({"type": "api_command", "command": req.command})
    return {"status": "queued", "command": req.command}

@app.get("/status")
async def get_status() -> dict:
    """Retrieve assistant running status and individual agent states."""
    global _workflow_ref
    if _workflow_ref is None:
        return {"running": False}
    
    states = {name: agent.state.value for name, agent in _workflow_ref._agents.items()}
    return {
        "running": _workflow_ref._running,
        "agents": states
    }

# ── Hooks ─────────────────────────────────────────────────────
async def broadcast_to_ws(data: dict) -> None:
    """Hook passed to RumainWorkflow to broadcast events to client browsers."""
    await manager.broadcast(data)

def set_workflow(wf) -> None:
    """Provide the server with a reference to the active workflow orchestrator."""
    global _workflow_ref
    _workflow_ref = wf
