-- =============================================================================
-- Add generated_at column for tracking CV generation
-- =============================================================================
-- This migration adds the generated_at timestamp to track when
-- CVs were generated for high-match jobs.

-- Add generated_at column to jobs table
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS generated_at TIMESTAMP WITH TIME ZONE;

-- Create partial index for efficient querying of high-match ungenerated jobs
CREATE INDEX IF NOT EXISTS idx_jobs_high_match_ungenerated
    ON jobs(llm_match_score DESC, created_at DESC)
    WHERE status = 'qualified' AND llm_match_score >= 4 AND generated_at IS NULL;

-- Add comment
COMMENT ON COLUMN jobs.generated_at IS 'Timestamp when CV/cover letter were generated and emailed';
