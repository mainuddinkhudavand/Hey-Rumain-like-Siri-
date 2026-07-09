# Rumain — 3D Desktop AI Voice Assistant

> **Wake word:** "Hey Rumain"  
> **Hotkey:** Double-tap `Ctrl`  
> A cross-platform Siri-like AI desktop assistant featuring a premium 3D Glassmorphic Overlay, custom Tool execution registry, Edge-TTS natural female voice, and SQLite-backed memory.

---

## 🏗️ Architecture

```
Microphone → [EarAgent] → [MindAgent] → [HandAgent] → [VoiceAgent] → Speaker
                ↕                                       ↕
         PyQt5 Overlay                         Edge-TTS / pyttsx3
         (System Tray)                                  ↕
                └────────── SQLite Memory DB ───────────┘
```

| Component | Role | Tech Stack |
|---|---|---|
| **EarAgent** | Wake word listening, manual hotkey hook, STT | `pyaudio`, `SpeechRecognition`, `vosk`, `keyboard` |
| **MindAgent** | Conversational context retrieval, tool selection prompt routing | `Claude API` (Anthropic) or local `Ollama` |
| **HandAgent** | Tool Registry dispatcher & script executor | Python execution interface |
| **VoiceAgent** | Natural soft girl voice narration (interruption-aware) | `edge-tts`, `pygame.mixer` (barge-in), `pyttsx3` |
| **UI Overlay** | Always-on-top glassmorphic widget & tray icon | `PyQt5` framework |
| **Memory** | Chat logs history buffer and user preferences storage | `SQLite` database |

---

## ⚡ Quick Setup

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```powershell
copy .env.example .env
```
Set `ANTHROPIC_API_KEY` to use the Claude LLM brain, or launch **Ollama** locally to run completely offline.

### 3. Run Diagnostic Tests (Recommended)
Before starting the assistant, run these diagnostic scripts to verify your system audio and tools configuration:
- Test Microphone access: `python test_microphone.py`
- Test Edge-TTS voice playback: `python test_tts.py`
- Test Tool registration: `python test_tools.py`

### 4. Launch Rumain
```powershell
python main.py
```

---

## 🎤 Core Features & Commands

1. **Passive Offline Wake Word**: Pasively listens for `"Hey Rumain"`.
2. **Keyboard Hotkey Wake**: Double-tap `Ctrl` to immediately trigger the assistant (without saying the wake word).
3. **Barge-in (Interruption Support)**: Start speaking your next command while the assistant is talking, and she will immediately stop to listen to you.
4. **Desktop Overlay**: A floating window in the bottom-right of your screen showing states (Listening/Thinking/Speaking) with a text input box if you prefer typing.

### Sample Voice Instructions
- `"Open notepad"` or `"Close notepad"`
- `"Search Google for space telescopes"`
- `"Volume up"` or `"Set volume to 40 percent"`
- `"Take a screenshot"`
- `"Set a timer for 10 seconds to take a break"`
- `"Type congratulations on your new role"` (Types text at cursor)
- `"What is my CPU status?"`

---

## 📁 Project Structure

```
quick-maxwell/
├── main.py               ← App Orchestrator and entry point
├── config.py             ← Environment options mapping
├── server.py             ← FastAPI / WebSockets routing
├── workflow.py           ← Agents communication bridge
├── memory.py             ← SQLite database store
├── requirements.txt      ← PIP package list
├── agents/               ← Framework agents
│   ├── __init__.py       ← Agent and Event base classes
│   ├── ear_agent.py      ← Microphone listener & hotkey hook
│   ├── mind_agent.py     ← LLM interface and tool routing
│   ├── hand_agent.py     ← Executor module
│   └── voice_agent.py    ← Natural TTS player
├── tools/                ← Tool registry
│   ├── __init__.py       ← Registry decorator mapping
│   ├── os_tools.py       ← Launch app and URLs
│   ├── system_tools.py   ← Volume, brightness, stats, media
│   ├── clipboard_tools.py← Clipboard read/write, simulated typing
│   └── utility_tools.py  ← Note saver, file search, timer alert
├── ui/                   ← PyQt5 interface
│   ├── __init__.py
│   └── overlay.py        ← Frameless always-on-top overlay & tray
└── frontend/             ← Three.js 3D dashboard assets
```
