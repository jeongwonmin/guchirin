import json
import re

from backend.config import MEMORY_MERGE_SIMILARITY_THRESHOLD
from backend.llm import chat_once
from backend.memory import store

_EXTRACT_PROMPT = (
    "次の会話に、ユーザーに関する新しい事実（名前・職業・好み・設定など）が"
    "含まれていれば、それぞれ短い日本語の文としてJSON配列で出力してください。"
    "会話文の引用や要約ではなく、事実そのものだけを書いてください。"
    "新しい事実が無ければ [] とだけ出力してください。"
    "説明文は一切書かず、JSON配列のみを出力してください。\n\n"
    "例:\n"
    "会話:\n"
    "ユーザー: 私の名前は田中です。猫が好きです。\n"
    "アシスタント: 田中さん、こんにちは！\n"
    "出力: [\"ユーザーの名前は田中\", \"ユーザーは猫が好き\"]\n\n"
    "会話:\n"
    "ユーザー: 今日は寒いね。\n"
    "アシスタント: そうですね、暖かくしてくださいね。\n"
    "出力: []\n\n"
    "会話:\n"
    "ユーザー: {user_message}\n"
    "アシスタント: {assistant_message}\n"
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


async def extract_and_store(user_message: str, assistant_message: str) -> None:
    """直近のやりとりから記憶すべき事実を抽出し、既存メモリとマージ/追加する"""
    try:
        raw = await chat_once(
            [
                {
                    "role": "user",
                    "content": _EXTRACT_PROMPT.format(
                        user_message=user_message, assistant_message=assistant_message
                    ),
                }
            ]
        )
    except Exception:
        return

    facts = _parse_json_array(raw)
    for fact in facts:
        similar = store.find_similar(fact, top_k=1)
        if similar and (1 - similar[0]["distance"]) >= MEMORY_MERGE_SIMILARITY_THRESHOLD:
            store.update_text(similar[0]["id"], fact)
        else:
            store.add(fact, source="auto")
