from collections.abc import AsyncIterator

import httpx

from backend.config import ANSWER_MAX_TOKENS, CONTEXT_WINDOW, LIGHT_MODEL, LIGHT_TASK_MAX_TOKENS, MAIN_MODEL, OLLAMA_HOST


async def stream_chat(
    messages: list[dict],
    model: str = MAIN_MODEL,
    max_tokens: int = ANSWER_MAX_TOKENS,
    num_ctx: int = CONTEXT_WINDOW,
    temperature: float = 0.7,
) -> AsyncIterator[tuple[str, str]]:
    """Ollama /api/chat をストリーミング呼び出しし、(種別, テキスト)を順次yieldする。種別は'thinking'または'content'。
    num_ctxを明示してデフォルト(4096)による早期のコンテキスト消耗を避け、num_predictで出力の暴走を防ぐ。
    JSON/SQLなど形式厳守の出力を求める呼び出しでは、低めのtemperatureを明示して指示無視を減らすこと"""
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"num_ctx": num_ctx, "num_predict": max_tokens, "temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", f"{OLLAMA_HOST}/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                chunk = httpx.Response(200, content=line).json()
                message = chunk.get("message", {})
                thinking = message.get("thinking", "")
                if thinking:
                    yield ("thinking", thinking)
                content = message.get("content", "")
                if content:
                    yield ("content", content)
                if chunk.get("done"):
                    break


async def chat_once(
    messages: list[dict],
    model: str = LIGHT_MODEL,
    max_tokens: int = LIGHT_TASK_MAX_TOKENS,
    think: bool = False,
    num_ctx: int = CONTEXT_WINDOW,
    temperature: float = 0.2,
) -> str:
    """軽量LLM用: ストリーミングせず完全な応答テキストを一度に返す（分類・抽出タスク向け）。
    結果はUIに出さないため、デフォルトでthinkingを無効化して生成量を抑える。
    分類/抽出はフォーマット厳守が重要なため、デフォルトのtemperatureを低めにしている"""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        "options": {"num_ctx": num_ctx, "num_predict": max_tokens, "temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip()


async def list_models() -> list[str]:
    """Ollamaにインストールされているモデル名一覧を返す（会話用モデル選択UI向け）。
    プランニング方式はプロンプトベースのJSON生成のためtool calling対応の有無を問わない"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{OLLAMA_HOST}/api/tags")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]


async def pull_model(model: str) -> AsyncIterator[dict]:
    """Ollama /api/pull をストリーミング呼び出しし、ダウンロード進捗を順次yieldする"""
    payload = {"model": model, "stream": True}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", f"{OLLAMA_HOST}/api/pull", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                yield httpx.Response(200, content=line).json()
