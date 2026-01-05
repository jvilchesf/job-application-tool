"""
MongoDB database connection and operations using Motor (async driver).
"""

from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from .config import Settings, get_settings


class Database:
    """Async MongoDB database wrapper."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self) -> None:
        """Establish database connection."""
        if self._client is not None:
            return

        logger.info(f"Connecting to MongoDB: {self.settings.mongodb_database}")
        self._client = AsyncIOMotorClient(self.settings.mongodb_uri)
        self._db = self._client[self.settings.mongodb_database]

        # Verify connection
        await self._client.admin.command("ping")
        logger.info("MongoDB connection established")

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("MongoDB connection closed")

    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance."""
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    # -------------------------------------------------------------------------
    # Jobs Collection
    # -------------------------------------------------------------------------

    async def insert_job(self, job: dict[str, Any]) -> str:
        """Insert a new job, returns job_id."""
        job["created_at"] = datetime.now(timezone.utc)
        job["updated_at"] = datetime.now(timezone.utc)
        result = await self.db.jobs.insert_one(job)
        return str(result.inserted_id)

    async def upsert_job(self, job: dict[str, Any]) -> tuple[str, bool]:
        """
        Upsert job by linkedin_id. Returns (job_id, was_inserted).
        """
        linkedin_id = job.get("linkedin_id")
        if not linkedin_id:
            raise ValueError("Job must have linkedin_id for upsert")

        job["updated_at"] = datetime.now(timezone.utc)

        result = await self.db.jobs.update_one(
            {"linkedin_id": linkedin_id},
            {
                "$set": job,
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )

        if result.upserted_id:
            return str(result.upserted_id), True

        # Find existing document
        existing = await self.db.jobs.find_one({"linkedin_id": linkedin_id})
        return str(existing["_id"]), False

    async def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        """Get job by ID."""
        from bson import ObjectId

        return await self.db.jobs.find_one({"_id": ObjectId(job_id)})

    async def get_jobs_by_status(
        self, status: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get jobs by status."""
        cursor = self.db.jobs.find({"status": status}).limit(limit)
        return await cursor.to_list(length=limit)

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
        from bson import ObjectId

        update = {"status": status, "updated_at": datetime.now(timezone.utc)}
        if extra_fields:
            update.update(extra_fields)

        result = await self.db.jobs.update_one(
            {"_id": ObjectId(job_id)}, {"$set": update}
        )
        return result.modified_count > 0

    async def update_job_ranking(
        self,
        job_id: str,
        score: int,
        matched_triggers: list[str],
        matched_support: list[str],
        status: str,
    ) -> bool:
        """Update job with ranking results."""
        from bson import ObjectId

        result = await self.db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "score": score,
                    "matched_triggers": matched_triggers,
                    "matched_support": matched_support,
                    "status": status,
                    "ranked_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    # -------------------------------------------------------------------------
    # Applications Collection
    # -------------------------------------------------------------------------

    async def insert_application(self, application: dict[str, Any]) -> str:
        """Insert a new application."""
        application["created_at"] = datetime.now(timezone.utc)
        application["updated_at"] = datetime.now(timezone.utc)
        result = await self.db.applications.insert_one(application)
        return str(result.inserted_id)

    async def get_application(self, application_id: str) -> Optional[dict[str, Any]]:
        """Get application by ID."""
        from bson import ObjectId

        return await self.db.applications.find_one({"_id": ObjectId(application_id)})

    async def get_applications_by_job(self, job_id: str) -> list[dict[str, Any]]:
        """Get all applications for a job."""
        cursor = self.db.applications.find({"job_id": job_id})
        return await cursor.to_list(length=100)

    async def update_application_status(
        self, application_id: str, status: str, extra_fields: Optional[dict] = None
    ) -> bool:
        """Update application status."""
        from bson import ObjectId

        update = {"status": status, "updated_at": datetime.now(timezone.utc)}
        if extra_fields:
            update.update(extra_fields)

        result = await self.db.applications.update_one(
            {"_id": ObjectId(application_id)}, {"$set": update}
        )
        return result.modified_count > 0

    # -------------------------------------------------------------------------
    # Index Setup
    # -------------------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        """Create database indexes."""
        # Jobs indexes
        job_indexes = [
            IndexModel([("linkedin_id", ASCENDING)], unique=True),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("score", DESCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("company", ASCENDING)]),
        ]
        await self.db.jobs.create_indexes(job_indexes)

        # Applications indexes
        app_indexes = [
            IndexModel([("job_id", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
        await self.db.applications.create_indexes(app_indexes)

        logger.info("Database indexes created")


# Global database instance
_database: Optional[Database] = None


async def get_database() -> Database:
    """Get or create database instance."""
    global _database
    if _database is None:
        _database = Database()
        await _database.connect()
    return _database
