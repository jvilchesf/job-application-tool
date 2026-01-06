"""
Scraper Service - Main entry point.
Fetches LinkedIn jobs via Apify and stores them in Supabase/PostgreSQL.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from loguru import logger

from shared.config import get_settings
from shared.database import Database
from scraper.apify_client import ApifyClient


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
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=settings.log_level,
        )


async def scrape_jobs(
    job_titles: list[str] | None = None,
    location: str | None = None,
    max_jobs: int | None = None,
    jobs_per_title: int | None = None,
    use_last_run: bool = False,
) -> int:
    """
    Scrape LinkedIn jobs and store in database.

    Args:
        job_titles: List of job titles to search for
        location: Location to search in (e.g., "Switzerland")
        max_jobs: Maximum total jobs to scrape
        jobs_per_title: Maximum jobs per title search
        use_last_run: Use results from last Apify run instead of new scrape

    Returns:
        Number of new jobs inserted
    """
    settings = get_settings()
    job_titles = job_titles or settings.job_titles_list
    location = location or settings.scraper_location
    max_jobs = max_jobs or settings.scraper_max_jobs
    jobs_per_title = jobs_per_title or settings.scraper_jobs_per_title

    logger.info("Starting LinkedIn job scraper")
    logger.info(f"Job titles: {job_titles}")
    logger.info(f"Location: {location}")
    logger.info(f"Max jobs: {max_jobs}, Per title: {jobs_per_title}")

    # Initialize clients
    db = Database()
    await db.connect()
    await db.ensure_indexes()

    apify = ApifyClient()

    try:
        # Fetch jobs from Apify
        if use_last_run:
            logger.info("Fetching results from last Apify run")
            results = await apify.get_last_run_results()
        else:
            logger.info("Starting new Apify LinkedIn scrape")
            results = await apify.run_multi_title_search(
                titles=job_titles,
                location=location,
                jobs_per_title=jobs_per_title,
                max_total_jobs=max_jobs,
                delay_between_searches=settings.scraper_delay_between_searches,
            )

        logger.info(f"Retrieved {len(results)} jobs from LinkedIn")

        # Store jobs in database
        new_count = 0
        updated_count = 0
        error_count = 0

        for result in results:
            try:
                # Use to_db_dict for direct database insertion
                job_dict = result.to_db_dict()

                if not job_dict.get("linkedin_id"):
                    logger.warning(f"Skipping job without ID: {job_dict.get('title')}")
                    continue

                job_id, was_inserted = await db.upsert_job(job_dict)

                if was_inserted:
                    new_count += 1
                    logger.debug(f"New job: {job_dict['title']} at {job_dict['company']}")
                else:
                    updated_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"Failed to store job: {e}")

        logger.info(f"Scraping complete: {new_count} new, {updated_count} updated, {error_count} errors")
        return new_count

    finally:
        await apify.close()
        await db.disconnect()


@click.command()
@click.option(
    "--titles",
    "-t",
    help="Comma-separated job titles (e.g., 'CISO,IT Security Manager')",
)
@click.option(
    "--location",
    "-l",
    help="Location to search in (e.g., 'Switzerland')",
)
@click.option(
    "--max-jobs",
    "-m",
    type=int,
    help="Maximum total jobs to scrape",
)
@click.option(
    "--per-title",
    "-p",
    type=int,
    help="Maximum jobs per title search",
)
@click.option(
    "--use-last-run",
    "-r",
    is_flag=True,
    help="Use results from last Apify run instead of starting new one",
)
@click.option(
    "--daemon",
    "-d",
    is_flag=True,
    help="Run continuously at configured interval",
)
def main(
    titles: str | None,
    location: str | None,
    max_jobs: int | None,
    per_title: int | None,
    use_last_run: bool,
    daemon: bool,
):
    """LinkedIn Job Scraper - Fetches jobs via Apify API."""
    setup_logging()
    settings = get_settings()

    # Parse titles from comma-separated string
    job_titles = None
    if titles:
        job_titles = [t.strip() for t in titles.split(",") if t.strip()]

    if daemon:
        logger.info(f"Starting in daemon mode (interval: {settings.scraper_interval_hours}h)")

        async def run_daemon():
            while True:
                try:
                    await scrape_jobs(job_titles, location, max_jobs, per_title, use_last_run=False)
                except Exception as e:
                    logger.error(f"Scrape failed: {e}")

                interval = settings.scraper_interval_hours * 3600
                logger.info(f"Sleeping for {settings.scraper_interval_hours} hours")
                await asyncio.sleep(interval)

        asyncio.run(run_daemon())
    else:
        new_jobs = asyncio.run(scrape_jobs(job_titles, location, max_jobs, per_title, use_last_run))
        click.echo(f"Scraped {new_jobs} new jobs")


if __name__ == "__main__":
    main()
