"""Hito 1: Core Foundation — Pydantic Settings for environment configuration."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Configuración de IdeaHub desde variables de entorno o .env.local."""

    telegram_bot_token: str = ""
    telegram_allowed_user_id: str = ""
    telegram_bot_token_enabled: bool = True

    api_host: str = "0.0.0.0"
    api_port: int = 8090

    sqlite_path: str = "data/index.sqlite"
    data_dir: str = "data"

    # MCP / API
    api_token: str = ""

    # Web
    web_password: str = ""
    web_auth_secret: str = ""

    # AI
    ai_base_url: str = "https://api.groq.com/openai/v1"
    ai_api_key: str = ""

    # Bot polling control
    disable_bot_polling: bool = False

    class Config:
        env_file = ".env.local"
        env_file_encoding = "utf-8"
        extra = "ignore"
