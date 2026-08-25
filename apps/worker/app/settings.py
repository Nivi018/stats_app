from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VERSION: str = "0.1.0"
    ENV: str = "development"

    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6380

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    model_config = {"env_prefix": "STATS_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
