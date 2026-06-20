from backend.config import MEMORY_SIMILARITY_THRESHOLD, MEMORY_TOP_K
from backend.memory import store


def retrieve_relevant_memories(user_message: str) -> list[str]:
    candidates = store.find_similar(user_message, top_k=MEMORY_TOP_K)
    relevant = []
    for c in candidates:
        similarity = 1 - c["distance"]
        if similarity >= MEMORY_SIMILARITY_THRESHOLD:
            relevant.append(c["text"])
    return relevant
