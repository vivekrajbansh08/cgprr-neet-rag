"""Typed settings loaded from the environment (.env).

Pass a Settings instance explicitly; no module-level singletons.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
