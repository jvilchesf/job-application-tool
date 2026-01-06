-- =============================================================================
-- Add LLM Match Scoring Columns to Jobs Table
-- =============================================================================
-- This migration adds columns for LLM-based CV matching to the jobs table

-- Add new columns for LLM-based matching
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS llm_match_score INTEGER;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS llm_match_reasoning TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS matched_at TIMESTAMP WITH TIME ZONE;

-- Add index for efficient querying of matched jobs
CREATE INDEX IF NOT EXISTS idx_jobs_llm_match_score ON jobs(llm_match_score DESC);

-- Add composite index for finding qualified but unmatched jobs
CREATE INDEX IF NOT EXISTS idx_jobs_qualified_unmatched
    ON jobs(status, matched_at)
    WHERE status = 'qualified' AND matched_at IS NULL;

-- Add constraint to ensure valid score range (1-5)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_llm_match_score_range'
    ) THEN
        ALTER TABLE jobs ADD CONSTRAINT chk_llm_match_score_range
            CHECK (llm_match_score IS NULL OR (llm_match_score >= 1 AND llm_match_score <= 5));
    END IF;
END $$;

-- Update comments
COMMENT ON COLUMN jobs.llm_match_score IS 'LLM-based CV match score (1=Poor, 2=Weak, 3=Moderate, 4=Good, 5=Excellent)';
COMMENT ON COLUMN jobs.llm_match_reasoning IS 'LLM explanation for the match score';
COMMENT ON COLUMN jobs.matched_at IS 'Timestamp when LLM matching was performed';
