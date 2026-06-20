from ddgs import DDGS

from backend.config import SEARCH_RESULT_COUNT
from backend.llm import chat_once

_EXTRACT_QUERY_PROMPT = (
    "次のユーザーの発言から、Web検索で調べるべき内容だけを"
    "短い検索キーワードとして1行で出力してください。"
    "発言そのものの言い回しや余分な言葉（「教えて」「について」など）は含めず、"
    "検索に使う語句のみを出力してください。説明は不要です。\n\n"
    "発言: {message}\n"
    "検索キーワード:"
)


async def extract_search_query(message: str) -> str:
    """ユーザーの発言からWeb検索すべき内容を抽出する。失敗時は発言そのものを返す"""
    try:
        query = await chat_once([{"role": "user", "content": _EXTRACT_QUERY_PROMPT.format(message=message)}])
    except Exception:
        return message
    return query.strip().strip('"').strip("「」") or message


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
