"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MongoDB
    mongodb_uri: str = Field(default="mongodb://localhost:27017")
    mongodb_database: str = Field(default="job_application")

    # Apify
    apify_api_token: SecretStr = Field(default=SecretStr(""))
    apify_actor_id: str = Field(default="KfYqwOhOXqkqO4DF8")
    apify_base_url: str = Field(default="https://api.apify.com/v2")

    # OpenAI / LLM
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = Field(default="gpt-4o")
    openai_model_mini: str = Field(default="gpt-4o-mini")

    # Scraper settings
    scraper_search_url: str = Field(
        default="https://www.linkedin.com/jobs/search/?keywords=Security%20Engineer&location=Switzerland"
    )
    scraper_max_jobs: int = Field(default=100)
    scraper_interval_hours: int = Field(default=6)

    # Ranker settings
    ranker_min_score: int = Field(default=30)
    ranker_min_triggers: int = Field(default=2)

    # Generator settings
    generator_output_dir: str = Field(default="./output")

    # Paths
    profile_path: Path = Field(default=Path("config/profile.yaml"))
    templates_path: Path = Field(default=Path("config/templates.yaml"))

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
