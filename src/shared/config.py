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

    # Supabase
    supabase_url: str = Field(default="http://localhost:8000")
    supabase_anon_key: SecretStr = Field(default=SecretStr(""))
    supabase_service_key: SecretStr = Field(default=SecretStr(""))
    # Direct database connection (for bulk operations)
    database_url: str = Field(default="postgresql://postgres:postgres@localhost:5432/postgres")

    # Apify - LinkedIn Jobs Scraper
    apify_api_token: SecretStr = Field(default=SecretStr(""))
    apify_actor_id: str = Field(default="bebity~linkedin-jobs-scraper")
    apify_base_url: str = Field(default="https://api.apify.com/v2")

    # OpenAI / LLM
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = Field(default="gpt-4o")
    openai_model_mini: str = Field(default="gpt-4o-mini")

    # Scraper settings
    scraper_job_titles: str = Field(
        default="Security Engineer",
        description="Comma-separated list of job titles to search"
    )
    scraper_location: str = Field(default="Switzerland")
    scraper_max_jobs: int = Field(default=50)
    scraper_jobs_per_title: int = Field(default=10)
    scraper_interval_hours: int = Field(default=6)
    scraper_delay_between_searches: float = Field(default=2.0)

    @property
    def job_titles_list(self) -> list[str]:
        """Parse comma-separated job titles into a list."""
        return [t.strip() for t in self.scraper_job_titles.split(",") if t.strip()]

    # Ranker settings
    ranker_min_score: int = Field(default=30)
    ranker_min_triggers: int = Field(default=2)

    # Generator settings
    generator_output_dir: str = Field(default="./output")

    # Matcher settings
    cv_path: Path = Field(default=Path("src/matcher/cv/ernest_haeberli.yaml"))
    matcher_min_llm_score: int = Field(
        default=3, description="Minimum LLM score to consider good match"
    )
    matcher_batch_size: int = Field(default=50, description="Jobs to process per batch")
    matcher_interval_seconds: int = Field(
        default=300, description="Polling interval in daemon mode"
    )

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
