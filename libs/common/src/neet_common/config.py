"""Typed settings loaded from the environment (.env).

Pass a Settings instance explicitly; no module-level singletons.
"""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root (libs/common/src/neet_common/config.py -> four levels up). Used to find .env and
# data/ regardless of the current directory.
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    postgres_host: str = "localhost"
    postgres_host_port: int = 5432
    postgres_db: str = "neet"
    neet_reader_password: SecretStr = SecretStr("")
    neet_ingest_password: SecretStr = SecretStr("")

    # Any OpenAI-compatible endpoint: Ollama (Mac) or vLLM (GPU box).
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: SecretStr = SecretStr("not-needed")
    llm_model: str = ""
    embed_model: str = ""
    embed_dim: int = 1024

    # Service URLs (services talk over HTTP; they never import each other). 127.0.0.1 only.
    retrieval_url: str = "http://127.0.0.1:8001"
    answer_url: str = "http://127.0.0.1:8002"
    llm_timeout_s: float = 120.0
