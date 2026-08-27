"""
backend/app/config.py
─────────────────────
Single source of truth for all environment-variable reads.
Every other module imports from here — no module reads os.environ directly.
"""
import os
from dotenv import load_dotenv

load_dotenv(override=False)  # won't overwrite values already in the environment


# ── RAG ──────────────────────────────────────────────────────────────────────
USE_MOCK_RAG: bool = os.getenv("USE_MOCK_RAG", "true").lower() == "true"

# ── LLM ──────────────────────────────────────────────────────────────────────
USE_MOCK_LLM: bool = os.getenv("USE_MOCK_LLM", "true").lower() == "true"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

# ── GRAPH ─────────────────────────────────────────────────────────────────────
USE_MOCK_GRAPH: bool = os.getenv("USE_MOCK_GRAPH", "false").lower() == "true"

# ── DATABASE ─────────────────────────────────────────────────────────────────
DATABASE_URL: str | None = os.getenv("DATABASE_URL")

# ── CROSS-EXAMINATION ─────────────────────────────────────────────────────────
MAX_CROSS_EXAM_ROUNDS: int = int(os.getenv("MAX_CROSS_EXAM_ROUNDS", "3"))
CROSS_EXAM_CONVERGENCE_THRESHOLD: float = float(
    os.getenv("CROSS_EXAM_CONVERGENCE_THRESHOLD", "0.02")
)

# ── JUDGE ─────────────────────────────────────────────────────────────────────
DEFAULT_JUDGE_PROFILE: str = os.getenv("DEFAULT_JUDGE_PROFILE", "balanced")
