-- =============================================================================
-- Schema Cleanup - Remove Unused Columns
-- =============================================================================
-- This migration removes unused columns from the jobs table to simplify the schema.
-- The keyword-based ranking (1st pipeline) is replaced by LLM matching (2nd pipeline).

-- Remove keyword ranking columns (replaced by LLM matching)
ALTER TABLE jobs DROP COLUMN IF EXISTS score;
ALTER TABLE jobs DROP COLUMN IF EXISTS matched_triggers;
ALTER TABLE jobs DROP COLUMN IF EXISTS matched_support;
ALTER TABLE jobs DROP COLUMN IF EXISTS ranked_at;

-- Remove columns that were never populated
ALTER TABLE jobs DROP COLUMN IF EXISTS description_html;
ALTER TABLE jobs DROP COLUMN IF EXISTS salary;
ALTER TABLE jobs DROP COLUMN IF EXISTS employment_type;
ALTER TABLE jobs DROP COLUMN IF EXISTS experience_level;

-- Remove future columns not yet needed (can be re-added later)
ALTER TABLE jobs DROP COLUMN IF EXISTS generated_at;
ALTER TABLE jobs DROP COLUMN IF EXISTS applied_at;

-- Drop unused indexes
DROP INDEX IF EXISTS idx_jobs_score;
DROP INDEX IF EXISTS idx_jobs_company;

-- Update status enum to simplify (remove unused statuses)
-- Note: We keep the enum as-is for now since changing enums requires more work

-- Add comments for clarity
COMMENT ON TABLE jobs IS 'LinkedIn job postings with LLM-based CV matching scores';
COMMENT ON COLUMN jobs.llm_match_score IS 'LLM match score (1=Poor, 2=Weak, 3=Moderate, 4=Good, 5=Excellent)';
COMMENT ON COLUMN jobs.status IS 'Job status: scraped -> qualified -> generated -> applied';
