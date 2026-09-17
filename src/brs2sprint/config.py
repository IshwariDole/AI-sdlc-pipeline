"""Runtime configuration. Reads a .env file if present, then os.environ."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    # "mock" runs the whole pipeline offline with no API key and no network.
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")   # mock | anthropic | openai | groq | gemini
    llm_model: str = os.getenv("LLM_MODEL", "")             # blank -> provider's own default below
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4000"))
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    # phase 2
    research_enabled: bool = os.getenv("RESEARCH_ENABLED", "false").lower() == "true"
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")

    # phase 1 chunking
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "3500"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "300"))

    # phase 8
    team_velocity: int = int(os.getenv("TEAM_VELOCITY", "20"))
    max_sprints: int = int(os.getenv("MAX_SPRINTS", "12"))

    db_path: str = os.getenv("DB_PATH", str(ROOT / "outputs" / "brs2sprint.db"))
    output_dir: str = os.getenv("OUTPUT_DIR", str(ROOT / "outputs"))

    def ensure_dirs(self) -> None:
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)


settings = Settings()
