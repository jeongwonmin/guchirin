from backend import profile
from backend.memory import gate, store
from backend.search import format_search_results, web_search

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Web検索を行い最新情報を取得する。"
            "最新ニュース、現在の情報、URLなど、LLM自身の知識にない情報が必要な場合に使う。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ"},
            },
            "required": ["query"],
        },
    },
}

RETRIEVE_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "retrieve_memory",
        "description": (
            "ユーザー自身に関する過去の記憶（名前・好み・職業など、"
            "以前のやりとりで本人が話した内容）を検索する。"
            "ユーザーの過去の発言を参照する必要がある場合に使う。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索したい内容"},
            },
            "required": ["query"],
        },
    },
}


RETRIEVE_PROFILE_TOOL = {
    "type": "function",
    "function": {
        "name": "retrieve_profile",
        "description": (
            "ユーザーの構造化されたデータ（基本情報・職歴・学歴・居住歴）をSQLのSELECT文で取得する。"
            "氏名・生年月日・現在の勤務先・職位・収入、職歴（在籍期間・職位・収入・転職理由）、学歴、"
            "居住歴の話題が出たときに使う。\n\n"
            + profile.PROFILE_SCHEMA_DESCRIPTION
            + "\nqueryには上記テーブルに対するSELECT文を書くこと。複数テーブルが必要な場合は';'区切りで複数文書ける。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "実行したいSELECT文。複数テーブルが必要な場合は';'区切りで複数書ける",
                },
            },
            "required": ["query"],
        },
    },
}


def available_tools() -> list[dict]:
    """会話開始時点で呼び出し可能なツールの一覧を返す。記憶/プロフィールが無ければ対応ツールは含めない"""
    tools = [WEB_SEARCH_TOOL]
    if store.count() > 0:
        tools.append(RETRIEVE_MEMORY_TOOL)
    if profile.format_profile_summary():
        tools.append(RETRIEVE_PROFILE_TOOL)
    return tools


def execute_tool(name: str, arguments: dict) -> str:
    """LLMが要求したツール呼び出しを実行し、結果を文字列で返す"""
    if name == "web_search":
        results = web_search(arguments.get("query", ""))
        return format_search_results(results) or "検索結果が見つかりませんでした。"
    if name == "retrieve_memory":
        memories = gate.retrieve_relevant_memories(arguments.get("query", ""))
        if not memories:
            return "関連する記憶は見つかりませんでした。"
        return "\n".join(f"- {m}" for m in memories)
    if name == "retrieve_profile":
        query = arguments.get("query", "")
        try:
            rows = profile.run_profile_query(query)
        except ValueError as e:
            return f"SQLエラー: {e}"
        if not rows:
            return "該当する情報は見つかりませんでした。"
        return "\n".join(", ".join(f"{k}: {v}" for k, v in row.items()) for row in rows)
    return f"不明なツール: {name}"
