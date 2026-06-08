from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_DIR = Path(__file__).resolve().parents[2]
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ENV_FILES = (
    _BACKEND_DIR / ".env",
    _ROOT_DIR / ".env",
)


class Settings(BaseSettings):
    app_name: str = "SciNova OS"
    database_url: str = "postgresql://scinova:scinova@localhost:5432/scinova"
    sqlite_fallback: bool = False
    environment: str = "development"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = ""
    celery_result_backend: str = ""
    use_celery: bool = True
    secret_key: str = "scinova-dev-secret-change-in-production"
    upload_dir: str = "./storage/uploads"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ncbi_email: str = ""
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "scinova12"
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_persist_dir: str = "./storage/chroma"
    chroma_use_http: bool = False
    chunk_size: int = 512
    chunk_overlap: int = 64
    # Embeddings: auto | openai | bedrock (auto prefers OpenAI when configured, else Bedrock)
    embedding_provider: str = "auto"
    embedding_model: str = "text-embedding-3-small"
    aws_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    bedrock_embedding_model: str = "amazon.titan-embed-text-v2:0"
    llm_model: str = "gpt-4o-mini"
    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai/v1"
    slm_model: str = "ministral-8b-latest"
    slm_json_mode: bool = True
    neo4j_enabled: bool = True
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    quota_max_uploads: int = 2
    quota_max_workflows: int = 2
    lims_api_url: str = ""
    lims_api_key: str = ""
    vina_bin: str = ""
    vina_receptor_pdbqt: str = ""
    vina_center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    vina_size: tuple[float, float, float] = (20.0, 20.0, 20.0)

    model_config = SettingsConfigDict(
        env_file=[str(p) for p in _ENV_FILES if p.exists()],
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
