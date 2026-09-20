"""Configuracao centralizada e tipada (12-factor: config via ambiente)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Todas as configuracoes lidas de variaveis de ambiente / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM ---
    openai_api_key: str = ""
    openai_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    route_temperature: float = 0.0
    answer_temperature: float = 0.3
    llm_max_retries: int = 2

    # --- RAG ---
    embed_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    collection_name: str = "sentinela_docs"
    retrieval_k: int = 4
    chunk_chars: int = 900
    chunk_overlap: int = 120

    # --- Camada de dados ---
    sql_max_rows: int = 500

    # --- Execucao ---
    log_level: str = "INFO"

    # Override da raiz do projeto para instalacoes fora do repositorio (ex.: Docker).
    # Não definido, resolve a partir do local do pacote (repo local/editable install).
    base_dir: Path | None = None

    @property
    def project_root(self) -> Path:
        return self.base_dir or Path(__file__).resolve().parent.parent.parent

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def docs_dir(self) -> Path:
        return self.project_root / "docs"

    @property
    def chroma_dir(self) -> Path:
        return self.project_root / "chroma_db"

    @property
    def db_path(self) -> Path:
        return self.project_root / "soc.duckdb"


@lru_cache
def get_settings() -> Settings:
    return Settings()
