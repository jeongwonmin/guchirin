import re

from ddgs import DDGS

from backend.config import SEARCH_RESULT_COUNT, SEARCH_TRIGGER_KEYWORDS

_KEYWORD_PATTERN = re.compile("|".join(re.escape(k) for k in SEARCH_TRIGGER_KEYWORDS), re.IGNORECASE)


def should_search(user_message: str, search_mode: bool) -> bool:
    """検索モードが明示ONか、発言に検索トリガーキーワードが含まれる場合にTrue"""
    if search_mode:
        return True
    return bool(_KEYWORD_PATTERN.search(user_message))


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
