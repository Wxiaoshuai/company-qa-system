from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Company QA System"
    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    openai_api_key: str = ""
    openai_base_url: str = ""

    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"

    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_top_k: int = 4
    rag_vector_index_path: str = "data/vector_store/index.json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def vector_index_path(self) -> Path:
        path = Path(self.rag_vector_index_path)
        if path.is_absolute():
            return path
        return (self.project_root / path).resolve()

    @property
    def docs_dir(self) -> Path:
        return (self.project_root / "data/docs").resolve()


settings = Settings()
