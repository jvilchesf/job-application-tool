"""
Unified Pipeline - Main entry point.

Real-time job application pipeline:
Scrape → Match → Generate → Email

Usage:
    # Run once
    python -m pipeline.main

    # Run as daemon (every 15 minutes)
    python -m pipeline.main --daemon

    # Dry run (no emails, no DB updates)
    python -m pipeline.main --dry-run
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from loguru import logger

from shared.config import get_settings
from pipeline.unified import UnifiedPipeline


def setup_logging():
    """Configure loguru logging."""
    settings = get_settings()
    logger.remove()

    if settings.log_format == "json":
        logger.add(
            sys.stderr,
            format="{message}",
            level=settings.log_level,
            serialize=True,
        )
    else:
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            level=settings.log_level,
        )


@click.command()
@click.option(
    "--daemon",
    "-d",
    is_flag=True,
    help="Run continuously as a daemon",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=15,
    help="Polling interval in minutes (daemon mode)",
)
@click.option(
    "--min-score",
    "-m",
    type=int,
    default=4,
    help="Minimum LLM match score to generate CV (4=Good, 5=Excellent)",
)
@click.option(
    "--max-jobs",
    "-j",
    type=int,
    default=10,
    help="Maximum jobs to scrape per title",
)
@click.option(
    "--skip-email",
    is_flag=True,
    help="Skip sending emails (generate PDFs only)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Don't update database or send emails (test mode)",
)
@click.option(
    "--titles",
    "-t",
    type=str,
    default=None,
    help="Comma-separated job titles to search (overrides settings)",
)
@click.option(
    "--location",
    "-l",
    type=str,
    default=None,
    help="Location to search (overrides settings)",
)
@click.option(
    "--date-posted",
    "-p",
    type=click.Choice(["past-24h", "past-week", "past-month", "any"]),
    default="past-week",
    help="Only get jobs posted within this time period (default: past-week)",
)
@click.option(
    "--max-days-old",
    type=int,
    default=7,
    help="Skip jobs older than this many days (default: 7, 0 to disable)",
)
def main(
    daemon: bool,
    interval: int,
    min_score: int,
    max_jobs: int,
    skip_email: bool,
    dry_run: bool,
    titles: str,
    location: str,
    date_posted: str,
    max_days_old: int,
):
    """
    Unified Pipeline - Real-time job application system.

    Scrapes LinkedIn jobs, matches with CV using LLM, and immediately
    sends tailored CVs for high-match positions (score >= 4).

    Examples:
        # Run once with default settings
        python -m pipeline.main

        # Run as daemon, checking every 15 minutes
        python -m pipeline.main --daemon --interval 15

        # Test run without sending emails
        python -m pipeline.main --dry-run

        # Search specific titles
        python -m pipeline.main --titles "CISO,Security Manager" --location "Switzerland"
    """
    setup_logging()

    if dry_run:
        logger.warning("DRY RUN MODE - No database updates or emails")
    if skip_email:
        logger.warning("SKIP EMAIL MODE - PDFs only, no emails")

    # Parse job titles if provided
    job_titles = None
    if titles:
        job_titles = [t.strip() for t in titles.split(",")]
        logger.info(f"Using custom job titles: {job_titles}")

    # Convert "any" to None for date filter
    date_filter = None if date_posted == "any" else date_posted

    logger.info(f"Date filter: {date_posted}, Max days old: {max_days_old}")

    async def run():
        pipeline = UnifiedPipeline(
            min_score=min_score,
            skip_email=skip_email,
            dry_run=dry_run,
            max_days_old=max_days_old,
            date_posted=date_filter,
        )

        try:
            await pipeline.initialize()

            if daemon:
                await pipeline.run_daemon(
                    interval_minutes=interval,
                    job_titles=job_titles,
                    location=location,
                    max_jobs_per_title=max_jobs,
                )
            else:
                stats = await pipeline.run_once(
                    job_titles=job_titles,
                    location=location,
                    max_jobs_per_title=max_jobs,
                )
                click.echo(f"\n{stats}")

        finally:
            await pipeline.cleanup()

    asyncio.run(run())


if __name__ == "__main__":
    main()
