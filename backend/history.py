import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from backend.config import CHAT_DB_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    conn = sqlite3.connect(CHAT_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )"""
        )


def create_session(title: str = "新しいチャット") -> dict:
    session_id = str(uuid.uuid4())
    created_at = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
            (session_id, title, created_at),
        )
    return {"id": session_id, "title": title, "created_at": created_at}


def list_sessions() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at FROM sessions ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_session_messages(session_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages "
            "WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_message(session_id: str, role: str, content: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), session_id, role, content, _now()),
        )


def delete_session(session_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def maybe_set_title(session_id: str, first_user_message: str) -> None:
    """セッションのタイトルが初期値のままなら、最初のユーザー発言から自動設定する"""
    title = first_user_message.strip()[:30] or "新しいチャット"
    with _connect() as conn:
        row = conn.execute(
            "SELECT title FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row and row["title"] == "新しいチャット":
            conn.execute(
                "UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)
            )
