import asyncio
import json

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import history, planner, profile, settings as app_settings, tools as agent_tools
from backend.config import BASE_DIR, MAIN_MODEL
from backend.llm import list_models, pull_model, stream_chat
from backend.memory import extractor, store

app = FastAPI(title="Local LLM Chat")

history.init_db()
profile.init_db()
app_settings.init_db()

TOOL_STATUS_LABELS = {
    "web_search": "Web検索中",
    "retrieve_memory": "記憶を検索中",
    "retrieve_profile": "プロフィールを確認中",
}


def _status_chunk(text: str) -> str:
    return json.dumps({"type": "status", "text": text}, ensure_ascii=False) + "\n"


def _content_chunk(text: str) -> str:
    return json.dumps({"type": "content", "text": text}, ensure_ascii=False) + "\n"


def _thinking_chunk(text: str) -> str:
    return json.dumps({"type": "thinking", "text": text}, ensure_ascii=False) + "\n"


def _tool_call_chunk(name: str, detail) -> str:
    return json.dumps({"type": "tool_call", "name": name, "detail": detail}, ensure_ascii=False) + "\n"


class ChatRequest(BaseModel):
    session_id: str
    message: str
    search_mode: bool = False
    model: str = ""


class SessionCreate(BaseModel):
    title: str = "新しいチャット"


@app.post("/chat")
async def chat(req: ChatRequest):
    history.maybe_set_title(req.session_id, req.message)
    history.add_message(req.session_id, "user", req.message)

    cfg = app_settings.get_settings()
    # 古いターンを無制限に積み上げない(コンテキストエンジニアリング): 直近のみをLLMに渡す
    past_messages = history.get_session_messages(req.session_id)[-cfg["max_history_messages"]:]
    messages = [{"role": "system", "content": cfg["answer_style_prompt"]}]
    messages += [{"role": m["role"], "content": m["content"]} for m in past_messages]
    chat_model = req.model or MAIN_MODEL

    async def event_stream():
        full_response = ""
        try:
            # ツール呼び出しは事前に1回だけ計画(プランニング)し、計画通りに順次実行してから回答する。
            # 個人情報(プロフィール/記憶)に依存する質問は、計画上Web検索より先に取得されるようにする
            tool_list = agent_tools.available_tools()
            plan = []
            async for kind, data in planner.build_plan(
                req.message,
                tool_list,
                req.search_mode,
                chat_model,
                max_tokens=cfg["plan_max_tokens"],
                num_ctx=cfg["context_window"],
            ):
                if kind == "thinking":
                    yield _thinking_chunk(data)
                elif kind == "plan":
                    plan = data

            # "tool"ロールのメッセージはOllamaのモデルによってはチャットテンプレートが対応しておらず
            # 黙って無視される(例: gemma4)ため、実行結果は通常のuserメッセージとして埋め込む
            tool_results = []
            for step in plan:
                name = step["name"]
                arguments = step["arguments"]
                yield _status_chunk(TOOL_STATUS_LABELS.get(name, f"{name} 実行中"))
                yield _tool_call_chunk(name, arguments.get("query", ""))
                result = agent_tools.execute_tool(name, arguments)
                tool_results.append(f"[{name}の実行結果]\n{result}")
            if tool_results:
                messages.append({"role": "user", "content": "\n\n".join(tool_results)})

            async for kind, text in stream_chat(
                messages, model=chat_model, max_tokens=cfg["answer_max_tokens"], num_ctx=cfg["context_window"]
            ):
                if kind == "thinking":
                    yield _thinking_chunk(text)
                else:
                    full_response += text
                    yield _content_chunk(text)
        except httpx.HTTPStatusError as e:
            yield _content_chunk(f"\n[エラー] モデル呼び出しに失敗しました: {e}")
        finally:
            # 途中で停止(クライアント切断)されても、それまでの応答は保存する
            if full_response:
                history.add_message(req.session_id, "assistant", full_response)
                asyncio.create_task(extractor.extract_and_store(req.message, full_response))

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.get("/models")
async def get_models():
    return {"models": await list_models(), "default": MAIN_MODEL}


@app.get("/settings")
def get_settings_endpoint():
    return {**app_settings.get_settings(), "_bounds": app_settings.get_bounds()}


class SettingsUpdate(BaseModel):
    context_window: int | None = None
    answer_max_tokens: int | None = None
    plan_max_tokens: int | None = None
    light_task_max_tokens: int | None = None
    import_max_tokens: int | None = None
    max_history_messages: int | None = None
    answer_style_prompt: str | None = None


@app.put("/settings")
def put_settings_endpoint(req: SettingsUpdate):
    partial = {k: v for k, v in req.model_dump().items() if v is not None}
    return app_settings.update_settings(partial)


@app.post("/settings/reset")
def post_settings_reset():
    return app_settings.reset_settings()


class ModelPull(BaseModel):
    model: str


@app.post("/models/pull")
async def post_models_pull(req: ModelPull):
    model = req.model.strip()
    if not model:
        raise HTTPException(status_code=400, detail="model is required")

    async def event_stream():
        try:
            async for chunk in pull_model(model):
                if chunk.get("error"):
                    yield json.dumps({"type": "error", "text": chunk["error"]}, ensure_ascii=False) + "\n"
                    return
                yield json.dumps(
                    {
                        "type": "progress",
                        "status": chunk.get("status", ""),
                        "total": chunk.get("total"),
                        "completed": chunk.get("completed"),
                    },
                    ensure_ascii=False,
                ) + "\n"
        except httpx.HTTPStatusError as e:
            yield json.dumps({"type": "error", "text": str(e)}, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


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


@app.get("/profile/basic")
def get_basic_info():
    return profile.get_basic_info()


class ProfileBasicUpdate(BaseModel):
    name: str = ""
    birth_date: str = ""
    current_company: str = ""
    current_position: str = ""
    current_salary: str = ""
    gender: str = ""
    religion: str = ""
    sexual_orientation: str = ""
    race: str = ""
    hometown: str = ""
    residence_country: str = ""
    nationality: str = ""


@app.put("/profile/basic")
def put_basic_info(req: ProfileBasicUpdate):
    return profile.set_basic_info(req.model_dump())


class CareerEntry(BaseModel):
    company: str = ""
    position: str = ""
    start_date: str = ""
    end_date: str = ""
    salary: str = ""
    reason_for_joining: str = ""
    reason_for_leaving: str = ""
    note: str = ""


@app.get("/profile/career")
def get_career():
    return profile.list_career()


@app.post("/profile/career")
def post_career(req: CareerEntry):
    return profile.add_career(req.model_dump())


@app.put("/profile/career/{entry_id}")
def put_career(entry_id: str, req: CareerEntry):
    updated = profile.update_career(entry_id, req.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="career entry not found")
    return updated


@app.delete("/profile/career/{entry_id}")
def delete_career(entry_id: str):
    profile.delete_career(entry_id)
    return {"ok": True}


class CareerMove(BaseModel):
    direction: str


@app.post("/profile/career/{entry_id}/move")
def move_career(entry_id: str, req: CareerMove):
    profile.move_career(entry_id, req.direction)
    return profile.list_career()


class EducationEntry(BaseModel):
    degree: str = ""
    field: str = ""
    school: str = ""
    graduated_year: str = ""
    note: str = ""


@app.get("/profile/education")
def get_education():
    return profile.list_education()


@app.post("/profile/education")
def post_education(req: EducationEntry):
    return profile.add_education(req.model_dump())


@app.put("/profile/education/{entry_id}")
def put_education(entry_id: str, req: EducationEntry):
    updated = profile.update_education(entry_id, req.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="education entry not found")
    return updated


@app.delete("/profile/education/{entry_id}")
def delete_education(entry_id: str):
    profile.delete_education(entry_id)
    return {"ok": True}


class ResidenceEntry(BaseModel):
    place: str = ""
    period: str = ""
    note: str = ""


@app.get("/profile/residence")
def get_residence():
    return profile.list_residence()


@app.post("/profile/residence")
def post_residence(req: ResidenceEntry):
    return profile.add_residence(req.model_dump())


@app.put("/profile/residence/{entry_id}")
def put_residence(entry_id: str, req: ResidenceEntry):
    updated = profile.update_residence(entry_id, req.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="residence entry not found")
    return updated


@app.delete("/profile/residence/{entry_id}")
def delete_residence(entry_id: str):
    profile.delete_residence(entry_id)
    return {"ok": True}


class ProfileImport(BaseModel):
    text: str


@app.post("/profile/import")
async def post_profile_import(req: ProfileImport):
    return await profile.import_profile_text(req.text)


@app.post("/profile/import/file")
async def post_profile_import_file(file: UploadFile = File(...)):
    data = await file.read()
    try:
        text = profile.extract_text_from_file(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not text.strip():
        raise HTTPException(status_code=400, detail="ファイルからテキストを抽出できませんでした")
    return await profile.import_profile_text(text)


app.mount("/", StaticFiles(directory=str(BASE_DIR / "frontend"), html=True), name="frontend")
