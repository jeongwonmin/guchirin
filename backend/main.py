from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import history
from backend.config import BASE_DIR
from backend.llm import stream_chat
from backend.memory import extractor, gate, store
from backend.search import format_search_results, should_search, web_search

app = FastAPI(title="Local LLM Chat")

history.init_db()


class ChatRequest(BaseModel):
    session_id: str
    message: str
    search_mode: bool = False


class SessionCreate(BaseModel):
    title: str = "新しいチャット"


@app.post("/chat")
async def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    history.maybe_set_title(req.session_id, req.message)
    history.add_message(req.session_id, "user", req.message)

    system_parts = []

    if should_search(req.message, req.search_mode):
        results = web_search(req.message)
        formatted = format_search_results(results)
        if formatted:
            system_parts.append(formatted)

    if await gate.should_retrieve_memory(req.message):
        memories = gate.retrieve_relevant_memories(req.message)
        if memories:
            system_parts.append(
                "以下はユーザーに関する過去の記憶です。関連する場合のみ参考にしてください:\n"
                + "\n".join(f"- {m}" for m in memories)
            )

    past_messages = history.get_session_messages(req.session_id)
    messages = []
    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})
    for m in past_messages:
        messages.append({"role": m["role"], "content": m["content"]})

    async def event_stream():
        full_response = ""
        async for chunk in stream_chat(messages):
            full_response += chunk
            yield chunk
        history.add_message(req.session_id, "assistant", full_response)
        background_tasks.add_task(extractor.extract_and_store, req.message, full_response)

    return StreamingResponse(event_stream(), media_type="text/plain")


@app.get("/sessions")
def get_sessions():
    return history.list_sessions()


@app.post("/sessions")
def post_session(req: SessionCreate):
    return history.create_session(req.title)


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    return history.get_session_messages(session_id)


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    history.delete_session(session_id)
    return {"ok": True}


@app.get("/memory")
def get_memory():
    return store.list_all()


@app.get("/memory/status")
def get_memory_status():
    return store.status()


@app.delete("/memory/{memory_id}")
def delete_memory(memory_id: str):
    store.delete(memory_id)
    return {"ok": True}


class MemoryCreate(BaseModel):
    text: str


@app.post("/memory")
def post_memory(req: MemoryCreate):
    created = store.add(req.text, source="manual")
    if created is None:
        raise HTTPException(status_code=409, detail="Memory capacity is full")
    return created


app.mount("/", StaticFiles(directory=str(BASE_DIR / "frontend"), html=True), name="frontend")
