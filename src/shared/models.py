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
    location: str = Field(default="", description="Job location")
    description: str = Field(default="", description="Full job description")
    description_html: Optional[str] = Field(default=None, description="HTML description")

    # Extracted metadata
    salary: Optional[str] = Field(default=None, description="Salary information")
    employment_type: Optional[str] = Field(default=None, description="Full-time, Part-time, etc.")
    experience_level: Optional[str] = Field(default=None, description="Entry, Mid, Senior, etc.")
    posted_date: Optional[datetime] = Field(default=None, description="When job was posted")
    apply_url: Optional[str] = Field(default=None, description="Direct application URL")

    # Ranking data
    score: int = Field(default=0, description="Ranking score")
    matched_triggers: list[str] = Field(default_factory=list, description="Matched trigger keywords")
    matched_support: list[str] = Field(default_factory=list, description="Matched support keywords")

    # Status tracking
    status: JobStatus = Field(default=JobStatus.SCRAPED)
    ranked_at: Optional[datetime] = Field(default=None)
    generated_at: Optional[datetime] = Field(default=None)
    applied_at: Optional[datetime] = Field(default=None)

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
    """Raw job data from Apify LinkedIn scraper."""

    # These fields match the Apify actor output
    id: Optional[str] = Field(default=None, alias="jobId")
    title: Optional[str] = None
    company: Optional[str] = Field(default=None, alias="companyName")
    company_url: Optional[str] = Field(default=None, alias="companyUrl")
    location: Optional[str] = None
    description: Optional[str] = None
    description_html: Optional[str] = Field(default=None, alias="descriptionHtml")
    url: Optional[str] = Field(default=None, alias="jobUrl")
    apply_url: Optional[str] = Field(default=None, alias="applyUrl")
    salary: Optional[str] = None
    posted_at: Optional[str] = Field(default=None, alias="postedAt")
    employment_type: Optional[str] = Field(default=None, alias="employmentType")
    experience_level: Optional[str] = Field(default=None, alias="experienceLevel")
    industries: Optional[list[str]] = None

    class Config:
        populate_by_name = True

    def to_job(self) -> Job:
        """Convert Apify result to Job model."""
        from dateutil import parser

        posted_date = None
        if self.posted_at:
            try:
                posted_date = parser.parse(self.posted_at)
            except Exception:
                pass

        return Job(
            linkedin_id=self.id or "",
            url=self.url or "",
            title=self.title or "",
            company=self.company or "",
            location=self.location or "",
            description=self.description or "",
            description_html=self.description_html,
            salary=self.salary,
            employment_type=self.employment_type,
            experience_level=self.experience_level,
            posted_date=posted_date,
            apply_url=self.apply_url,
        )
