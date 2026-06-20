import uuid
from datetime import datetime, timezone

import chromadb
from chromadb.utils import embedding_functions

from backend.config import CHROMA_DIR, EMBEDDING_MODEL, MAX_MEMORY_ENTRIES, MEMORY_WARNING_RATIO

_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
_collection = _client.get_or_create_collection(
    name="user_memory",
    embedding_function=_embedding_fn,
    metadata={"hnsw:space": "cosine"},
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def count() -> int:
    return _collection.count()


def status() -> dict:
    n = count()
    return {
        "count": n,
        "max_entries": MAX_MEMORY_ENTRIES,
        "warning": n >= MAX_MEMORY_ENTRIES * MEMORY_WARNING_RATIO,
        "full": n >= MAX_MEMORY_ENTRIES,
    }


def list_all() -> list[dict]:
    data = _collection.get()
    items = []
    for i, doc_id in enumerate(data["ids"]):
        meta = data["metadatas"][i] or {}
        items.append(
            {
                "id": doc_id,
                "text": data["documents"][i],
                "source": meta.get("source", "manual"),
                "created_at": meta.get("created_at"),
                "updated_at": meta.get("updated_at"),
            }
        )
    items.sort(key=lambda x: x["updated_at"] or "", reverse=True)
    return items


def delete(memory_id: str) -> None:
    _collection.delete(ids=[memory_id])


def add(text: str, source: str = "manual") -> dict | None:
    """新規メモリを追加する。容量が満杯の場合は追加せずNoneを返す（更新のみ許可）"""
    if status()["full"]:
        return None
    memory_id = str(uuid.uuid4())
    now = _now()
    _collection.add(
        ids=[memory_id],
        documents=[text],
        metadatas=[{"source": source, "created_at": now, "updated_at": now}],
    )
    return {"id": memory_id, "text": text, "source": source, "created_at": now, "updated_at": now}


def update_text(memory_id: str, text: str) -> None:
    existing = _collection.get(ids=[memory_id])
    meta = (existing["metadatas"] or [{}])[0] or {}
    meta["updated_at"] = _now()
    _collection.update(ids=[memory_id], documents=[text], metadatas=[meta])


def find_similar(text: str, top_k: int = 1) -> list[dict]:
    """類似メモリを検索する。距離(distance)が小さいほど類似度が高い"""
    if count() == 0:
        return []
    result = _collection.query(query_texts=[text], n_results=min(top_k, count()))
    items = []
    for i, doc_id in enumerate(result["ids"][0]):
        items.append(
            {
                "id": doc_id,
                "text": result["documents"][0][i],
                "distance": result["distances"][0][i],
            }
        )
    return items
