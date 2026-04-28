from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - compatibility for pydantic v1 environments
    from pydantic import BaseSettings

    SettingsConfigDict = None


if SettingsConfigDict is not None:
    class Settings(BaseSettings):
        app_name: str = "Company QA System"
        app_env: str = "dev"
        app_host: str = "127.0.0.1"
        app_port: int = 8000

        openai_api_key: str = ""
        openai_base_url: str = ""

        embedding_model: str = "text-embedding-3-small"
        chat_model: str = "gpt-4o-mini"

        rag_engine: str = "auto"
        rag_chunk_size: int = 800
        rag_chunk_overlap: int = 120
        rag_top_k: int = 4
        rag_vector_index_path: str = "data/vector_store/index.json"
        rag_llamaindex_persist_dir: str = "data/vector_store/llamaindex"
        auth_db_path: str = "data/auth.db"
        auth_session_cookie_name: str = "company_qa_session"
        auth_session_secret: str = "change-me-in-production"
        auth_session_ttl_hours: int = 12
        auth_cookie_secure: bool = False
        auth_login_max_attempts: int = 5
        auth_lock_minutes: int = 15
        auth_init_admin_enabled: bool = True
        auth_init_admin_username: str = "admin"
        auth_init_admin_password: str = "ChangeMe123!"
        auth_init_admin_display_name: str = "System Admin"
        auth_init_admin_reset_password: bool = False

        model_config = SettingsConfigDict(env_file=(Path(__file__).parent.parent.parent / ".env").resolve(), env_file_encoding="utf-8", extra="ignore")

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
        def llamaindex_persist_dir(self) -> Path:
            path = Path(self.rag_llamaindex_persist_dir)
            if path.is_absolute():
                return path
            return (self.project_root / path).resolve()

        @property
        def auth_db_file(self) -> Path:
            path = Path(self.auth_db_path)
            if path.is_absolute():
                return path
            return (self.project_root / path).resolve()

        @property
        def docs_dir(self) -> Path:
            return (self.project_root / "data/docs").resolve()
else:
    class Settings(BaseSettings):
        app_name: str = "Company QA System"
        app_env: str = "dev"
        app_host: str = "127.0.0.1"
        app_port: int = 8000

        openai_api_key: str = ""
        openai_base_url: str = ""

        embedding_model: str = "text-embedding-3-small"
        chat_model: str = "gpt-4o-mini"

        rag_engine: str = "auto"
        rag_chunk_size: int = 800
        rag_chunk_overlap: int = 120
        rag_top_k: int = 4
        rag_vector_index_path: str = "data/vector_store/index.json"
        rag_llamaindex_persist_dir: str = "data/vector_store/llamaindex"
        auth_db_path: str = "data/auth.db"
        auth_session_cookie_name: str = "company_qa_session"
        auth_session_secret: str = "change-me-in-production"
        auth_session_ttl_hours: int = 12
        auth_cookie_secure: bool = False
        auth_login_max_attempts: int = 5
        auth_lock_minutes: int = 15
        auth_init_admin_enabled: bool = True
        auth_init_admin_username: str = "admin"
        auth_init_admin_password: str = "ChangeMe123!"
        auth_init_admin_display_name: str = "System Admin"
        auth_init_admin_reset_password: bool = False

        class Config:
            env_file = str((Path(__file__).parent.parent.parent / ".env").resolve())
            env_file_encoding = "utf-8"
            extra = "ignore"

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
        def llamaindex_persist_dir(self) -> Path:
            path = Path(self.rag_llamaindex_persist_dir)
            if path.is_absolute():
                return path
            return (self.project_root / path).resolve()

        @property
        def auth_db_file(self) -> Path:
            path = Path(self.auth_db_path)
            if path.is_absolute():
                return path
            return (self.project_root / path).resolve()

        @property
        def docs_dir(self) -> Path:
            return (self.project_root / "data/docs").resolve()


settings = Settings()
