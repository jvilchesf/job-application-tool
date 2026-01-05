"""
Generator Service - Main entry point.
Generates tailored resumes and cover letters for qualified jobs.
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
from generator.profile import ProfileLoader
from generator.llm import ResumeGenerator, CoverLetterGenerator
from generator.pdf import PDFGenerator


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


async def generate_applications(
    limit: int = 10,
    skip_existing: bool = True,
    pdf: bool = True,
) -> int:
    """
    Generate resumes and cover letters for qualified jobs.

    Args:
        limit: Maximum jobs to process
        skip_existing: Skip jobs that already have generated applications
        pdf: Generate PDF files

    Returns:
        Number of applications generated
    """
    settings = get_settings()

    logger.info("Starting application generator")

    # Initialize components
    db = Database()
    await db.connect()

    profile_loader = ProfileLoader(settings.profile_path)
    profile_loader.load()

    resume_gen = ResumeGenerator(profile_loader)
    cover_gen = CoverLetterGenerator(profile_loader)
    pdf_gen = PDFGenerator(Path(settings.generator_output_dir))

    try:
        # Get qualified jobs
        jobs = await db.get_qualified_jobs(limit)
        logger.info(f"Found {len(jobs)} qualified jobs")

        generated_count = 0

        for job in jobs:
            job_id = str(job["_id"])
            title = job.get("title", "")
            company = job.get("company", "")
            description = job.get("description_translated") or job.get("description", "")

            # Check if already generated
            if skip_existing:
                existing = await db.get_applications_by_job(job_id)
                if existing:
                    logger.debug(f"Skipping {title} at {company} - already generated")
                    continue

            logger.info(f"Generating application for: {title} at {company}")

            try:
                # Get matched keywords for context
                matched_keywords = (
                    job.get("matched_triggers", []) + job.get("matched_support", [])
                )

                # Generate resume
                resume_content = await resume_gen.generate_resume(
                    job_title=title,
                    job_description=description,
                    company=company,
                    matched_keywords=matched_keywords,
                )

                # Generate cover letter
                cover_letter_content = await cover_gen.generate_cover_letter(
                    job_title=title,
                    job_description=description,
                    company=company,
                    matched_keywords=matched_keywords,
                )

                # Generate PDFs
                resume_path = None
                cover_letter_path = None

                if pdf:
                    resume_path = pdf_gen.generate_resume_pdf(
                        content=resume_content,
                        job_id=job_id,
                        company=company,
                    )
                    cover_letter_path = pdf_gen.generate_cover_letter_pdf(
                        content=cover_letter_content,
                        job_id=job_id,
                        company=company,
                    )

                # Store application in database
                application = {
                    "job_id": job_id,
                    "job_title": title,
                    "company": company,
                    "resume_content": resume_content,
                    "cover_letter_content": cover_letter_content,
                    "resume_path": str(resume_path) if resume_path else None,
                    "cover_letter_path": str(cover_letter_path) if cover_letter_path else None,
                    "status": "pending",
                }

                await db.insert_application(application)

                # Update job status
                await db.update_job_status(job_id, "generated")

                generated_count += 1
                logger.info(f"Generated application for {title} at {company}")

            except Exception as e:
                logger.error(f"Failed to generate for {title} at {company}: {e}")
                await db.update_job_status(job_id, "error", {"error": str(e)})

        logger.info(f"Generation complete: {generated_count} applications created")
        return generated_count

    finally:
        await db.disconnect()


@click.command()
@click.option(
    "--limit",
    "-l",
    type=int,
    default=10,
    help="Maximum jobs to process",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Regenerate even if application exists",
)
@click.option(
    "--no-pdf",
    is_flag=True,
    help="Skip PDF generation (save content only)",
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
    force: bool,
    no_pdf: bool,
    daemon: bool,
    interval: int,
):
    """Application Generator - Creates tailored resumes and cover letters."""
    setup_logging()

    if daemon:
        logger.info(f"Starting in daemon mode (interval: {interval}s)")

        async def run_daemon():
            while True:
                try:
                    await generate_applications(
                        limit=limit,
                        skip_existing=not force,
                        pdf=not no_pdf,
                    )
                except Exception as e:
                    logger.error(f"Generation failed: {e}")

                logger.info(f"Sleeping for {interval} seconds")
                await asyncio.sleep(interval)

        asyncio.run(run_daemon())
    else:
        count = asyncio.run(
            generate_applications(
                limit=limit,
                skip_existing=not force,
                pdf=not no_pdf,
            )
        )
        click.echo(f"Generated {count} applications")


if __name__ == "__main__":
    main()
