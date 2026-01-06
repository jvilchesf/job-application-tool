"""
Generator Service - Main entry point.
Generates tailored CVs (via RenderCV) and cover letters for high-match jobs,
then emails them to the user via Resend.
"""

import asyncio
import os
import sys
from pathlib import Path

# Set library path for WeasyPrint on macOS (must be before imports)
if sys.platform == "darwin":
    homebrew_lib = "/opt/homebrew/lib"
    if os.path.exists(homebrew_lib):
        os.environ["DYLD_LIBRARY_PATH"] = homebrew_lib

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from loguru import logger

from shared.config import get_settings
from shared.database import Database

from generator.cv_tailor import CVTailor
from generator.rendercv_generator import RenderCVGenerator
from generator.email_service import EmailService


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


async def generate_and_email_applications(
    limit: int = 10,
    min_score: int = 4,
    skip_email: bool = False,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """
    Generate tailored CVs and cover letters for high-match jobs,
    then email them to the user.

    Args:
        limit: Maximum jobs to process
        min_score: Minimum LLM match score (default: 4)
        skip_email: Skip sending emails (generate only)
        dry_run: Don't update database or send emails

    Returns:
        Tuple of (total_processed, successful, failed)
    """
    settings = get_settings()

    logger.info(f"Starting generator (min_score: {min_score}, limit: {limit})")

    # Initialize components
    db = Database()
    await db.connect()

    cv_tailor = CVTailor(
        base_cv_path=settings.generator_cv_path,
        settings=settings,
    )

    pdf_generator = RenderCVGenerator(
        output_dir=Path(settings.generator_output_dir),
    )

    email_service = EmailService(settings=settings) if not skip_email else None

    try:
        # Get high-match jobs that haven't been generated
        jobs = await db.get_high_match_ungenerated_jobs(
            min_score=min_score,
            limit=limit,
        )

        if not jobs:
            logger.info("No high-match jobs found to process")
            return 0, 0, 0

        logger.info(f"Found {len(jobs)} high-match jobs to process")

        total_processed = 0
        successful = 0
        failed = 0

        for job in jobs:
            job_id = str(job["id"])
            title = job.get("title", "Unknown")
            company = job.get("company", "Unknown")
            location = job.get("location", "")
            description = job.get("description", "")
            llm_score = job.get("llm_match_score", 0)

            logger.info(f"Processing: {title} at {company} (score: {llm_score}/5)")

            try:
                # Step 1: Tailor CV and generate cover letter
                logger.debug("Tailoring CV and generating cover letter...")
                tailoring_result = await cv_tailor.tailor_for_job(
                    job_title=title,
                    company=company,
                    location=location,
                    job_description=description,
                )

                if not tailoring_result.success:
                    logger.error(f"Tailoring failed: {tailoring_result.error}")
                    failed += 1
                    continue

                # Step 2: Generate PDF with RenderCV
                logger.debug("Generating PDF with RenderCV...")
                pdf_result = pdf_generator.generate_pdf(
                    cv_data=tailoring_result.tailored_cv,
                    job_id=job_id,
                    company=company,
                )

                if not pdf_result.success:
                    logger.error(f"PDF generation failed: {pdf_result.error}")
                    failed += 1
                    continue

                # Step 3: Generate cover letter PDF
                cv_name = tailoring_result.tailored_cv.get("cv", {}).get("name", "Candidate")
                cover_letter_pdf = pdf_generator.generate_cover_letter_pdf(
                    cover_letter=tailoring_result.cover_letter,
                    job_id=job_id,
                    company=company,
                    job_title=title,
                    candidate_name=cv_name,
                )

                # Step 4: Send email (unless skip_email or dry_run)
                if email_service and not dry_run:
                    logger.debug("Sending email via Resend...")
                    email_result = email_service.send_application_package(
                        job=job,
                        cv_pdf_path=pdf_result.pdf_path,
                        cover_letter=tailoring_result.cover_letter,
                        ats_keywords=tailoring_result.ats_keywords,
                        cover_letter_pdf_path=cover_letter_pdf,
                    )

                    if not email_result.success:
                        logger.error(f"Email failed: {email_result.error}")
                        # Still count as success if PDF was generated
                        logger.warning("PDF generated but email failed - marking as generated")

                # Step 5: Update database (unless dry_run)
                if not dry_run:
                    # Store application record
                    application = {
                        "job_id": job_id,
                        "job_title": title,
                        "company": company,
                        "resume_content": None,  # Stored as YAML
                        "cover_letter_content": tailoring_result.cover_letter,
                        "resume_path": str(pdf_result.pdf_path) if pdf_result.pdf_path else None,
                        "cover_letter_path": str(cover_letter_pdf) if cover_letter_pdf else None,
                        "status": "pending",
                        "notes": f"ATS keywords: {', '.join(tailoring_result.ats_keywords[:10])}",
                    }
                    await db.insert_application(application)

                    # Mark job as generated
                    await db.update_job_generated(job_id, status="generated")

                total_processed += 1
                successful += 1
                logger.info(
                    f"SUCCESS: Generated application for {title} at {company} "
                    f"(PDF: {pdf_result.pdf_path})"
                )

            except Exception as e:
                logger.error(f"Failed to process {title} at {company}: {e}")
                failed += 1

                if not dry_run:
                    await db.update_job_status(job_id, "error")

        logger.info(
            f"Generation complete: {total_processed} processed, "
            f"{successful} successful, {failed} failed"
        )

        return total_processed, successful, failed

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
    "--min-score",
    "-m",
    type=int,
    default=4,
    help="Minimum LLM match score (4=Good, 5=Excellent)",
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
    "--daemon",
    "-d",
    is_flag=True,
    help="Run continuously, processing new high-match jobs",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=14400,  # 4 hours
    help="Polling interval in seconds (daemon mode)",
)
def main(
    limit: int,
    min_score: int,
    skip_email: bool,
    dry_run: bool,
    daemon: bool,
    interval: int,
):
    """
    Generator Service - Creates tailored CVs and emails them.

    Processes jobs with llm_match_score >= min_score, generates tailored
    CV PDFs using RenderCV, and emails them via Resend.
    """
    setup_logging()

    if dry_run:
        logger.warning("DRY RUN MODE - No database updates or emails will be sent")

    if daemon:
        logger.info(f"Starting in daemon mode (interval: {interval}s)")

        async def run_daemon():
            while True:
                try:
                    await generate_and_email_applications(
                        limit=limit,
                        min_score=min_score,
                        skip_email=skip_email,
                        dry_run=dry_run,
                    )
                except Exception as e:
                    logger.error(f"Generation failed: {e}")

                logger.info(f"Sleeping for {interval} seconds ({interval/3600:.1f} hours)")
                await asyncio.sleep(interval)

        asyncio.run(run_daemon())
    else:
        total, success, failed = asyncio.run(
            generate_and_email_applications(
                limit=limit,
                min_score=min_score,
                skip_email=skip_email,
                dry_run=dry_run,
            )
        )
        click.echo(f"Processed: {total}, Successful: {success}, Failed: {failed}")


if __name__ == "__main__":
    main()
