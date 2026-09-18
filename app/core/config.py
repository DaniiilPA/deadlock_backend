from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Приложение
    APP_NAME: str = "Auth Service"
    DEBUG: bool = False

    # JWT
    JWT_SECRET_KEY: str = "super-secret-key-change-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 900

    # Refresh Token & Cookies
    REFRESH_TOKEN_EXPIRE_SECONDS: int = 2592000
    COOKIE_NAME: str = "refresh_token"
    COOKIE_PATH: str = "/api/auth"
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "strict"

    # База данных
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/auth_db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()