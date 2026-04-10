from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Smarthub API"
    app_version: str = "1.1.0"
    debug: bool = False

    # Database
    database_url: str

    # Security
    secret_key: str

    # CORS — Qt tourne en local, overlay aussi
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "app://.",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
