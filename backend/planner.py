import json
import re
from collections.abc import AsyncIterator

from backend import profile
from backend.config import CONTEXT_WINDOW, PLAN_MAX_TOKENS
from backend.llm import stream_chat
from backend.search import extract_search_queries

_PLAN_PROMPT = (
    "あなたは、ユーザーに回答する前に必要な情報をツールで集めるアシスタントです。\n"
    "次のユーザーの発言を読み、回答の前に実行すべきツール呼び出しの計画を立ててください。\n"
    "ユーザー自身の経歴・収入・年齢など個人的な文脈に依存する質問であれば、"
    "Web検索より先にretrieve_profile/retrieve_memoryで必要な個人情報を取得する計画にしてください。\n\n"
    "利用可能なツール:\n{tool_catalog}\n\n"
    "{search_mode_note}"
    "出力は次の形式のJSON配列のみとし、説明文は書かないでください。\n"
    "[{{\"name\": \"<ツール名>\", \"arguments\": {{<引数オブジェクト>}}}}, ...]\n"
    "ツールが不要なら空配列 [] を出力してください。\n\n"
    "ユーザーの発言: {message}\n"
    "出力:"
)

_SEARCH_MODE_NOTE = (
    "ユーザーは検索モードをONにしているため、計画には必ずweb_searchの呼び出しを1つ以上含めてください。\n\n"
)


def _build_tool_catalog(tool_list: list[dict]) -> str:
    lines = []
    for tool in tool_list:
        fn = tool["function"]
        params = ", ".join(fn.get("parameters", {}).get("properties", {}).keys())
        lines.append(f"- {fn['name']}({params}): {fn['description']}")
    return "\n".join(lines)


def _parse_plan(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    plan = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            plan.append({"name": item["name"], "arguments": item.get("arguments") or {}})
    return plan


async def build_plan(
    message: str,
    tool_list: list[dict],
    search_mode: bool,
    model: str,
    max_tokens: int = PLAN_MAX_TOKENS,
    num_ctx: int = CONTEXT_WINDOW,
) -> AsyncIterator[tuple[str, str | list]]:
    """ユーザー発言とツール一覧から実行計画(ツール名+引数のリスト)を生成する。
    (種別, データ)を順次yieldする。種別は'thinking'(データ:str)、最後に必ず'plan'(データ:list)"""
    valid_names = {t["function"]["name"] for t in tool_list}
    prompt = _PLAN_PROMPT.format(
        tool_catalog=_build_tool_catalog(tool_list),
        search_mode_note=_SEARCH_MODE_NOTE if search_mode else "",
        message=message,
    )

    raw = ""
    # 計画はJSON形式厳守が必須なため、創造性より指示への忠実さを優先してtemperatureを下げる
    async for kind, text in stream_chat(
        [{"role": "user", "content": prompt}], model=model, max_tokens=max_tokens, num_ctx=num_ctx, temperature=0.2
    ):
        if kind == "thinking":
            yield ("thinking", text)
        else:
            raw += text

    raw_plan = _parse_plan(raw)
    plan = []
    for step in raw_plan:
        name = step["name"]
        if name not in valid_names:
            # モデルがretrieve_profileの代わりにテーブル名(profile_basic等)をnameに
            # 書いてしまうことがあるため、SQLらしき引数が来ていればretrieve_profileとして救済する
            if name in profile.QUERY_TABLE_NAMES and "retrieve_profile" in valid_names:
                name = "retrieve_profile"
            else:
                continue
        plan.append({"name": name, "arguments": step["arguments"]})

    if search_mode and not any(step["name"] == "web_search" for step in plan):
        queries = await extract_search_queries(message)
        plan.extend({"name": "web_search", "arguments": {"query": q}} for q in queries)

    yield ("plan", plan)
