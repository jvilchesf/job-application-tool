"""
Ranker Service - Main entry point.
Scores jobs using template matching and translates if needed.
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
from ranker.templates import TemplateMatcher
from ranker.translator import JobTranslator


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


async def rank_jobs(
    translate: bool = True,
    limit: int = 100,
    reprocess: bool = False,
) -> tuple[int, int]:
    """
    Rank pending jobs.

    Args:
        translate: Whether to translate non-English descriptions
        limit: Maximum jobs to process
        reprocess: Reprocess already ranked jobs

    Returns:
        Tuple of (qualified_count, disqualified_count)
    """
    settings = get_settings()

    logger.info("Starting job ranker")

    # Initialize components
    db = Database()
    await db.connect()

    matcher = TemplateMatcher(settings.templates_path)
    translator = JobTranslator() if translate else None

    try:
        # Get jobs to process
        if reprocess:
            # Get all jobs regardless of status
            jobs = await db.db.jobs.find({}).limit(limit).to_list(length=limit)
        else:
            jobs = await db.get_pending_jobs(limit)

        logger.info(f"Processing {len(jobs)} jobs")

        qualified_count = 0
        disqualified_count = 0

        for job in jobs:
            job_id = str(job["_id"])
            title = job.get("title", "")
            description = job.get("description", "")
            company = job.get("company", "")

            logger.debug(f"Ranking: {title} at {company}")

            # Translate if needed
            if translator and description:
                description, was_translated = await translator.translate_if_needed(
                    description
                )
                if was_translated:
                    # Store translated description
                    await db.db.jobs.update_one(
                        {"_id": job["_id"]},
                        {"$set": {"description_translated": description}},
                    )

            # Score the job
            result = matcher.score_job(title, description)

            # Update job with ranking results
            status = "qualified" if result.passed else "disqualified"

            await db.update_job_ranking(
                job_id=job_id,
                score=result.score,
                matched_triggers=result.matched_triggers,
                matched_support=result.matched_support,
                status=status,
            )

            if result.passed:
                qualified_count += 1
                logger.info(
                    f"QUALIFIED: {title} at {company} "
                    f"(score: {result.score}, triggers: {result.matched_triggers})"
                )
            else:
                disqualified_count += 1
                logger.debug(
                    f"Disqualified: {title} at {company} (score: {result.score})"
                )

        logger.info(
            f"Ranking complete: {qualified_count} qualified, "
            f"{disqualified_count} disqualified"
        )

        return qualified_count, disqualified_count

    finally:
        await db.disconnect()


@click.command()
@click.option(
    "--no-translate",
    is_flag=True,
    help="Skip translation of non-English descriptions",
)
@click.option(
    "--limit",
    "-l",
    type=int,
    default=100,
    help="Maximum jobs to process",
)
@click.option(
    "--reprocess",
    "-r",
    is_flag=True,
    help="Reprocess already ranked jobs",
)
@click.option(
    "--daemon",
    "-d",
    is_flag=True,
    help="Run continuously, processing new jobs as they arrive",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=300,
    help="Polling interval in seconds (daemon mode)",
)
def main(
    no_translate: bool,
    limit: int,
    reprocess: bool,
    daemon: bool,
    interval: int,
):
    """Job Ranker - Scores and qualifies jobs for application."""
    setup_logging()

    if daemon:
        logger.info(f"Starting in daemon mode (interval: {interval}s)")

        async def run_daemon():
            while True:
                try:
                    await rank_jobs(
                        translate=not no_translate,
                        limit=limit,
                        reprocess=False,
                    )
                except Exception as e:
                    logger.error(f"Ranking failed: {e}")

                logger.info(f"Sleeping for {interval} seconds")
                await asyncio.sleep(interval)

        asyncio.run(run_daemon())
    else:
        qualified, disqualified = asyncio.run(
            rank_jobs(
                translate=not no_translate,
                limit=limit,
                reprocess=reprocess,
            )
        )
        click.echo(f"Qualified: {qualified}, Disqualified: {disqualified}")


if __name__ == "__main__":
    main()
