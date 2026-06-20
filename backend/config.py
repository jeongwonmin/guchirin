from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CHROMA_DIR = DATA_DIR / "chroma"
CHAT_DB_PATH = DATA_DIR / "chat.db"

OLLAMA_HOST = "http://localhost:11434"
MAIN_MODEL = "qwen3:4b"
LIGHT_MODEL = "gemma3:1b"

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

MAX_MEMORY_ENTRIES = 1000
MEMORY_WARNING_RATIO = 0.9

MEMORY_TOP_K = 3
MEMORY_SIMILARITY_THRESHOLD = 0.5
MEMORY_MERGE_SIMILARITY_THRESHOLD = 0.85

SEARCH_RESULT_COUNT = 5
