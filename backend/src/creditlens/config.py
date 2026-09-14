from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    app_env: str = "development"
    app_version: str = "dev"
    demo_password: str = "creditlens-demo"
    secret_key: str = "change-me-in-production"
    database_path: str = "data/creditlens.db"
    qdrant_url: str = "http://127.0.0.1:6333"
    observability: str = "local"

    llm_base_url: str = "https://routerai.ru/api/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-4o-mini"
    llm_embedding_model: str = "openai/text-embedding-3-large"

    max_agent_steps: int = 12
    agent_timeout_sec: int = 60
    max_output_tokens: int = 1200

    analyze_rate_limit: int = 10
    chat_rate_limit: int = 30

    @property
    def db_path(self) -> Path:
        path = Path(self.database_path)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)


def get_settings() -> Settings:
    return Settings()
