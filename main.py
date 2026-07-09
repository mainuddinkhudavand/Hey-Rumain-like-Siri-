# ============================================================
#  main.py — Assistant Entry Point & Orchestrator
#  Starts the background voice pipeline, web server, and PyQt5 GUI
# ============================================================
from __future__ import annotations
import asyncio
import logging
import sys
import threading
import io
import uvicorn
from PyQt5 import QtWidgets

from agents.ear_agent import EarAgent
from agents.mind_agent import MindAgent
from agents.hand_agent import HandAgent
from agents.voice_agent import VoiceAgent
from workflow import RumainWorkflow
from server import app, broadcast_to_ws, set_workflow
from config import SERVER_HOST, SERVER_PORT, LOG_LEVEL
from ui.overlay import VoiceAssistantOverlay, SystemTrayIcon, ui_bridge

# ── Logging Setup ────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(
            io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            if hasattr(sys.stdout, 'buffer') else sys.stdout
        )
    ],
)
logger = logging.getLogger(__name__)

# ── Global Loop & Agents ─────────────────────────────────────
backend_loop = asyncio.new_event_loop()

ear = EarAgent()
mind = MindAgent()
hand = HandAgent()
voice = VoiceAgent()

agents = {"ear": ear, "mind": mind, "hand": hand, "voice": voice}
workflow = RumainWorkflow(agents)

def run_backend():
    """Runs the uvicorn web server and the agent pipeline inside the asyncio loop."""
    asyncio.set_event_loop(backend_loop)
    
    # Wire VoiceAgent's speech events to websocket broadcast
    voice.set_broadcast(broadcast_to_ws)
    
    # Wire workflow to server reference
    set_workflow(workflow)
    workflow.register_broadcast(broadcast_to_ws)
    
    # Start EarAgent background thread and connect it to VoiceAgent for barge-in
    ear.start_listening(workflow, voice)
    
    # Configure and run uvicorn
    config = uvicorn.Config(
        app, host=SERVER_HOST, port=SERVER_PORT,
        log_level="warning", loop="asyncio"
    )
    server = uvicorn.Server(config)
    
    async def main_async():
        server_task = asyncio.create_task(server.serve())
        try:
            await workflow.start()
        finally:
            await workflow.stop()
            ear.stop_listening()
            server_task.cancel()
            
    try:
        backend_loop.run_until_complete(main_async())
    except Exception as e:
        logger.error(f"Backend loop raised exception: {e}")

# ── Startup ──────────────────────────────────────────────────
def main() -> None:
    logger.info("=" * 60)
    logger.info("  RUMAIN 3D Desktop Assistant — Starting Up")
    logger.info("=" * 60)

    # 1. Start backend uvicorn & agent workflow in a background thread
    backend_thread = threading.Thread(target=run_backend, daemon=True, name="Backend-Thread")
    backend_thread.start()
    
    logger.info(f"Dashboard available at: http://{SERVER_HOST}:{SERVER_PORT}")

    # 2. Launch the PyQt5 Desktop GUI Overlay on the main thread
    qt_app = QtWidgets.QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False) # Keep running in system tray if overlay is closed
    
    overlay = VoiceAssistantOverlay()
    tray_icon = SystemTrayIcon(overlay)
    
    overlay.show()
    tray_icon.show()
    
    logger.info("PyQt5 tray icon and always-on-top overlay initialized.")

    # 3. Handle clean shutdown on GUI quit
    def cleanup():
        logger.info("Cleaning up and stopping assistant threads...")
        # Signal asyncio loop to stop
        backend_loop.call_soon_threadsafe(backend_loop.stop)
        
    qt_app.aboutToQuit.connect(cleanup)

    # 4. Run Qt Main Event Loop
    sys.exit(qt_app.exec_())

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Rumain] Shutting down...")
