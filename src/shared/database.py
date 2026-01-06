"""
Supabase/PostgreSQL database connection and operations using asyncpg.
"""

from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from loguru import logger

from .config import Settings, get_settings


class Database:
    """Async PostgreSQL database wrapper for Supabase."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._pool = None

    async def connect(self) -> None:
        """Establish database connection pool."""
        if self._pool is not None:
            return

        import asyncpg

        logger.info(f"Connecting to PostgreSQL database")
        self._pool = await asyncpg.create_pool(
            self.settings.database_url,
            min_size=1,
            max_size=10,
        )
        logger.info("PostgreSQL connection pool established")

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection closed")

    @property
    def pool(self):
        """Get connection pool."""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    # -------------------------------------------------------------------------
    # Jobs Table
    # -------------------------------------------------------------------------

    async def insert_job(self, job: dict[str, Any]) -> str:
        """Insert a new job, returns job_id."""
        job_id = str(uuid.uuid4())

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO jobs (
                    id, linkedin_id, url, title, company, company_url, location,
                    description, posted_at, posted_time, applications_count,
                    apply_url, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                uuid.UUID(job_id),
                job.get("linkedin_id"),
                job.get("url"),
                job.get("title"),
                job.get("company"),
                job.get("company_url"),
                job.get("location"),
                job.get("description"),
                job.get("posted_at"),
                job.get("posted_time"),
                job.get("applications_count"),
                job.get("apply_url"),
                job.get("status", "scraped"),
            )

        return job_id

    async def upsert_job(self, job: dict[str, Any]) -> tuple[str, bool]:
        """
        Upsert job by linkedin_id. Returns (job_id, was_inserted).
        """
        linkedin_id = job.get("linkedin_id")
        if not linkedin_id:
            raise ValueError("Job must have linkedin_id for upsert")

        async with self.pool.acquire() as conn:
            # Check if exists
            existing = await conn.fetchrow(
                "SELECT id FROM jobs WHERE linkedin_id = $1",
                linkedin_id
            )

            if existing:
                # Update existing job
                await conn.execute(
                    """
                    UPDATE jobs SET
                        url = $2, title = $3, company = $4, company_url = $5,
                        location = $6, description = $7, posted_at = $8,
                        posted_time = $9, applications_count = $10,
                        apply_url = $11, updated_at = NOW()
                    WHERE linkedin_id = $1
                    """,
                    linkedin_id,
                    job.get("url"),
                    job.get("title"),
                    job.get("company"),
                    job.get("company_url"),
                    job.get("location"),
                    job.get("description"),
                    job.get("posted_at"),
                    job.get("posted_time"),
                    job.get("applications_count"),
                    job.get("apply_url"),
                )
                return str(existing["id"]), False
            else:
                # Insert new job
                job_id = str(uuid.uuid4())
                await conn.execute(
                    """
                    INSERT INTO jobs (
                        id, linkedin_id, url, title, company, company_url, location,
                        description, posted_at, posted_time, applications_count,
                        apply_url, status
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    """,
                    uuid.UUID(job_id),
                    linkedin_id,
                    job.get("url"),
                    job.get("title"),
                    job.get("company"),
                    job.get("company_url"),
                    job.get("location"),
                    job.get("description"),
                    job.get("posted_at"),
                    job.get("posted_time"),
                    job.get("applications_count"),
                    job.get("apply_url"),
                    job.get("status", "scraped"),
                )
                return job_id, True

    async def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        """Get job by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM jobs WHERE id = $1",
                uuid.UUID(job_id)
            )
            return dict(row) if row else None

    async def get_job_by_linkedin_id(self, linkedin_id: str) -> Optional[dict[str, Any]]:
        """Get job by LinkedIn ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM jobs WHERE linkedin_id = $1",
                linkedin_id
            )
            return dict(row) if row else None

    async def get_jobs_by_status(
        self, status: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get jobs by status."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM jobs WHERE status = $1 ORDER BY created_at DESC LIMIT $2",
                status,
                limit
            )
            return [dict(row) for row in rows]

    async def get_pending_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get jobs pending ranking."""
        return await self.get_jobs_by_status("scraped", limit)

    async def get_qualified_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get jobs that passed ranking."""
        return await self.get_jobs_by_status("qualified", limit)

    async def update_job_status(
        self, job_id: str, status: str, extra_fields: Optional[dict] = None
    ) -> bool:
        """Update job status and optional extra fields."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE jobs SET status = $1, updated_at = NOW() WHERE id = $2",
                status,
                uuid.UUID(job_id)
            )
            return result == "UPDATE 1"

    # -------------------------------------------------------------------------
    # Matcher Operations (LLM-based CV matching)
    # -------------------------------------------------------------------------

    async def update_job_match(
        self,
        job_id: str,
        llm_match_score: int,
        llm_match_reasoning: str,
    ) -> bool:
        """Update job with LLM match results."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE jobs SET
                    llm_match_score = $1,
                    llm_match_reasoning = $2,
                    matched_at = NOW(),
                    updated_at = NOW()
                WHERE id = $3
                """,
                llm_match_score,
                llm_match_reasoning,
                uuid.UUID(job_id),
            )
            return result == "UPDATE 1"

    async def get_qualified_unmatched_jobs(
        self, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get qualified jobs that haven't been LLM-matched yet."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM jobs
                WHERE status = 'qualified' AND matched_at IS NULL
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(row) for row in rows]

    async def get_well_matched_jobs(
        self, min_llm_score: int = 3, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get jobs with good LLM match scores for CV generation."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM jobs
                WHERE status = 'qualified'
                  AND llm_match_score >= $1
                ORDER BY llm_match_score DESC, created_at DESC
                LIMIT $2
                """,
                min_llm_score,
                limit,
            )
            return [dict(row) for row in rows]

    async def get_high_match_ungenerated_jobs(
        self, min_score: int = 4, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get high-match jobs that haven't been generated yet."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM jobs
                WHERE status = 'qualified'
                  AND llm_match_score >= $1
                  AND generated_at IS NULL
                ORDER BY llm_match_score DESC, created_at DESC
                LIMIT $2
                """,
                min_score,
                limit,
            )
            return [dict(row) for row in rows]

    async def update_job_generated(
        self, job_id: str, status: str = "generated"
    ) -> bool:
        """Mark job as generated."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE jobs SET
                    status = $1,
                    generated_at = NOW(),
                    updated_at = NOW()
                WHERE id = $2
                """,
                status,
                uuid.UUID(job_id),
            )
            return result == "UPDATE 1"

    async def get_all_jobs(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Get all jobs."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT $1",
                limit
            )
            return [dict(row) for row in rows]

    async def count_jobs(self) -> int:
        """Count total jobs."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM jobs")
            return row["count"]

    async def count_jobs_by_status(self) -> dict[str, int]:
        """Count jobs grouped by status."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
            )
            return {row["status"]: row["count"] for row in rows}

    # -------------------------------------------------------------------------
    # Applications Table
    # -------------------------------------------------------------------------

    async def insert_application(self, application: dict[str, Any]) -> str:
        """Insert a new application."""
        app_id = str(uuid.uuid4())

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO applications (
                    id, job_id, job_title, company, resume_path, cover_letter_path,
                    resume_content, cover_letter_content, status, notes
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                uuid.UUID(app_id),
                uuid.UUID(application.get("job_id")),
                application.get("job_title"),
                application.get("company"),
                application.get("resume_path"),
                application.get("cover_letter_path"),
                application.get("resume_content"),
                application.get("cover_letter_content"),
                application.get("status", "pending"),
                application.get("notes"),
            )

        return app_id

    async def get_application(self, application_id: str) -> Optional[dict[str, Any]]:
        """Get application by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM applications WHERE id = $1",
                uuid.UUID(application_id)
            )
            return dict(row) if row else None

    async def get_applications_by_job(self, job_id: str) -> list[dict[str, Any]]:
        """Get all applications for a job."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM applications WHERE job_id = $1",
                uuid.UUID(job_id)
            )
            return [dict(row) for row in rows]

    async def update_application_status(
        self, application_id: str, status: str, extra_fields: Optional[dict] = None
    ) -> bool:
        """Update application status."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE applications SET status = $1, updated_at = NOW() WHERE id = $2",
                status,
                uuid.UUID(application_id)
            )
            return result == "UPDATE 1"

    # -------------------------------------------------------------------------
    # Index Setup (no-op for PostgreSQL - indexes are in migration)
    # -------------------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        """Indexes are created via SQL migration."""
        logger.info("Indexes managed via SQL migrations")


# Global database instance
_database: Optional[Database] = None


async def get_database() -> Database:
    """Get or create database instance."""
    global _database
    if _database is None:
        _database = Database()
        await _database.connect()
    return _database
