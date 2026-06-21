import sqlite3
from contextlib import contextmanager

from backend.config import (
    ANSWER_MAX_TOKENS,
    ANSWER_STYLE_PROMPT,
    CHAT_DB_PATH,
    CONTEXT_WINDOW,
    IMPORT_MAX_TOKENS,
    LIGHT_TASK_MAX_TOKENS,
    MAX_HISTORY_MESSAGES,
    PLAN_MAX_TOKENS,
)

DEFAULTS = {
    "context_window": CONTEXT_WINDOW,
    "answer_max_tokens": ANSWER_MAX_TOKENS,
    "plan_max_tokens": PLAN_MAX_TOKENS,
    "light_task_max_tokens": LIGHT_TASK_MAX_TOKENS,
    "import_max_tokens": IMPORT_MAX_TOKENS,
    "max_history_messages": MAX_HISTORY_MESSAGES,
    "answer_style_prompt": ANSWER_STYLE_PROMPT,
}

# 値が大きすぎるとVRAM不足や生成の暴走/ハングに繋がるため、画面からの調整値には上限を必ず設ける
_INT_BOUNDS = {
    "context_window": (1024, 32768),
    "answer_max_tokens": (64, 4096),
    "plan_max_tokens": (64, 2048),
    "light_task_max_tokens": (32, 2048),
    "import_max_tokens": (256, 8192),
    "max_history_messages": (2, 200),
}
_STYLE_PROMPT_MAX_LENGTH = 2000


def get_bounds() -> dict:
    """画面側で入力のmin/maxを示すための上限・下限一覧を返す"""
    return {k: list(v) for k, v in _INT_BOUNDS.items()}


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
            """CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )"""
        )


def _clamp(key: str, value: int) -> int:
    lo, hi = _INT_BOUNDS[key]
    return max(lo, min(hi, value))


def get_settings() -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    overrides = {r["key"]: r["value"] for r in rows}
    result = dict(DEFAULTS)
    for key, value in overrides.items():
        if key not in DEFAULTS:
            continue
        if key in _INT_BOUNDS:
            result[key] = _clamp(key, int(value))
        else:
            result[key] = value[:_STYLE_PROMPT_MAX_LENGTH]
    return result


def update_settings(partial: dict) -> dict:
    with _connect() as conn:
        for key, value in partial.items():
            if key not in DEFAULTS:
                continue
            if key in _INT_BOUNDS:
                stored = str(_clamp(key, int(value)))
            else:
                stored = str(value)[:_STYLE_PROMPT_MAX_LENGTH]
            conn.execute(
                """INSERT INTO app_settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (key, stored),
            )
    return get_settings()


def reset_settings() -> dict:
    with _connect() as conn:
        conn.execute("DELETE FROM app_settings")
    return get_settings()
