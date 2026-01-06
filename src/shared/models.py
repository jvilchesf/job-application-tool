"""
Pydantic models for Jobs and Applications.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job processing status."""

    SCRAPED = "scraped"  # Just scraped, pending ranking
    QUALIFIED = "qualified"  # Passed ranking, ready for CV generation
    DISQUALIFIED = "disqualified"  # Failed ranking
    GENERATED = "generated"  # CV/cover letter generated
    APPLIED = "applied"  # Application submitted
    REJECTED = "rejected"  # Application rejected
    INTERVIEW = "interview"  # Got interview
    ERROR = "error"  # Processing error


class ApplicationStatus(str, Enum):
    """Application status."""

    PENDING = "pending"  # Ready to submit
    SUBMITTED = "submitted"  # Submitted successfully
    FAILED = "failed"  # Submission failed
    WITHDRAWN = "withdrawn"  # Withdrawn by user


class Job(BaseModel):
    """LinkedIn job posting."""

    # LinkedIn data
    linkedin_id: str = Field(..., description="LinkedIn job ID")
    url: str = Field(..., description="Job URL")
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    company_url: Optional[str] = Field(default=None, description="Company LinkedIn URL")
    location: str = Field(default="", description="Job location")
    description: str = Field(default="", description="Full job description")

    # Metadata
    posted_at: Optional[datetime] = Field(default=None, description="When job was posted")
    posted_time: Optional[str] = Field(default=None, description="Original posted time string")
    applications_count: Optional[str] = Field(default=None, description="Number of applicants")
    apply_url: Optional[str] = Field(default=None, description="Direct application URL")

    # LLM Matching (2nd pipeline)
    llm_match_score: Optional[int] = Field(default=None, description="LLM match score (1-5)")
    llm_match_reasoning: Optional[str] = Field(default=None, description="LLM match explanation")
    matched_at: Optional[datetime] = Field(default=None, description="When LLM matching was done")

    # Status tracking
    status: JobStatus = Field(default=JobStatus.SCRAPED)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())

    class Config:
        use_enum_values = True


class Application(BaseModel):
    """Job application record."""

    job_id: str = Field(..., description="Reference to Job")
    job_title: str = Field(..., description="Job title (denormalized)")
    company: str = Field(..., description="Company name (denormalized)")

    # Generated documents
    resume_path: Optional[str] = Field(default=None, description="Path to generated resume PDF")
    cover_letter_path: Optional[str] = Field(default=None, description="Path to generated cover letter PDF")
    resume_content: Optional[str] = Field(default=None, description="Resume content (markdown/text)")
    cover_letter_content: Optional[str] = Field(default=None, description="Cover letter content")

    # Application data
    status: ApplicationStatus = Field(default=ApplicationStatus.PENDING)
    submitted_at: Optional[datetime] = Field(default=None)
    response_received_at: Optional[datetime] = Field(default=None)
    notes: Optional[str] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())

    class Config:
        use_enum_values = True


class ApifyJobResult(BaseModel):
    """Raw job data from Apify LinkedIn Jobs Scraper (bebity/linkedin-jobs-scraper)."""

    # These fields match the LinkedIn Jobs Scraper output
    id: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = Field(default=None, alias="companyName")
    company_url: Optional[str] = Field(default=None, alias="companyUrl")
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = Field(default=None, alias="jobUrl")
    salary: Optional[str] = None
    published_at: Optional[str] = Field(default=None, alias="publishedAt")
    posted_time: Optional[str] = Field(default=None, alias="postedTime")
    applications_count: Optional[str] = Field(default=None, alias="applicationsCount")

    class Config:
        populate_by_name = True

    def to_job(self) -> Job:
        """Convert Apify result to Job model."""
        from dateutil import parser

        posted_at = None
        if self.published_at:
            try:
                posted_at = parser.parse(self.published_at)
            except Exception:
                pass

        return Job(
            linkedin_id=self.id or "",
            url=self.url or "",
            title=self.title or "",
            company=self.company or "",
            company_url=self.company_url,
            location=self.location or "",
            description=self.description or "",
            posted_at=posted_at,
            posted_time=self.posted_time,
            applications_count=self.applications_count,
            apply_url=self.url,
        )

    def to_db_dict(self) -> dict:
        """Convert to dictionary for database insert."""
        from dateutil import parser

        posted_at = None
        if self.published_at:
            try:
                posted_at = parser.parse(self.published_at)
            except Exception:
                pass

        return {
            "linkedin_id": self.id or "",
            "url": self.url or "",
            "title": self.title or "",
            "company": self.company or "",
            "company_url": self.company_url,
            "location": self.location or "",
            "description": self.description or "",
            "posted_at": posted_at,
            "posted_time": self.posted_time,
            "applications_count": self.applications_count,
            "apply_url": self.url,
            "status": "scraped",
        }
