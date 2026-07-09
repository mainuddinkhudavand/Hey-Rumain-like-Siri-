# ============================================================
#  ui/overlay.py — PyQt5 Tray Icon & 3D Glassmorphic Overlay
#  Provides desktop overlay widget with text fallback input
# ============================================================
import os
import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal, QObject
from config import AGENT_COLORS

# Signaler class to bridge background threads and the Qt main loop thread-safely
class UIBridgeSignaler(QObject):
    state_changed = pyqtSignal(str, str)     # agent_name, state_val
    speech_received = pyqtSignal(str, str)   # text, sender
    system_log = pyqtSignal(str, str)        # log_msg, log_type

# Global bridge instance
ui_bridge = UIBridgeSignaler()

class VoiceAssistantOverlay(QtWidgets.QWidget):
    """
    A beautiful, frameless, translucent, always-on-top desktop overlay.
    Displays the assistant's avatar, active speech transcript, and text fallback input.
    """
    def __init__(self) -> None:
        super().__init__()
        
        # Dragging variables
        self._drag_pos = QtCore.QPoint()
        
        self.init_ui()
        self.connect_signals()

    def init_ui(self) -> None:
        # Window flags: Frameless, Tool window (no taskbar item), Always-on-top
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | 
            QtCore.Qt.WindowStaysOnTopHint | 
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setMinimumSize(320, 480)
        self.resize(340, 520)

        # Move to bottom right of screen
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 40, screen.height() - self.height() - 80)

        # Main Layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # Frame Container (the Glassmorphic card)
        self.card_frame = QtWidgets.QFrame()
        self.card_frame.setObjectName("CardFrame")
        self.card_frame.setStyleSheet("""
            QFrame#CardFrame {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                                    stop:0 rgba(20, 20, 35, 0.82), 
                                    stop:1 rgba(10, 10, 20, 0.9));
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 24px;
            }
        """)
        
        # Shadow effect on the glass card
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QtGui.QColor(0, 0, 0, 180))
        shadow.setOffset(0, 8)
        self.card_frame.setGraphicsEffect(shadow)

        self.card_layout = QtWidgets.QVBoxLayout(self.card_frame)
        self.card_layout.setContentsMargins(20, 15, 20, 20)
        self.card_layout.setSpacing(12)

        # 1. Header Drag Bar & Close Buttons
        self.header_layout = QtWidgets.QHBoxLayout()
        self.header_title = QtWidgets.QLabel("Rumain")
        self.header_title.setStyleSheet("color: white; font-family: 'Outfit'; font-weight: 800; font-size: 15px; letter-spacing: 1px;")
        
        self.close_btn = QtWidgets.QPushButton("✕")
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 50, 100, 0.15);
                color: #ff3264;
                border: 1px solid rgba(255, 50, 100, 0.3);
                border-radius: 11px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #ff3264;
                color: white;
            }
        """)
        self.close_btn.clicked.connect(self.hide)

        self.header_layout.addWidget(self.header_title)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.close_btn)
        self.card_layout.addLayout(self.header_layout)

        # 2. Avatar Container (Pulsing glowing circle with the girl picture)
        self.avatar_layout = QtWidgets.QHBoxLayout()
        self.avatar_widget = QtWidgets.QLabel()
        self.avatar_widget.setFixedSize(140, 140)
        self.avatar_widget.setAlignment(QtCore.Qt.AlignCenter)
        
        # Load avatar.png as pixmap
        avatar_path = os.path.join(os.getcwd(), "frontend", "avatar.png")
        if os.path.exists(avatar_path):
            pixmap = QtGui.QPixmap(avatar_path)
        else:
            # Fallback if avatar.png is missing
            pixmap = QtGui.QPixmap(140, 140)
            pixmap.fill(QtGui.QColor(100, 50, 150))
            
        # Crop pixmap to circle
        size = 130
        rounded_pixmap = QtGui.QPixmap(size, size)
        rounded_pixmap.fill(QtCore.Qt.transparent)
        
        painter = QtGui.QPainter(rounded_pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        path = QtGui.QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, size, size, pixmap.scaled(size, size, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation))
        painter.end()

        self.avatar_widget.setPixmap(rounded_pixmap)
        self.set_avatar_glow("idle")
        
        self.avatar_layout.addStretch()
        self.avatar_layout.addWidget(self.avatar_widget)
        self.avatar_layout.addStretch()
        self.card_layout.addLayout(self.avatar_layout)

        # State label
        self.state_label = QtWidgets.QLabel("Say 'Hey Rumain'")
        self.state_label.setAlignment(QtCore.Qt.AlignCenter)
        self.state_label.setStyleSheet("color: #00f0ff; font-family: 'Outfit'; font-weight: 600; font-size: 14px;")
        self.card_layout.addWidget(self.state_label)

        # 3. Log Feed area (Keep only the conversation logs)
        self.log_area = QtWidgets.QTextBrowser()
        self.log_area.setStyleSheet("""
            QTextBrowser {
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                color: #d1fae5;
                font-family: 'Outfit';
                font-size: 12px;
                padding: 8px;
            }
        """)
        self.log_area.append("<i>Rumain core initialized.</i>")
        self.card_layout.addWidget(self.log_area)

        # 4. Text Fallback Input deck
        self.input_layout = QtWidgets.QHBoxLayout()
        self.input_box = QtWidgets.QLineEdit()
        self.input_box.setPlaceholderText("Type a command...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                background-color: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                color: white;
                font-family: 'Outfit';
                padding: 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #b026ff;
            }
        """)
        self.input_box.returnPressed.connect(self.submit_text_command)

        self.send_btn = QtWidgets.QPushButton("➤")
        self.send_btn.setFixedSize(36, 36)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b026ff, stop:1 #00f0ff);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                transform: scale(1.05);
            }
        """)
        self.send_btn.clicked.connect(self.submit_text_command)

        self.input_layout.addWidget(self.input_box)
        self.input_layout.addWidget(self.send_btn)
        self.card_layout.addLayout(self.input_layout)

        self.main_layout.addWidget(self.card_frame)

    # ── Avatar Glow Customizer ───────────────────────────────
    def set_avatar_glow(self, state: str) -> None:
        """Sets glowing border color on the avatar label based on pipeline states."""
        color_map = {
            "idle": "#b026ff",       # Purple
            "listening": "#00f0ff",  # Cyan
            "thinking": "#b026ff",   # Violet
            "speaking": "#00ff88",   # Emerald
            "error": "#ff3264",      # Red
        }
        color = color_map.get(state, "#b026ff")
        self.avatar_widget.setStyleSheet(f"""
            QLabel {{
                border: 3px solid {color};
                border-radius: 70px;
                background-color: transparent;
                padding: 2px;
            }}
        """)

    # ── Signals Bridge ───────────────────────────────────────
    def connect_signals(self) -> None:
        ui_bridge.state_changed.connect(self.on_state_changed)
        ui_bridge.speech_received.connect(self.on_speech_received)
        ui_bridge.system_log.connect(self.on_system_log)

    def on_state_changed(self, agent_name: str, state: str) -> None:
        # Map agent state to assistant label
        if state == "running":
            state_map = {
                "ear": ("Listening…", "listening"),
                "mind": ("Thinking…", "thinking"),
                "hand": ("Thinking…", "thinking"),
                "voice": ("Speaking…", "speaking"),
            }
            label_text, glow_state = state_map.get(agent_name, ("Processing…", "thinking"))
            self.state_label.setText(label_text)
            self.state_label.setStyleSheet(f"color: {AGENT_COLORS.get(agent_name, '#fff')}; font-weight: bold;")
            self.set_avatar_glow(glow_state)
        elif state == "success" and agent_name == "voice":
            self.state_label.setText("Say 'Hey Rumain'")
            self.state_label.setStyleSheet("color: #00f0ff; font-weight: bold;")
            self.set_avatar_glow("idle")

    def on_speech_received(self, text: str, sender: str) -> None:
        if sender == "user":
            self.log_area.append(f"<span style='color:#00f0ff;'><b>User:</b> \"{text}\"</span>")
        elif sender == "assistant":
            self.log_area.append(f"<span style='color:#00ff88;'><b>Rumain:</b> \"{text}\"</span>")

    def on_system_log(self, msg: str, log_type: str) -> None:
        color = "#a7f3d0" if log_type == "info" else "#ff3264"
        self.log_area.append(f"<span style='color:{color}; font-style:italic;'>{msg}</span>")

    # ── Submission ───────────────────────────────────────────
    def submit_text_command(self) -> None:
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()
        
        # Log to local overlay
        ui_bridge.speech_received.emit(text, "user")
        
        # Inject to pipeline
        from server import inject_command
        # We run it in a separate thread so PyQt5 loop doesn't block on network
        threading.Thread(target=self._run_injection_sync, args=(text,), daemon=True).start()

    def _run_injection_sync(self, text: str) -> None:
        try:
            import urllib.request
            import json
            from config import SERVER_HOST, SERVER_PORT
            url = f"http://{SERVER_HOST}:{SERVER_PORT}/command"
            data = json.dumps({"command": text}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"content-type":"application/json"})
            with urllib.request.urlopen(req) as response:
                response.read()
        except Exception as e:
            logger.error(f"Failed to inject manual Qt text command: {e}")

    # ── Mouse Press/Move Event overrides for dragging Window ─
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.buttons() == QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

# ── System Tray Controller ────────────────────────────────────
class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, parent_window: QtWidgets.QWidget) -> None:
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.init_tray()

    def init_tray(self) -> None:
        # Use simple fallback emoji/character as icon or search file system
        icon_path = os.path.join(os.getcwd(), "frontend", "avatar.png")
        if os.path.exists(icon_path):
            self.setIcon(QtGui.QIcon(icon_path))
        else:
            # Create a simple colored block icon if no asset
            pix = QtGui.QPixmap(32, 32)
            pix.fill(QtGui.QColor(176, 38, 255))
            self.setIcon(QtGui.QIcon(pix))
            
        # Left-click -> Toggle visible
        self.activated.connect(self.on_activated)

        # Context Menu
        self.menu = QtWidgets.QMenu()
        
        self.show_action = self.menu.addAction("Show Assistant")
        self.show_action.triggered.connect(self.parent_window.show)
        
        self.hide_action = self.menu.addAction("Hide Assistant")
        self.hide_action.triggered.connect(self.parent_window.hide)
        
        self.menu.addSeparator()
        
        self.quit_action = self.menu.addAction("Exit Assistant")
        self.quit_action.triggered.connect(QtWidgets.qApp.quit)
        
        self.setContextMenu(self.menu)

    def on_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            if self.parent_window.isVisible():
                self.parent_window.hide()
            else:
                self.parent_window.show()
                self.parent_window.activateWindow()
