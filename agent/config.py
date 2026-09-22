import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
# Used by evals/ only; the agent never calls it.
JUDGE_MODEL = os.getenv("GEMINI_JUDGE_MODEL", "gemini-3.1-pro-preview")
MAX_OUTPUT_TOKENS = 4096
MAX_STEPS = 8  # cap on model calls per user turn (guards runaway tool loops)
REQUEST_TIMEOUT_MS = 60_000
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v2")  # "v1" = original baseline prompt, "v2" = fixed

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
