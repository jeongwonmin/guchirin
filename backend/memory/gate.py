import re

from backend.config import MEMORY_SIMILARITY_THRESHOLD, MEMORY_TOP_K
from backend.llm import chat_once
from backend.memory import store

_TRIVIAL_PATTERN = re.compile(
    r"^\s*(こんにちは|おはよう|こんばんは|やあ|hi|hello|hey|ありがとう|thanks|了解|ok|おつかれ)[!!。.\s]*$",
    re.IGNORECASE,
)

_GATE_PROMPT = (
    "ユーザー発言に答えるために、ユーザー自身に関する過去の情報"
    "（名前・好み・職業など、以前のやりとりで本人が話した内容）を"
    "参照する必要があるか判定してください。"
    "出力は YES か NO の1語のみにしてください。\n\n"
    "発言: 私の好きな食べ物は何でしたか？\n判定: YES\n\n"
    "発言: 私の名前を覚えてる？\n判定: YES\n\n"
    "発言: こんにちは\n判定: NO\n\n"
    "発言: 今日は何曜日？\n判定: NO\n\n"
    "発言: {message}\n判定:"
)


async def should_retrieve_memory(user_message: str) -> bool:
    if store.count() == 0:
        return False
    if _TRIVIAL_PATTERN.match(user_message):
        return False
    try:
        answer = await chat_once(
            [{"role": "user", "content": _GATE_PROMPT.format(message=user_message)}]
        )
    except Exception:
        return True
    return "yes" in answer.strip().lower()


def retrieve_relevant_memories(user_message: str) -> list[str]:
    candidates = store.find_similar(user_message, top_k=MEMORY_TOP_K)
    relevant = []
    for c in candidates:
        similarity = 1 - c["distance"]
        if similarity >= MEMORY_SIMILARITY_THRESHOLD:
            relevant.append(c["text"])
    return relevant
