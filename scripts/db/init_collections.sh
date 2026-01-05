#!/bin/bash
# =============================================================================
# Initialize MongoDB collections and indexes
# =============================================================================
# Usage: ./init_collections.sh
#
# Required environment variables:
#   MONGODB_URI - MongoDB connection string
#   MONGODB_DATABASE - Database name (default: job_application)

set -e

# Load environment variables from .env if exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

MONGODB_URI="${MONGODB_URI:-mongodb://localhost:27017}"
MONGODB_DATABASE="${MONGODB_DATABASE:-job_application}"

echo "=============================================="
echo "Initializing MongoDB collections"
echo "Database: ${MONGODB_DATABASE}"
echo "=============================================="

# Run the initialization script using mongosh
mongosh "${MONGODB_URI}/${MONGODB_DATABASE}" --quiet <<'EOF'

// =============================================================================
// Jobs Collection - Raw scraped jobs from LinkedIn
// =============================================================================
db.createCollection("jobs", { capped: false });

db.jobs.createIndex({ "linkedin_id": 1 }, { unique: true, name: "idx_linkedin_id" });
db.jobs.createIndex({ "status": 1 }, { name: "idx_status" });
db.jobs.createIndex({ "scraped_at": -1 }, { name: "idx_scraped_at" });
db.jobs.createIndex({ "company": 1 }, { name: "idx_company" });
db.jobs.createIndex({ "location": 1 }, { name: "idx_location" });

print("✓ Created 'jobs' collection with indexes");

// =============================================================================
// Ranked Jobs Collection - Jobs with scores
// =============================================================================
db.createCollection("ranked_jobs", { capped: false });

db.ranked_jobs.createIndex({ "job_id": 1 }, { unique: true, name: "idx_job_id" });
db.ranked_jobs.createIndex({ "score": -1 }, { name: "idx_score" });
db.ranked_jobs.createIndex({ "pass": 1, "score": -1 }, { name: "idx_pass_score" });
db.ranked_jobs.createIndex({ "template": 1 }, { name: "idx_template" });
db.ranked_jobs.createIndex({ "ranked_at": -1 }, { name: "idx_ranked_at" });

print("✓ Created 'ranked_jobs' collection with indexes");

// =============================================================================
// Generated CVs Collection - Customized CVs
// =============================================================================
db.createCollection("generated_cvs", { capped: false });

db.generated_cvs.createIndex({ "job_id": 1 }, { name: "idx_job_id" });
db.generated_cvs.createIndex({ "generated_at": -1 }, { name: "idx_generated_at" });

print("✓ Created 'generated_cvs' collection with indexes");

// =============================================================================
// Applications Collection - Job application records
// =============================================================================
db.createCollection("applications", { capped: false });

db.applications.createIndex({ "job_id": 1 }, { unique: true, name: "idx_job_id" });
db.applications.createIndex({ "status": 1 }, { name: "idx_status" });
db.applications.createIndex({ "applied_at": -1 }, { name: "idx_applied_at" });

print("✓ Created 'applications' collection with indexes");

// =============================================================================
// Profile Collection - User profile for matching
// =============================================================================
db.createCollection("profile", { capped: false });

print("✓ Created 'profile' collection");

// =============================================================================
// Execution Log Collection - Service execution audit trail
// =============================================================================
db.createCollection("execution_log", { capped: false });

db.execution_log.createIndex({ "service": 1, "started_at": -1 }, { name: "idx_service_started" });
db.execution_log.createIndex({ "started_at": -1 }, { name: "idx_started_at" });

print("✓ Created 'execution_log' collection with indexes");

// =============================================================================
// Summary
// =============================================================================
print("");
print("============================================");
print("MongoDB initialization complete!");
print("============================================");
print("Collections created:");
db.getCollectionNames().forEach(function(c) { print("  - " + c); });

EOF

echo ""
echo "Initialization complete!"
