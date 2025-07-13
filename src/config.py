"""
Configuration management for the German Learning Bot
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Telegram Bot Configuration
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_webhook_url: str | None = Field(None, env="TELEGRAM_WEBHOOK_URL")
    allowed_users: str = Field(default="", env="ALLOWED_USERS")

    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=1000, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(
        default=1.0, env="OPENAI_TEMPERATURE"
    )  # GPT-4 only supports 1.0

    # Database Configuration
    database_url: str = Field(default="sqlite:///data/bot.db", env="DATABASE_URL")
    database_backup_enabled: bool = Field(default=True, env="DATABASE_BACKUP_ENABLED")
    database_backup_interval: int = Field(default=24, env="DATABASE_BACKUP_INTERVAL")

    # Application Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    debug: bool = Field(default=False, env="DEBUG")
    polling_interval: float = Field(default=1.0, env="POLLING_INTERVAL")
    max_workers: int = Field(default=4, env="MAX_WORKERS")

    # Rate Limiting
    max_words_per_request: int = Field(default=50, env="MAX_WORDS_PER_REQUEST")
    max_words_per_day: int = Field(default=100, env="MAX_WORDS_PER_DAY")
    max_openai_requests_per_day: int = Field(
        default=200, env="MAX_OPENAI_REQUESTS_PER_DAY"
    )
    api_timeout: int = Field(default=60, env="API_TIMEOUT")

    # Spaced Repetition Configuration
    default_cards_per_session: int = Field(default=10, env="DEFAULT_CARDS_PER_SESSION")
    default_easiness_factor: float = Field(default=2.5, env="DEFAULT_EASINESS_FACTOR")
    min_easiness_factor: float = Field(default=1.3, env="MIN_EASINESS_FACTOR")
    max_easiness_factor: float = Field(default=3.0, env="MAX_EASINESS_FACTOR")

    # Reminder Configuration
    reminder_enabled: bool = Field(default=True, env="REMINDER_ENABLED")
    default_reminder_time: str = Field(default="09:00", env="DEFAULT_REMINDER_TIME")
    timezone: str = Field(default="UTC", env="TIMEZONE")

    @property
    def allowed_users_list(self) -> list[int]:
        """Convert allowed_users string to list of integers"""
        if not self.allowed_users.strip():
            return []
        # Parse comma-separated string of user IDs
        return [
            int(user_id.strip())
            for user_id in self.allowed_users.split(",")
            if user_id.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def get_database_path() -> str:
    """Get the database file path from URL"""
    settings = get_settings()
    if settings.database_url.startswith("sqlite:///"):
        return settings.database_url.replace("sqlite:///", "")
    return "data/bot.db"
