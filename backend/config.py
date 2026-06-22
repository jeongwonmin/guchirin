from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CHROMA_DIR = DATA_DIR / "chroma"
CHAT_DB_PATH = DATA_DIR / "chat.db"

OLLAMA_HOST = "http://localhost:11434"
MAIN_MODEL = "gemma4:e2b"
LIGHT_MODEL = "gemma3:1b"
EXTRACT_MODEL = "gemma4:e2b"

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

MAX_MEMORY_ENTRIES = 1000
MEMORY_WARNING_RATIO = 0.9

MEMORY_TOP_K = 3
MEMORY_SIMILARITY_THRESHOLD = 0.5
MEMORY_MERGE_SIMILARITY_THRESHOLD = 0.85

SEARCH_RESULT_COUNT = 5

# コンテキストエンジニアリング: Ollamaのnum_ctxはデフォルト4096のままだと
# 履歴+ツール結果+thinkingの長い出力であっという間に消費されるため明示的に広げる
CONTEXT_WINDOW = 16384
# 1ターンの生成量の上限(num_predict)。最終回答が冗長になりすぎてコンテキストを圧迫しないようにする
ANSWER_MAX_TOKENS = 1200
# thinkingモデルは計画立案の説明だけでも数百トークン使うため、JSON出力前に予算切れにならない余裕を持たせる
PLAN_MAX_TOKENS = 1500
LIGHT_TASK_MAX_TOKENS = 300
IMPORT_MAX_TOKENS = 4096
# 会話履歴は直近何件まで毎ターンLLMに渡すか(古いターンを無制限に積み上げない)
MAX_HISTORY_MESSAGES = 20
# エージェントループ(1ステップずつツールを判断→実行)が無限に続かないようにする上限
MAX_AGENT_STEPS = 4

ANSWER_STYLE_PROMPT = (
    "回答は要点を絞り、必要十分な長さで簡潔に答えてください。"
    "過剰な見出し・箇条書き・表・絵文字の多用は避け、自然な文章を基本としてください。"
)
