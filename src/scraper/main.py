"""
Scraper Service - Main entry point.
Fetches LinkedIn jobs via Apify and stores them in MongoDB.
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
    search_url: str | None = None,
    max_jobs: int | None = None,
    use_last_run: bool = False,
) -> int:
    """
    Scrape LinkedIn jobs and store in database.

    Returns:
        Number of new jobs inserted
    """
    settings = get_settings()
    search_url = search_url or settings.scraper_search_url
    max_jobs = max_jobs or settings.scraper_max_jobs

    logger.info(f"Starting job scraper")
    logger.info(f"Search URL: {search_url}")
    logger.info(f"Max jobs: {max_jobs}")

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
            logger.info("Starting new Apify scrape run")
            results = await apify.run_actor(
                search_url=search_url,
                max_jobs=max_jobs,
            )

        logger.info(f"Retrieved {len(results)} jobs from Apify")

        # Store jobs in database
        new_count = 0
        updated_count = 0

        for result in results:
            try:
                job = result.to_job()

                if not job.linkedin_id:
                    logger.warning(f"Skipping job without ID: {job.title}")
                    continue

                job_dict = job.model_dump()
                job_dict["status"] = "scraped"

                job_id, was_inserted = await db.upsert_job(job_dict)

                if was_inserted:
                    new_count += 1
                    logger.debug(f"New job: {job.title} at {job.company}")
                else:
                    updated_count += 1

            except Exception as e:
                logger.error(f"Failed to store job: {e}")

        logger.info(f"Scraping complete: {new_count} new, {updated_count} updated")
        return new_count

    finally:
        await apify.close()
        await db.disconnect()


@click.command()
@click.option(
    "--search-url",
    "-u",
    help="LinkedIn search URL (overrides config)",
)
@click.option(
    "--max-jobs",
    "-m",
    type=int,
    help="Maximum jobs to scrape (overrides config)",
)
@click.option(
    "--use-last-run",
    "-l",
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
    search_url: str | None,
    max_jobs: int | None,
    use_last_run: bool,
    daemon: bool,
):
    """LinkedIn Job Scraper - Fetches jobs via Apify API."""
    setup_logging()
    settings = get_settings()

    if daemon:
        logger.info(f"Starting in daemon mode (interval: {settings.scraper_interval_hours}h)")

        async def run_daemon():
            while True:
                try:
                    await scrape_jobs(search_url, max_jobs, use_last_run=False)
                except Exception as e:
                    logger.error(f"Scrape failed: {e}")

                interval = settings.scraper_interval_hours * 3600
                logger.info(f"Sleeping for {settings.scraper_interval_hours} hours")
                await asyncio.sleep(interval)

        asyncio.run(run_daemon())
    else:
        new_jobs = asyncio.run(scrape_jobs(search_url, max_jobs, use_last_run))
        click.echo(f"Scraped {new_jobs} new jobs")


if __name__ == "__main__":
    main()
