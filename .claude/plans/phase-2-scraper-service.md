# Phase 2: Scraper Service Implementation

## Status: IN PROGRESS

## Overview

Implement and test the Scraper service that fetches LinkedIn jobs via Apify API and stores them in MongoDB.

## Tasks

### Core Implementation
- [x] Implement `ApifyClient` class with API methods
- [x] Implement actor run and polling logic
- [x] Implement dataset fetching
- [x] Implement job normalization (ApifyJobResult → Job)
- [x] Implement MongoDB upsert logic

### CLI Interface
- [x] Implement Click-based CLI
- [x] Add `--search-url` option
- [x] Add `--max-jobs` option
- [x] Add `--use-last-run` option
- [x] Add `--daemon` mode for continuous execution

### Testing
- [ ] Create `.env` file with actual API tokens
- [ ] Install Python dependencies
- [ ] Run scraper manually to test Apify integration
- [ ] Verify jobs are stored in MongoDB
- [ ] Test deduplication (run twice, check no duplicates)

### Docker
- [ ] Build scraper Docker image
- [ ] Test image locally with docker run
- [ ] Verify environment variable injection

### Kubernetes
- [ ] Deploy to Kind cluster
- [ ] Verify CronJob execution
- [ ] Check logs for successful runs

## Implementation Details

### Apify API Flow

1. POST `/acts/{actorId}/runs` - Start actor with search URL
2. GET `/actor-runs/{runId}` - Poll for completion
3. GET `/datasets/{datasetId}/items` - Fetch results

### Job Normalization

Apify returns:
```json
{
  "jobId": "123",
  "title": "Security Engineer",
  "companyName": "Company",
  "jobUrl": "https://linkedin.com/...",
  "description": "...",
  ...
}
```

Normalized to:
```json
{
  "linkedin_id": "123",
  "title": "Security Engineer",
  "company": "Company",
  "url": "https://linkedin.com/...",
  "description": "...",
  "status": "scraped",
  ...
}
```

## Testing Commands

```bash
# Install dependencies
cd /home/administrator/job-application-tool-2
pip install -e .

# Create .env file
cp .env.example .env
# Edit .env with actual API tokens

# Run scraper (one-time)
python -m scraper.main

# Run with custom URL
python -m scraper.main --search-url "https://linkedin.com/jobs/search/?keywords=DevOps"

# Use last Apify run (no new scrape)
python -m scraper.main --use-last-run

# Check MongoDB
docker exec -it mongodb mongosh job_application --eval "db.jobs.countDocuments()"
docker exec -it mongodb mongosh job_application --eval "db.jobs.find().limit(3).pretty()"
```

## Blockers

- Need Apify API token to test
- Need to verify Apify actor ID is correct

## Next Phase

Proceed to Phase 3: Ranker Service Testing
