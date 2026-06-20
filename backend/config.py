from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CHROMA_DIR = DATA_DIR / "chroma"
CHAT_DB_PATH = DATA_DIR / "chat.db"

OLLAMA_HOST = "http://localhost:11434"
MAIN_MODEL = "gemma3:4b-it-qat"
LIGHT_MODEL = "gemma3:1b"

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

MAX_MEMORY_ENTRIES = 1000
MEMORY_WARNING_RATIO = 0.9

MEMORY_TOP_K = 3
MEMORY_SIMILARITY_THRESHOLD = 0.5
MEMORY_MERGE_SIMILARITY_THRESHOLD = 0.85

SEARCH_TRIGGER_KEYWORDS = [
    "検索", "ググ", "調べて", "調べる", "search", "最新", "ニュース",
    "今日の", "現在の", "公式サイト", "url", "サイト教えて",
]
SEARCH_RESULT_COUNT = 5
