"""
Matcher Service - Main entry point.
Matches qualified jobs against CV using LLM.
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

from .cv_loader import CVLoader
from .llm_matcher import LLMMatcher


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


async def match_jobs(
    limit: int = 50,
    min_score: int = 3,
    reprocess: bool = False,
) -> tuple[int, int, int]:
    """
    Match qualified jobs against CV using LLM.

    Args:
        limit: Maximum jobs to process
        min_score: Minimum LLM score to consider a good match (for reporting)
        reprocess: Reprocess already matched jobs

    Returns:
        Tuple of (total_processed, good_matches, poor_matches)
    """
    settings = get_settings()

    logger.info("Starting job matcher")

    # Initialize components
    db = Database()
    await db.connect()

    cv_loader = CVLoader(settings.cv_path)
    cv_loader.load()

    matcher = LLMMatcher(cv_loader)

    try:
        # Get qualified jobs that haven't been matched yet
        async with db.pool.acquire() as conn:
            if reprocess:
                # Get all qualified jobs
                rows = await conn.fetch(
                    """
                    SELECT * FROM jobs
                    WHERE status = 'qualified'
                    ORDER BY llm_match_score DESC NULLS LAST, created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
            else:
                # Get only unmatched qualified jobs
                rows = await conn.fetch(
                    """
                    SELECT * FROM jobs
                    WHERE status = 'qualified' AND matched_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )

        jobs = [dict(row) for row in rows]
        logger.info(f"Processing {len(jobs)} qualified jobs")

        total_processed = 0
        good_matches = 0
        poor_matches = 0

        for job in jobs:
            job_id = str(job["id"])
            title = job.get("title", "")
            company = job.get("company", "")
            location = job.get("location", "")
            description = job.get("description", "")

            logger.debug(f"Matching: {title} at {company}")

            # Perform LLM matching
            result = await matcher.match_job(
                job_title=title,
                company=company,
                location=location,
                job_description=description,
            )

            if result.success:
                # Update job with match results
                await db.update_job_match(
                    job_id=job_id,
                    llm_match_score=result.score,
                    llm_match_reasoning=result.reasoning,
                )

                total_processed += 1

                if result.score >= min_score:
                    good_matches += 1
                    reasoning_preview = (
                        result.reasoning[:100] + "..."
                        if len(result.reasoning) > 100
                        else result.reasoning
                    )
                    logger.info(
                        f"GOOD MATCH: {title} at {company} "
                        f"(score: {result.score}/5) - {reasoning_preview}"
                    )
                else:
                    poor_matches += 1
                    logger.debug(
                        f"Poor match: {title} at {company} (score: {result.score}/5)"
                    )
            else:
                logger.error(f"Failed to match {title} at {company}: {result.error}")

        logger.info(
            f"Matching complete: {total_processed} processed, "
            f"{good_matches} good matches, {poor_matches} poor matches"
        )

        return total_processed, good_matches, poor_matches

    finally:
        await db.disconnect()


@click.command()
@click.option(
    "--limit",
    "-l",
    type=int,
    default=50,
    help="Maximum jobs to process",
)
@click.option(
    "--min-score",
    "-m",
    type=int,
    default=3,
    help="Minimum score to consider a good match (for reporting)",
)
@click.option(
    "--reprocess",
    "-r",
    is_flag=True,
    help="Reprocess already matched jobs",
)
@click.option(
    "--daemon",
    "-d",
    is_flag=True,
    help="Run continuously, processing new qualified jobs",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=300,
    help="Polling interval in seconds (daemon mode)",
)
def main(
    limit: int,
    min_score: int,
    reprocess: bool,
    daemon: bool,
    interval: int,
):
    """Job Matcher - Evaluates CV-job fit using LLM."""
    setup_logging()

    if daemon:
        logger.info(f"Starting in daemon mode (interval: {interval}s)")

        async def run_daemon():
            while True:
                try:
                    await match_jobs(
                        limit=limit,
                        min_score=min_score,
                        reprocess=False,
                    )
                except Exception as e:
                    logger.error(f"Matching failed: {e}")

                logger.info(f"Sleeping for {interval} seconds")
                await asyncio.sleep(interval)

        asyncio.run(run_daemon())
    else:
        total, good, poor = asyncio.run(
            match_jobs(
                limit=limit,
                min_score=min_score,
                reprocess=reprocess,
            )
        )
        click.echo(f"Processed: {total}, Good matches: {good}, Poor matches: {poor}")


if __name__ == "__main__":
    main()
