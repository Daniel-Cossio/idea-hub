"""Hito 1: Core Foundation — Pydantic Settings for environment configuration."""

from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Configuración de IdeaHub desde variables de entorno o archivos .env / .env.local."""

    telegram_bot_token: str = Field("", validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "telegram_bot_token"))
    telegram_allowed_user_id: str = Field("", validation_alias=AliasChoices("TELEGRAM_ALLOWED_USER_ID", "telegram_allowed_user_id"))
    telegram_bot_token_enabled: bool = True

    api_host: str = Field("0.0.0.0", validation_alias=AliasChoices("API_HOST", "api_host"))
    api_port: int = Field(8090, validation_alias=AliasChoices("API_PORT", "api_port"))

    sqlite_path: str = Field("data/index.sqlite", validation_alias=AliasChoices("SQLITE_PATH", "sqlite_path"))
    data_dir: str = Field("data", validation_alias=AliasChoices("DATA_DIR", "data_dir"))

    # MCP / API
    api_token: str = Field("", validation_alias=AliasChoices("IDEAHUB_API_TOKEN", "API_TOKEN", "api_token"))

    # Web
    web_password: str = Field("", validation_alias=AliasChoices("IDEAHUB_WEB_PASSWORD", "WEB_PASSWORD", "web_password"))
    web_auth_secret: str = Field("", validation_alias=AliasChoices("WEB_AUTH_SECRET", "web_auth_secret"))

    # AI
    ai_base_url: str = Field("https://api.groq.com/openai/v1", validation_alias=AliasChoices("AI_BASE_URL", "ai_base_url"))
    ai_api_key: str = Field("", validation_alias=AliasChoices("AI_API_KEY", "ai_api_key"))

    # Bot polling control
    disable_bot_polling: bool = Field(False, validation_alias=AliasChoices("DISABLE_BOT_POLLING", "disable_bot_polling"))

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
