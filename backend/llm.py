from collections.abc import AsyncIterator

import httpx

from backend.config import LIGHT_MODEL, MAIN_MODEL, OLLAMA_HOST


async def stream_chat(messages: list[dict], model: str = MAIN_MODEL) -> AsyncIterator[str]:
    """Ollama /api/chat をストリーミング呼び出しし、応答テキストの断片を順次yieldする"""
    payload = {"model": model, "messages": messages, "stream": True}
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", f"{OLLAMA_HOST}/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                chunk = httpx.Response(200, content=line).json()
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
                if chunk.get("done"):
                    break


async def chat_with_tools(messages: list[dict], tools: list[dict], model: str = MAIN_MODEL) -> dict:
    """tools付きでOllama /api/chat を一度呼び出し、応答メッセージ（content/tool_calls）を返す"""
    payload = {"model": model, "messages": messages, "tools": tools, "stream": False}
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {})


async def chat_once(messages: list[dict], model: str = LIGHT_MODEL) -> str:
    """軽量LLM用: ストリーミングせず完全な応答テキストを一度に返す（分類・抽出タスク向け）"""
    payload = {"model": model, "messages": messages, "stream": False}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip()
