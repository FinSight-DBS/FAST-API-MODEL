from pydantic_settings import BaseSettings
from pydantic import computed_field


class Settings(BaseSettings):
    APP_ENV: str = "development"
    PORT: int = 8000

    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    AUTOENCODER_MODEL_PATH: str
    KMEANS_MODEL_PATH: str
    KMEANS_LABEL_MAP_PATH: str
    NLP_MODEL_PATH: str
    NLP_TOKENIZER_PATH: str

    ANOMALY_THRESHOLD_DEFAULT: float = 0.05
    ANOMALY_MIN_TRANSACTION_COUNT: int = 15
    ANOMALY_LOOKBACK_DAYS: int = 90

    LLM_API_URL: str
    LLM_API_KEY: str
    LLM_MODEL: str = "gpt-4o-mini"

    COLD_START_THRESHOLD_DAYS: int = 30

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
