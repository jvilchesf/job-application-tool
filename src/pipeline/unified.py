"""
Unified Pipeline - Real-time job processing.

Combines Scraper → Matcher → Generator → Email in one continuous flow
to minimize time-to-application for high-match jobs.
"""

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Set library path for WeasyPrint on macOS (must be before imports)
if sys.platform == "darwin":
    homebrew_lib = "/opt/homebrew/lib"
    if os.path.exists(homebrew_lib):
        os.environ["DYLD_LIBRARY_PATH"] = homebrew_lib

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from scraper.apify_client import ApifyClient
from matcher.cv_loader import CVLoader
from matcher.llm_matcher import LLMMatcher
from generator.cv_tailor import CVTailor
from generator.cv_selector import select_best_cv
from generator.rendercv_generator import RenderCVGenerator
from generator.email_service import EmailService
from shared.config import Settings, get_settings
from shared.database import Database


@dataclass
class PipelineStats:
    """Statistics for pipeline run."""
    jobs_scraped: int = 0
    jobs_new: int = 0
    jobs_matched: int = 0
    score_5_jobs: int = 0
    score_4_jobs: int = 0
    emails_sent: int = 0
    errors: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def duration_seconds(self) -> float:
        return time.time() - self.start_time

    def __str__(self) -> str:
        return (
            f"Scraped: {self.jobs_scraped}, New: {self.jobs_new}, "
            f"Matched: {self.jobs_matched} (5⭐:{self.score_5_jobs}, 4⭐:{self.score_4_jobs}), "
            f"Emails: {self.emails_sent}, Errors: {self.errors}, "
            f"Duration: {self.duration_seconds:.1f}s"
        )


class UnifiedPipeline:
    """
    Real-time unified pipeline: Scrape → Match → Generate → Email.

    Processes jobs immediately as they are scraped, prioritizing
    high-match jobs (score 5 before score 4) to be among the first applicants.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        min_score: int = 4,
        skip_email: bool = False,
        dry_run: bool = False,
    ):
        self.settings = settings or get_settings()
        self.min_score = min_score
        self.skip_email = skip_email
        self.dry_run = dry_run

        # Components (initialized lazily)
        self._db: Optional[Database] = None
        self._scraper: Optional[ApifyClient] = None
        self._cv_loader: Optional[CVLoader] = None
        self._matcher: Optional[LLMMatcher] = None
        self._pdf_generator: Optional[RenderCVGenerator] = None
        self._email_service: Optional[EmailService] = None

        # CV directory
        self.cv_dir = Path(__file__).parent.parent / "generator" / "cv"

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing unified pipeline...")

        # Database
        self._db = Database()
        await self._db.connect()

        # Scraper
        self._scraper = ApifyClient(settings=self.settings)

        # Matcher - use CISO CV for matching (most comprehensive)
        ciso_cv_path = self.cv_dir / "ernest_haberli_ciso.yaml"
        self._cv_loader = CVLoader(ciso_cv_path)
        self._matcher = LLMMatcher(self._cv_loader, settings=self.settings)

        # Generator
        self._pdf_generator = RenderCVGenerator(
            output_dir=Path(self.settings.generator_output_dir),
        )

        # Email service
        if not self.skip_email:
            self._email_service = EmailService(settings=self.settings)

        logger.info("Pipeline initialized successfully")

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._db:
            await self._db.disconnect()
        if self._scraper:
            await self._scraper.close()

    async def process_single_job(
        self,
        job_data: dict,
        stats: PipelineStats,
    ) -> Optional[int]:
        """
        Process a single job through the full pipeline.

        Returns:
            LLM match score if processed, None if skipped/error
        """
        # Use linkedin_id as the unique identifier
        linkedin_id = job_data.get("linkedin_id")
        title = job_data.get("title", "Unknown")
        company = job_data.get("company", "Unknown")
        location = job_data.get("location", "")
        description = job_data.get("description", "")
        apply_url = job_data.get("apply_url") or job_data.get("url", "")

        try:
            # Step 1: Check if job already exists
            existing = await self._db.get_job_by_linkedin_id(linkedin_id)
            if existing:
                logger.debug(f"Skipping existing job: {title} at {company}")
                return None

            stats.jobs_new += 1

            # Step 2: Insert job into database (use the full job_data dict)
            job_data["status"] = "scraped"

            if not self.dry_run:
                inserted_job = await self._db.insert_job(job_data)
                internal_job_id = str(inserted_job["id"])
            else:
                internal_job_id = linkedin_id

            # Step 3: Match with LLM
            logger.info(f"Matching: {title} at {company}")
            match_result = await self._matcher.match_job(
                job_title=title,
                company=company,
                location=location,
                job_description=description,
            )

            if not match_result.success:
                logger.error(f"Matching failed: {match_result.error}")
                stats.errors += 1
                return None

            score = match_result.score
            reasoning = match_result.reasoning

            # Update database with match result
            if not self.dry_run:
                await self._db.update_job_match(
                    internal_job_id, score, reasoning
                )
                # Update status to qualified for high matches
                if score >= self.min_score:
                    await self._db.update_job_status(internal_job_id, "qualified")

            stats.jobs_matched += 1

            if score == 5:
                stats.score_5_jobs += 1
            elif score == 4:
                stats.score_4_jobs += 1

            logger.info(f"Match score: {score}/5 - {title} at {company}")

            # Step 4: If high match, generate CV and send email
            if score >= self.min_score:
                await self._generate_and_send(
                    job_id=internal_job_id,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    apply_url=apply_url,
                    score=score,
                    reasoning=reasoning,
                    stats=stats,
                )

            return score

        except Exception as e:
            logger.error(f"Error processing {title} at {company}: {e}")
            stats.errors += 1
            return None

    async def _generate_and_send(
        self,
        job_id: str,
        title: str,
        company: str,
        location: str,
        description: str,
        apply_url: str,
        score: int,
        reasoning: str,
        stats: PipelineStats,
    ) -> None:
        """Generate tailored CV and send email for high-match job."""
        logger.info(f"🎯 High match ({score}/5)! Generating application for {title} at {company}")

        # Select best CV variant for this job
        cv_path, cv_variant = select_best_cv(title, description, self.cv_dir)
        logger.info(f"Selected CV variant: {cv_variant}")

        # Create tailored CV
        cv_tailor = CVTailor(base_cv_path=cv_path, settings=self.settings)

        tailoring_result = await cv_tailor.tailor_for_job(
            job_title=title,
            company=company,
            location=location,
            job_description=description,
        )

        if not tailoring_result.success:
            logger.error(f"CV tailoring failed: {tailoring_result.error}")
            stats.errors += 1
            return

        # Generate PDF
        pdf_result = self._pdf_generator.generate_pdf(
            cv_data=tailoring_result.tailored_cv,
            job_id=job_id,
            company=company,
        )

        if not pdf_result.success:
            logger.error(f"PDF generation failed: {pdf_result.error}")
            stats.errors += 1
            return

        # Generate cover letter PDF
        cv_name = tailoring_result.tailored_cv.get("cv", {}).get("name", "Candidate")
        cover_letter_pdf = self._pdf_generator.generate_cover_letter_pdf(
            cover_letter=tailoring_result.cover_letter,
            job_id=job_id,
            company=company,
            job_title=title,
            candidate_name=cv_name,
        )

        # Send email
        if self._email_service and not self.dry_run:
            job_dict = {
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "apply_url": apply_url,
                "llm_match_score": score,
                "llm_match_reasoning": reasoning,
            }

            email_result = self._email_service.send_application_package(
                job=job_dict,
                cv_pdf_path=pdf_result.pdf_path,
                cover_letter=tailoring_result.cover_letter,
                ats_keywords=tailoring_result.ats_keywords,
                cover_letter_pdf_path=cover_letter_pdf,
            )

            if email_result.success:
                stats.emails_sent += 1
                logger.info(f"✉️ Email sent for {title} at {company}")
            else:
                logger.error(f"Email failed: {email_result.error}")
                stats.errors += 1

        # Update database
        if not self.dry_run:
            application = {
                "job_id": job_id,
                "job_title": title,
                "company": company,
                "resume_content": None,
                "cover_letter_content": tailoring_result.cover_letter,
                "resume_path": str(pdf_result.pdf_path) if pdf_result.pdf_path else None,
                "cover_letter_path": str(cover_letter_pdf) if cover_letter_pdf else None,
                "status": "pending",
                "notes": f"CV: {cv_variant}, ATS: {', '.join(tailoring_result.ats_keywords[:10])}",
            }
            await self._db.insert_application(application)
            await self._db.update_job_generated(job_id, status="generated")

    async def run_once(
        self,
        job_titles: Optional[list[str]] = None,
        location: Optional[str] = None,
        max_jobs_per_title: int = 10,
    ) -> PipelineStats:
        """
        Run the pipeline once for all job titles.

        Args:
            job_titles: List of job titles to search (default from settings)
            location: Location to search (default from settings)
            max_jobs_per_title: Max jobs to scrape per title

        Returns:
            Pipeline statistics
        """
        stats = PipelineStats()

        # Use defaults from settings
        if job_titles is None:
            job_titles = self.settings.scraper_job_titles
        if location is None:
            location = self.settings.scraper_location

        logger.info(f"Starting pipeline run: {len(job_titles)} titles, location={location}")

        # Collect all jobs first (for priority sorting)
        all_jobs = []

        for title in job_titles:
            logger.info(f"Scraping: {title} in {location}")

            try:
                jobs = await self._scraper.run_actor_sync(
                    title=title,
                    location=location,
                    max_jobs=max_jobs_per_title,
                    timeout_secs=300,
                )

                stats.jobs_scraped += len(jobs)
                logger.info(f"Found {len(jobs)} jobs for '{title}'")

                # Convert to dict format using the model's to_db_dict method
                for job in jobs:
                    job_dict = job.to_db_dict()
                    job_dict["search_title"] = title  # Track which search found it
                    all_jobs.append(job_dict)

                # Small delay between searches
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Scraping failed for '{title}': {e}")
                stats.errors += 1

        logger.info(f"Total jobs scraped: {stats.jobs_scraped}")

        # Process jobs - we'll collect scores and process high ones first
        jobs_with_scores = []

        # First pass: match all jobs to get scores
        for job_data in all_jobs:
            score = await self.process_single_job(job_data, stats)
            if score is not None:
                jobs_with_scores.append((score, job_data))

        # Note: In this implementation, high-match jobs are already processed
        # in process_single_job. The priority is handled by processing score 5
        # jobs immediately when found. For even faster processing of score 5 jobs,
        # we could parallelize the scraping and matching.

        logger.info(f"Pipeline run complete: {stats}")
        return stats

    async def run_daemon(
        self,
        interval_minutes: int = 15,
        job_titles: Optional[list[str]] = None,
        location: Optional[str] = None,
        max_jobs_per_title: int = 10,
    ) -> None:
        """
        Run the pipeline continuously as a daemon.

        Args:
            interval_minutes: Minutes between runs
            job_titles: List of job titles to search
            location: Location to search
            max_jobs_per_title: Max jobs per title per run
        """
        logger.info(f"Starting unified pipeline daemon (interval: {interval_minutes}min)")

        while True:
            try:
                stats = await self.run_once(
                    job_titles=job_titles,
                    location=location,
                    max_jobs_per_title=max_jobs_per_title,
                )

                if stats.emails_sent > 0:
                    logger.info(f"🚀 Sent {stats.emails_sent} applications this run!")

            except Exception as e:
                logger.error(f"Pipeline run failed: {e}")

            logger.info(f"Sleeping for {interval_minutes} minutes...")
            await asyncio.sleep(interval_minutes * 60)
