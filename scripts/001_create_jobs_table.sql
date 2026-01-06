-- =============================================================================
-- Job Application Tool - Database Schema
-- =============================================================================
-- This script creates the tables needed for the job application tool.
-- Run this in your PostgreSQL database.

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- ENUM Types
-- =============================================================================

-- Job processing status
CREATE TYPE job_status AS ENUM (
    'scraped',      -- Just scraped, pending matching
    'qualified',    -- Ready for LLM matching
    'generated',    -- CV/cover letter generated
    'applied',      -- Application submitted
    'rejected',     -- Application rejected
    'interview',    -- Got interview
    'error'         -- Processing error
);

-- Application status
CREATE TYPE application_status AS ENUM (
    'pending',      -- Ready to submit
    'submitted',    -- Submitted successfully
    'failed',       -- Submission failed
    'withdrawn'     -- Withdrawn by user
);

-- =============================================================================
-- Jobs Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS jobs (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- External ID (LinkedIn job ID)
    linkedin_id VARCHAR(50) UNIQUE NOT NULL,

    -- Core job information
    url TEXT NOT NULL,
    title VARCHAR(500) NOT NULL,
    company VARCHAR(500) NOT NULL,
    company_url TEXT,
    location VARCHAR(500),
    description TEXT,

    -- Job metadata
    posted_at TIMESTAMP WITH TIME ZONE,
    posted_time VARCHAR(100),  -- Original "2 days ago" format
    applications_count VARCHAR(100),
    apply_url TEXT,

    -- LLM Match data (2nd pipeline)
    llm_match_score INTEGER,
    llm_match_reasoning TEXT,
    matched_at TIMESTAMP WITH TIME ZONE,

    -- Status tracking
    status job_status DEFAULT 'scraped',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_llm_match_score_range
        CHECK (llm_match_score IS NULL OR (llm_match_score >= 1 AND llm_match_score <= 5))
);

-- =============================================================================
-- Applications Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS applications (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Reference to job
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,

    -- Denormalized job info for quick access
    job_title VARCHAR(500) NOT NULL,
    company VARCHAR(500) NOT NULL,

    -- Generated documents
    resume_path TEXT,
    cover_letter_path TEXT,
    resume_content TEXT,
    cover_letter_content TEXT,

    -- Application tracking
    status application_status DEFAULT 'pending',
    submitted_at TIMESTAMP WITH TIME ZONE,
    response_received_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Jobs indexes
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_linkedin_id ON jobs(linkedin_id);
CREATE INDEX IF NOT EXISTS idx_jobs_llm_match_score ON jobs(llm_match_score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_qualified_unmatched
    ON jobs(status, matched_at)
    WHERE status = 'qualified' AND matched_at IS NULL;

-- Applications indexes
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_created_at ON applications(created_at DESC);

-- =============================================================================
-- Triggers for updated_at
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for jobs table
DROP TRIGGER IF EXISTS update_jobs_updated_at ON jobs;
CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for applications table
DROP TRIGGER IF EXISTS update_applications_updated_at ON applications;
CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE jobs IS 'LinkedIn job postings with LLM-based CV matching scores';
COMMENT ON TABLE applications IS 'Job applications with generated documents';

COMMENT ON COLUMN jobs.linkedin_id IS 'Unique LinkedIn job ID for deduplication';
COMMENT ON COLUMN jobs.llm_match_score IS 'LLM match score (1=Poor, 2=Weak, 3=Moderate, 4=Good, 5=Excellent)';
COMMENT ON COLUMN jobs.llm_match_reasoning IS 'LLM explanation for the match score';
COMMENT ON COLUMN jobs.matched_at IS 'Timestamp when LLM matching was performed';
