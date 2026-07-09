# ============================================================
#  memory.py — Persistent SQLite Memory Store
#  Handles chat logs, short-term context, and user settings
# ============================================================
import sqlite3
import time
from typing import Any, List, Dict, Optional
from config import DB_PATH

class AssistantMemory:
    """
    Manages assistant memory using a local SQLite database.
    Provides storage for chat messages (conversation history) and
    persistent key-value pairs (user preferences, status stats).
    """
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            # Create messages history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            # Create user settings / preferences table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()

    # ── Chat Memory (Conversation History) ────────────────────
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the history (role: 'user' or 'assistant')."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (role, content, timestamp) VALUES (?, ?, ?)",
                (role, content, time.time())
            )
            conn.commit()

    def get_recent_context(self, limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve recent conversation context for LLM prompt."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            # Reverse to get chronological order
            messages = [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
            return messages

    def clear_history(self) -> None:
        """Clear all conversation logs."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages")
            conn.commit()

    # ── Preferences / Settings Store ──────────────────────────
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored preference."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: Any) -> None:
        """Persist a preference value."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )
            conn.commit()
