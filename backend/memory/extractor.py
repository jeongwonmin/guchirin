import json
import re

from backend.config import EXTRACT_MODEL, MEMORY_MERGE_SIMILARITY_THRESHOLD
from backend.llm import chat_once
from backend.memory import store
from backend.settings import get_settings

# 具体例(few-shot)を入れるとその例の内容自体が事実として誤抽出されやすいため、
# 例は出さずに出力フォーマットをプレースホルダーで示す。
# 抽出品質を優先してEXTRACT_MODEL(MAIN_MODELより上位のローカルモデル)を使う（非同期タスクなので速度は重視しない）
_EXTRACT_PROMPT = (
    "次の会話から、ユーザー本人について今後も変わらず使える事実だけを抽出してください。\n"
    "対象: 氏名・年齢・職業・居住地・家族構成・恒常的な好み/嫌い・確定した設定や予定など。\n"
    "対象外: 一時的な感情や状態（疲れた、寒い等）、相手への質問、推測や不確かな情報、"
    "あいさつ・相づちのみの発言、抽象的すぎる感想。\n"
    "確信が持てない場合や、当てはまる事実が無い場合は出力しないでください。\n"
    "各事実は短い日本語の一文とし、会話文の引用や要約ではなく事実そのものを書いてください。\n"
    "出力は下記の会話に基づくJSON配列のみとし、例や他の会話の内容は含めないでください。"
    "説明文は一切書かないでください。\n\n"
    "出力フォーマット: [\"<事実1>\", \"<事実2>\", ...] または、事実が無ければ []\n\n"
    "会話:\n"
    "ユーザー: {user_message}\n"
    "アシスタント: {assistant_message}\n"
    "出力:"
)

_MIN_FACT_LENGTH = 4
_MAX_FACT_LENGTH = 100


def _parse_json_array(text: str) -> list[str]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [str(item).strip() for item in data if str(item).strip()]


def _is_plausible_fact(fact: str) -> bool:
    """抽出ノイズ(短すぎ/長すぎ/疑問文/会話の引用っぽい文)を除外する"""
    if not (_MIN_FACT_LENGTH <= len(fact) <= _MAX_FACT_LENGTH):
        return False
    if fact.endswith(("?", "？")):
        return False
    if fact.startswith(("ユーザー:", "アシスタント:", "ユーザー：", "アシスタント：")):
        return False
    return True


async def extract_and_store(user_message: str, assistant_message: str) -> None:
    """直近のやりとりから記憶すべき事実を抽出し、既存メモリとマージ/追加する"""
    try:
        cfg = get_settings()
        raw = await chat_once(
            [
                {
                    "role": "user",
                    "content": _EXTRACT_PROMPT.format(
                        user_message=user_message, assistant_message=assistant_message
                    ),
                }
            ],
            model=EXTRACT_MODEL,
            max_tokens=cfg["light_task_max_tokens"],
            num_ctx=cfg["context_window"],
        )
    except Exception:
        return

    facts = [f for f in _parse_json_array(raw) if _is_plausible_fact(f)]
    for fact in facts:
        similar = store.find_similar(fact, top_k=1)
        if similar and (1 - similar[0]["distance"]) >= MEMORY_MERGE_SIMILARITY_THRESHOLD:
            store.update_text(similar[0]["id"], fact)
        else:
            store.add(fact, source="auto")
