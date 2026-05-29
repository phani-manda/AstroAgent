import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
MAX_TOKENS = 500
TEMPERATURE = 0.7
JUDGE_TEMPERATURE = 0.0
MAX_TOOL_ITERATIONS = 4
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "astroagent.db")
ALLOWED_ORIGINS = ["*"]
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
