from collections.abc import AsyncIterator

import httpx

from backend.config import LIGHT_MODEL, MAIN_MODEL, OLLAMA_HOST

# Ollamaでtool calling(function calling)に対応していることが確認されているモデルファミリーのプレフィックス
# 会話用モデルはtools付きでchat_with_toolsを呼ぶため、未対応モデルを選ぶと400エラーになる
TOOL_CAPABLE_PREFIXES = (
    "llama3.1",
    "llama3.2",
    "llama3.3",
    "llama4",
    "qwen2.5",
    "qwen3",
    "gemma4",
    "devstral",
    "mistral-nemo",
    "mistral-small",
    "mistral-large",
    "firefunction-v2",
    "command-r",
    "hermes3",
)


def is_tool_capable(model_name: str) -> bool:
    """モデル名(タグ含む)がtool calling対応ファミリーかどうかを判定する"""
    base = model_name.split(":")[0].lower()
    return base.startswith(TOOL_CAPABLE_PREFIXES)


async def stream_chat(messages: list[dict], model: str = MAIN_MODEL) -> AsyncIterator[tuple[str, str]]:
    """Ollama /api/chat をストリーミング呼び出しし、(種別, テキスト)を順次yieldする。種別は'thinking'または'content'"""
    payload = {"model": model, "messages": messages, "stream": True}
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


async def chat_with_tools(
    messages: list[dict], tools: list[dict], model: str = MAIN_MODEL
) -> AsyncIterator[tuple[str, str | list]]:
    """tools付きでOllama /api/chat をストリーミング呼び出しし、(種別, データ)を順次yieldする。
    種別は'thinking'/'content'(データ:str)、または'tool_calls'(データ:list)"""
    payload = {"model": model, "messages": messages, "tools": tools, "stream": True}
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
                tool_calls = message.get("tool_calls")
                if tool_calls:
                    yield ("tool_calls", tool_calls)
                if chunk.get("done"):
                    break


async def chat_once(messages: list[dict], model: str = LIGHT_MODEL) -> str:
    """軽量LLM用: ストリーミングせず完全な応答テキストを一度に返す（分類・抽出タスク向け）"""
    payload = {"model": model, "messages": messages, "stream": False}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip()


async def list_models() -> list[str]:
    """Ollamaにインストールされているtool calling対応モデル名一覧を返す（会話用モデル選択UI向け）"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{OLLAMA_HOST}/api/tags")
        resp.raise_for_status()
        names = [m["name"] for m in resp.json().get("models", [])]
        return [n for n in names if is_tool_capable(n)]


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
