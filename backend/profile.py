import io
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import docx
from pypdf import PdfReader

from backend.config import CHAT_DB_PATH, MAIN_MODEL
from backend.llm import chat_once
from backend.settings import get_settings


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


def _ensure_column(conn, table: str, column: str, col_type: str = "TEXT") -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS career_history (
                id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                position TEXT,
                start_date TEXT,
                end_date TEXT,
                salary TEXT,
                reason_for_joining TEXT,
                reason_for_leaving TEXT,
                note TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS education_history (
                id TEXT PRIMARY KEY,
                degree TEXT,
                field TEXT,
                school TEXT,
                graduated_year TEXT,
                note TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS profile_basic (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS residence_history (
                id TEXT PRIMARY KEY,
                place TEXT,
                period TEXT,
                note TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        _ensure_column(conn, "career_history", "note")
        _ensure_column(conn, "education_history", "note")
        _ensure_column(conn, "career_history", "sort_order", "INTEGER")
        _backfill_career_sort_order(conn)


def _backfill_career_sort_order(conn) -> None:
    rows = conn.execute(
        "SELECT id FROM career_history WHERE sort_order IS NULL ORDER BY created_at ASC"
    ).fetchall()
    if not rows:
        return
    next_order = (conn.execute("SELECT MAX(sort_order) AS m FROM career_history").fetchone()["m"] or 0) + 1
    for row in rows:
        conn.execute("UPDATE career_history SET sort_order = ? WHERE id = ?", (next_order, row["id"]))
        next_order += 1


def _next_career_sort_order(conn) -> int:
    return (conn.execute("SELECT MAX(sort_order) AS m FROM career_history").fetchone()["m"] or 0) + 1


BASIC_INFO_KEYS = [
    "name", "birth_date", "current_company", "current_position", "current_salary",
    "gender", "religion", "sexual_orientation", "race", "hometown",
    "residence_country", "nationality",
]


def get_basic_info() -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM profile_basic").fetchall()
        return {r["key"]: r["value"] for r in rows}


def set_basic_info(data: dict) -> dict:
    now = _now()
    with _connect() as conn:
        for key, value in data.items():
            if key not in BASIC_INFO_KEYS or not str(value).strip():
                continue
            conn.execute(
                """INSERT INTO profile_basic (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
                (key, value, now),
            )
    return get_basic_info()


def list_career() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM career_history ORDER BY sort_order DESC, created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def move_career(entry_id: str, direction: str) -> None:
    """現在の表示順の中でentry_idを一つ上/下に動かす(direction: 'up' または 'down')"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, sort_order FROM career_history ORDER BY sort_order DESC, created_at DESC"
        ).fetchall()
        ids = [r["id"] for r in rows]
        orders = [r["sort_order"] for r in rows]
        if entry_id not in ids:
            return
        idx = ids.index(entry_id)
        swap_idx = idx - 1 if direction == "up" else idx + 1
        if swap_idx < 0 or swap_idx >= len(ids):
            return
        conn.execute("UPDATE career_history SET sort_order = ? WHERE id = ?", (orders[swap_idx], entry_id))
        conn.execute("UPDATE career_history SET sort_order = ? WHERE id = ?", (orders[idx], ids[swap_idx]))


def add_career(entry: dict) -> dict:
    record = {
        "id": str(uuid.uuid4()),
        "company": entry.get("company", ""),
        "position": entry.get("position", ""),
        "start_date": entry.get("start_date", ""),
        "end_date": entry.get("end_date", ""),
        "salary": entry.get("salary", ""),
        "reason_for_joining": entry.get("reason_for_joining", ""),
        "reason_for_leaving": entry.get("reason_for_leaving", ""),
        "note": entry.get("note", ""),
        "created_at": _now(),
    }
    with _connect() as conn:
        record["sort_order"] = _next_career_sort_order(conn)
        conn.execute(
            """INSERT INTO career_history
            (id, company, position, start_date, end_date, salary, reason_for_joining, reason_for_leaving, note,
             sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record["id"], record["company"], record["position"], record["start_date"],
                record["end_date"], record["salary"], record["reason_for_joining"],
                record["reason_for_leaving"], record["note"], record["sort_order"], record["created_at"],
            ),
        )
    return record


CAREER_FIELDS = [
    "company", "position", "start_date", "end_date", "salary",
    "reason_for_joining", "reason_for_leaving", "note",
]


def update_career(entry_id: str, entry: dict) -> dict | None:
    fields = {k: v for k, v in entry.items() if k in CAREER_FIELDS}
    if not fields:
        return None
    with _connect() as conn:
        conn.execute(
            f"UPDATE career_history SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
            (*fields.values(), entry_id),
        )
        row = conn.execute("SELECT * FROM career_history WHERE id = ?", (entry_id,)).fetchone()
        return dict(row) if row else None


def delete_career(entry_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM career_history WHERE id = ?", (entry_id,))


def list_education() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM education_history ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def add_education(entry: dict) -> dict:
    record = {
        "id": str(uuid.uuid4()),
        "degree": entry.get("degree", ""),
        "field": entry.get("field", ""),
        "school": entry.get("school", ""),
        "graduated_year": entry.get("graduated_year", ""),
        "note": entry.get("note", ""),
        "created_at": _now(),
    }
    with _connect() as conn:
        conn.execute(
            """INSERT INTO education_history (id, degree, field, school, graduated_year, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (record["id"], record["degree"], record["field"], record["school"],
             record["graduated_year"], record["note"], record["created_at"]),
        )
    return record


EDUCATION_FIELDS = ["degree", "field", "school", "graduated_year", "note"]


def update_education(entry_id: str, entry: dict) -> dict | None:
    fields = {k: v for k, v in entry.items() if k in EDUCATION_FIELDS}
    if not fields:
        return None
    with _connect() as conn:
        conn.execute(
            f"UPDATE education_history SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
            (*fields.values(), entry_id),
        )
        row = conn.execute("SELECT * FROM education_history WHERE id = ?", (entry_id,)).fetchone()
        return dict(row) if row else None


def delete_education(entry_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM education_history WHERE id = ?", (entry_id,))


def list_residence() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM residence_history ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def add_residence(entry: dict) -> dict:
    record = {
        "id": str(uuid.uuid4()),
        "place": entry.get("place", ""),
        "period": entry.get("period", ""),
        "note": entry.get("note", ""),
        "created_at": _now(),
    }
    with _connect() as conn:
        conn.execute(
            """INSERT INTO residence_history (id, place, period, note, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (record["id"], record["place"], record["period"], record["note"], record["created_at"]),
        )
    return record


RESIDENCE_FIELDS = ["place", "period", "note"]


def update_residence(entry_id: str, entry: dict) -> dict | None:
    fields = {k: v for k, v in entry.items() if k in RESIDENCE_FIELDS}
    if not fields:
        return None
    with _connect() as conn:
        conn.execute(
            f"UPDATE residence_history SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
            (*fields.values(), entry_id),
        )
        row = conn.execute("SELECT * FROM residence_history WHERE id = ?", (entry_id,)).fetchone()
        return dict(row) if row else None


def delete_residence(entry_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM residence_history WHERE id = ?", (entry_id,))


_IMPORT_PROMPT = (
    "次のテキストは職務経歴書またはLinkedInのプロフィールです。"
    "そこから読み取れる基本情報・職歴・学歴を、以下の形式のJSONオブジェクトとして出力してください。\n"
    "{{\n"
    '  "basic": {{"name": "氏名", "birth_date": "生年月日(あれば)",'
    ' "current_company": "現在の勤務先", "current_position": "現在の職位",'
    ' "current_salary": "現在の年収(記載があれば)"}},\n'
    '  "career": [\n'
    '    {{"company": "会社名", "position": "職位", "start_date": "YYYY-MM", "end_date": "YYYY-MM または 現在なら空文字",'
    ' "salary": "年収などの記載があれば", "reason_for_joining": "入社理由の記載があれば",'
    ' "reason_for_leaving": "退職理由の記載があれば", "note": "その他補足があれば自由記述"}}\n'
    "  ],\n"
    '  "education": [\n'
    '    {{"degree": "学士/修士/博士など", "field": "専攻", "school": "学校名", "graduated_year": "YYYY",'
    ' "note": "その他補足があれば自由記述"}}\n'
    "  ]\n"
    "}}\n"
    "記載が無い項目は空文字にしてください。説明文は書かず、JSONオブジェクトのみを出力してください。\n\n"
    "テキスト:\n{text}\n\n"
    "出力:"
)


def _parse_json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def extract_text_from_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_docx(data: bytes) -> str:
    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


def extract_text_from_file(filename: str, data: bytes) -> str:
    """ファイル名の拡張子からPDF/DOCXを判別してテキストを抽出する"""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(data)
    if lower.endswith(".docx"):
        return extract_text_from_docx(data)
    raise ValueError(f"対応していないファイル形式です: {filename}")


async def import_profile_text(text: str) -> dict:
    """職務経歴書/LinkedInテキストから基本情報・職歴・学歴を抽出し、DBに保存する"""
    cfg = get_settings()
    raw = await chat_once(
        [{"role": "user", "content": _IMPORT_PROMPT.format(text=text)}],
        model=MAIN_MODEL,
        max_tokens=cfg["import_max_tokens"],
        num_ctx=cfg["context_window"],
    )
    parsed = _parse_json_object(raw)

    basic = parsed.get("basic", {})
    if isinstance(basic, dict):
        set_basic_info(basic)

    created_career = [add_career(entry) for entry in parsed.get("career", []) if isinstance(entry, dict)]
    created_education = [
        add_education(entry) for entry in parsed.get("education", []) if isinstance(entry, dict)
    ]
    return {"basic": get_basic_info(), "career": created_career, "education": created_education}


PROFILE_SCHEMA_DESCRIPTION = (
    "テーブル一覧:\n"
    "- profile_basic(key, value, updated_at): 基本情報。1行1項目のkey-value形式であり、"
    "name や birth_date 自体はカラムではなくkey列に入る値である点に注意。"
    "keyに入るのは次のいずれか: " + ", ".join(BASIC_INFO_KEYS) + "\n"
    "  例: SELECT value FROM profile_basic WHERE key = 'name'\n"
    "- career_history(id, company, position, start_date, end_date, salary, "
    "reason_for_joining, reason_for_leaving, note, sort_order, created_at): 職歴。1行1社。\n"
    "- education_history(id, degree, field, school, graduated_year, note, created_at): 学歴。1行1校。\n"
    "- residence_history(id, place, period, note, created_at): 居住歴。1行1拠点。\n"
    "複数のテーブルから取得したい場合は、1つのSELECT文にまとめようとせず、"
    "';'で区切って複数のSELECT文を並べること(各テーブルにつき1文)。\n"
    "  例: SELECT value FROM profile_basic WHERE key = 'name'; SELECT * FROM career_history\n"
)

QUERY_TABLE_NAMES = {"profile_basic", "career_history", "education_history", "residence_history"}


def _validate_select(statement: str) -> str:
    statement = statement.strip()
    if not re.match(r"(?is)^select\b", statement):
        raise ValueError("SELECT文のみ実行できます")
    referenced = {m.lower() for m in re.findall(r"(?i)\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", statement)}
    if not referenced or not referenced.issubset(QUERY_TABLE_NAMES):
        raise ValueError(f"参照できるテーブルは {', '.join(sorted(QUERY_TABLE_NAMES))} のみです")
    return statement


def run_profile_query(sql: str) -> list[dict]:
    """LLMが生成したSELECT文を検証して実行する。複数テーブルから取得したい場合は';'区切りで
    複数のSELECT文を渡せる(各文はSELECT文かつ許可テーブルのみ参照可能であること)。結果は全文の行を結合して返す"""
    statements = [_validate_select(s) for s in sql.split(";") if s.strip()]
    if not statements:
        raise ValueError("SELECT文を1つ以上指定してください")
    rows = []
    with _connect() as conn:
        for statement in statements:
            try:
                rows.extend(dict(r) for r in conn.execute(statement).fetchall())
            except sqlite3.Error as e:
                raise ValueError(str(e)) from e
    return rows


def format_profile_summary() -> str:
    """チャットのtool callingから呼び出す用: 基本情報・職歴・学歴・居住歴を読みやすいテキストにまとめる"""
    basic = get_basic_info()
    career = list_career()
    education = list_education()
    residence = list_residence()

    if not basic and not career and not education and not residence:
        return ""

    lines = []
    if basic:
        lines.append("[基本情報]")
        for key, value in basic.items():
            lines.append(f"{key}: {value}")
    if residence:
        lines.append("[居住歴]")
        for r in residence:
            lines.append(f"- {r['place']} ({r['period']})" + (f" 補足: {r['note']}" if r.get("note") else ""))
    if career:
        lines.append("[職歴]")
        for c in career:
            period = f"{c['start_date']}〜{c['end_date'] or '現在'}"
            lines.append(
                f"- {c['company']} / {c['position']} ({period}) "
                f"収入: {c['salary'] or '不明'} "
                f"入社理由: {c['reason_for_joining'] or '不明'} "
                f"退職理由: {c['reason_for_leaving'] or '不明'}"
                + (f" 補足: {c['note']}" if c.get("note") else "")
            )
    if education:
        lines.append("[学歴]")
        for e in education:
            lines.append(
                f"- {e['school']} {e['field']} {e['degree']} ({e['graduated_year']}卒)"
                + (f" 補足: {e['note']}" if e.get("note") else "")
            )
    return "\n".join(lines)
