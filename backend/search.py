import json
import re

from ddgs import DDGS

from backend.config import SEARCH_RESULT_COUNT
from backend.llm import chat_once
from backend.settings import get_settings

_EXTRACT_QUERY_PROMPT = (
    "次のユーザーの発言を読み、Web検索で調べるべき検索キーワードを"
    "1〜10個、JSON配列で出力してください。"
    "社名やサービス名、団体名、地名などの固有名詞にも注目してほしい"
    "調べたい対象が複数あるなら、それぞれ別のキーワードに分けること。"
    "発言そのものの言い回しや余分な言葉（「教えて」「について」など）は含めず、"
    "検索に使う語句のみにしてください。説明文は書かず、JSON配列のみを出力してください。\n\n"
    "例:\n"
    "発言: 東京と大阪の今日の天気を教えて\n"
    "出力: [\"東京 天気 今日\", \"大阪 天気 今日\"]\n\n"
    "発言: {message}\n"
    "出力:"
)


def _parse_json_array(text: str) -> list[str]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [str(item).strip() for item in data if str(item).strip()]


async def extract_search_queries(message: str) -> list[str]:
    """ユーザーの発言からWeb検索すべきキーワードを1〜3個抽出する。失敗時は発言そのものを1件返す"""
    try:
        cfg = get_settings()
        raw = await chat_once(
            [{"role": "user", "content": _EXTRACT_QUERY_PROMPT.format(message=message)}],
            max_tokens=cfg["light_task_max_tokens"],
            num_ctx=cfg["context_window"],
        )
    except Exception:
        return [message]
    queries = _parse_json_array(raw)
    return queries[:3] if queries else [message]


def web_search(query: str, max_results: int = SEARCH_RESULT_COUNT) -> list[dict]:
    """DuckDuckGoで検索し、title/body/href のリストを返す。失敗時は空リスト"""
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            return list(results)
    except Exception:
        return []


def format_search_results(results: list[dict]) -> str:
    if not results:
        return ""
    lines = ["以下はWeb検索結果です。必要に応じて参考にして回答してください:\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        body = r.get("body", "")
        href = r.get("href", "")
        lines.append(f"[{i}] {title}\n{body}\n出典: {href}\n")
    return "\n".join(lines)
