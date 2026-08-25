from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VERSION: str = "0.1.0"
    ENV: str = "development"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5434
    POSTGRES_USER: str = "stats"
    POSTGRES_PASSWORD: str = "stats"
    POSTGRES_DB: str = "stats_app"

    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6380

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url(self) -> str:
        return self.postgres_url

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    model_config = {"env_prefix": "STATS_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
