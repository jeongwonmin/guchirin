import json
import re
from collections.abc import AsyncIterator

from backend import profile
from backend import tools as agent_tools
from backend.config import CONTEXT_WINDOW, MAX_AGENT_STEPS, PLAN_MAX_TOKENS
from backend.llm import stream_chat
from backend.search import extract_search_queries

_AGENT_STEP_PROMPT = (
    "あなたは、ユーザーに回答する前に必要な情報をツールで集めるエージェントです。\n"
    "これまでの実行結果を踏まえて、次に実行すべきツール呼び出しを1つだけ決めてください。\n"
    "もう十分な情報が集まっていれば、ツールを呼ばずに終了してください。\n\n"
    "利用可能なツール:\n{tool_catalog}\n\n"
    "{search_mode_note}"
    "ユーザー自身の経歴・収入・年齢など個人的な文脈に依存する質問であれば、"
    "Web検索より先にretrieve_profile/retrieve_memoryで必要な個人情報を取得してください。\n"
    "あるツールの実行結果(取得した社名・地名などの具体的な情報)を使って、"
    "次のツールの引数を決めても構いません"
    "(例: retrieve_profileで現在の勤務先を取得し、その社名でweb_searchする)。\n"
    "retrieve_profileがSQLエラーを返した場合は、エラー内容を踏まえて修正したSELECT文で"
    "再度retrieve_profileを呼び出してください。\n\n"
    "出力は次の形式のJSONオブジェクト1つのみとし、説明文は書かないでください。\n"
    'ツールを呼ぶ場合: {{"name": "<ツール名>", "arguments": {{<引数オブジェクト>}}}}\n'
    'もう十分な場合:    {{"name": "final"}}\n\n'
    "ユーザーの発言: {message}\n"
    "{history_block}"
    "出力:"
)

_SEARCH_MODE_NOTE = (
    "ユーザーは検索モードをONにしているため、最終的にはweb_searchの呼び出しを1つ以上含めてください。\n\n"
)


def _build_tool_catalog(tool_list: list[dict]) -> str:
    lines = []
    for tool in tool_list:
        fn = tool["function"]
        params = ", ".join(fn.get("parameters", {}).get("properties", {}).keys())
        lines.append(f"- {fn['name']}({params}): {fn['description']}")
    return "\n".join(lines)


def _format_history(executed: list[tuple[str, dict, str]]) -> str:
    if not executed:
        return ""
    lines = ["### これまでの実行結果"]
    for i, (name, arguments, result) in enumerate(executed, 1):
        arg_str = json.dumps(arguments, ensure_ascii=False)
        lines.append(f"[{i}] {name}({arg_str}) → {result}")
    return "\n".join(lines) + "\n\n"


def _parse_action(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("name"), str):
        return None
    return {"name": data["name"], "arguments": data.get("arguments") or {}}


async def run_agent(
    message: str,
    tool_list: list[dict],
    search_mode: bool,
    model: str,
    max_tokens: int = PLAN_MAX_TOKENS,
    num_ctx: int = CONTEXT_WINDOW,
    max_steps: int = MAX_AGENT_STEPS,
) -> AsyncIterator[tuple[str, str | tuple | list]]:
    """ユーザー発言とツール一覧から、1ステップずつ次のツール呼び出しを判断して実行するエージェントループ。
    各ステップは直前までの実行結果を見て次の引数を決められるため、SQLのリトライや
    「取得した情報を使って次のツールの引数を決める」ような逐次的な計画にも対応する。
    (種別, データ)を順次yieldする。種別は'thinking'(str)、'tool_start'((name, query))、
    最後に必ず'context'(list[str]: ツール実行結果のテキスト一覧)"""
    valid_names = {t["function"]["name"] for t in tool_list}
    catalog = _build_tool_catalog(tool_list)
    search_mode_note = _SEARCH_MODE_NOTE if search_mode else ""

    executed: list[tuple[str, dict, str]] = []
    seen: set[tuple[str, str]] = set()
    used_web_search = False

    for _ in range(max_steps):
        prompt = _AGENT_STEP_PROMPT.format(
            tool_catalog=catalog,
            search_mode_note=search_mode_note,
            message=message,
            history_block=_format_history(executed),
        )

        raw = ""
        # ステップ判断はJSON形式厳守が必須なため、創造性より指示への忠実さを優先してtemperatureを下げる
        async for kind, text in stream_chat(
            [{"role": "user", "content": prompt}], model=model, max_tokens=max_tokens, num_ctx=num_ctx,
            temperature=0.2,
        ):
            if kind == "thinking":
                yield ("thinking", text)
            else:
                raw += text

        action = _parse_action(raw)
        if action is None or action["name"] == "final":
            break

        name = action["name"]
        if name not in valid_names:
            # モデルがretrieve_profileの代わりにテーブル名(profile_basic等)をnameに
            # 書いてしまうことがあるため、SQLらしき引数が来ていればretrieve_profileとして救済する
            if name in profile.QUERY_TABLE_NAMES and "retrieve_profile" in valid_names:
                name = "retrieve_profile"
            else:
                break

        arguments = action["arguments"]
        key = (name, json.dumps(arguments, sort_keys=True, ensure_ascii=False))
        if key in seen:
            # 同じ呼び出しを繰り返しているだけなら、終了判断ができていないとみなして止める
            break
        seen.add(key)

        yield ("tool_start", (name, arguments.get("query", "")))
        result = agent_tools.execute_tool(name, arguments)
        executed.append((name, arguments, result))
        if name == "web_search":
            used_web_search = True

    if search_mode and not used_web_search:
        queries = await extract_search_queries(message)
        for q in queries:
            yield ("tool_start", ("web_search", q))
            result = agent_tools.execute_tool("web_search", {"query": q})
            executed.append(("web_search", {"query": q}, result))

    tool_results = [f"[{name}の実行結果]\n{result}" for name, _, result in executed]
    yield ("context", tool_results)
