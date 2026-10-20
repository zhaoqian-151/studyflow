from pydantic_settings import BaseSettings, SettingsConfigDict

VECTOR_DIMENSIONS = 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "StudyFlow"
    database_url: str = "postgresql+psycopg://studyflow@127.0.0.1:5433/studyflow"
    postgres_password: str = ""
    cookie_secure: bool = False
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4.1-mini"
    ai_daily_request_limit: int = 50
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"


settings = Settings()
