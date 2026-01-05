# Phase 5: End-to-End Testing & Deployment

## Status: PENDING

## Overview

Test the complete pipeline from scraping to generation, then deploy to Kubernetes.

## Tasks

### Local E2E Testing
- [ ] Run scraper → verify jobs in MongoDB
- [ ] Run ranker → verify qualified jobs
- [ ] Run generator → verify applications created
- [ ] Review generated PDFs for quality

### Docker Testing
- [ ] Build all Docker images
- [ ] Test each image locally
- [ ] Verify environment variable handling
- [ ] Test volume mounts for output

### Kubernetes Deployment
- [ ] Create namespace and secrets
- [ ] Deploy MongoDB (or use external)
- [ ] Deploy scraper CronJob
- [ ] Deploy ranker CronJob
- [ ] Deploy generator CronJob
- [ ] Verify scheduled execution

### Monitoring
- [ ] Check pod logs
- [ ] Verify job completion
- [ ] Set up alerts for failures

## E2E Test Script

```bash
#!/bin/bash
# Full pipeline test

echo "=== Step 1: Scrape Jobs ==="
python -m scraper.main --max-jobs 20
echo "Jobs scraped: $(docker exec mongodb mongosh job_application --quiet --eval 'db.jobs.countDocuments({status: "scraped"})')"

echo "=== Step 2: Rank Jobs ==="
python -m ranker.main
echo "Qualified: $(docker exec mongodb mongosh job_application --quiet --eval 'db.jobs.countDocuments({status: "qualified"})')"
echo "Disqualified: $(docker exec mongodb mongosh job_application --quiet --eval 'db.jobs.countDocuments({status: "disqualified"})')"

echo "=== Step 3: Generate Applications ==="
python -m generator.main --limit 5
echo "Generated: $(docker exec mongodb mongosh job_application --quiet --eval 'db.applications.countDocuments()')"

echo "=== Step 4: Review Output ==="
ls -la output/
```

## Docker Commands

```bash
# Build images
docker build -f docker/Dockerfile.scraper -t job-application/scraper:latest .
docker build -f docker/Dockerfile.ranker -t job-application/ranker:latest .
docker build -f docker/Dockerfile.generator -t job-application/generator:latest .

# Test scraper
docker run --rm --network host \
  -e MONGODB_URI=mongodb://localhost:27017 \
  -e APIFY_API_TOKEN=$APIFY_API_TOKEN \
  job-application/scraper:latest

# Test generator with volume mount
docker run --rm --network host \
  -e MONGODB_URI=mongodb://localhost:27017 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/config:/app/config \
  job-application/generator:latest
```

## Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace job-application

# Create secrets
kubectl create secret generic job-application-secrets \
  --namespace job-application \
  --from-literal=APIFY_API_TOKEN=$APIFY_API_TOKEN \
  --from-literal=OPENAI_API_KEY=$OPENAI_API_KEY

# Deploy services
kubectl apply -k deployments/scraper/
kubectl apply -k deployments/ranker/
kubectl apply -k deployments/generator/

# Check status
kubectl get cronjobs -n job-application
kubectl get pods -n job-application

# Trigger manual run
kubectl create job --from=cronjob/scraper scraper-manual -n job-application

# View logs
kubectl logs -f job/scraper-manual -n job-application
```

## Success Criteria

1. Scraper fetches 50+ jobs without errors
2. Ranker correctly categorizes jobs (review 10 manually)
3. Generator produces readable, relevant CVs and cover letters
4. PDFs render correctly with professional formatting
5. Kubernetes CronJobs execute on schedule
6. System runs for 24 hours without manual intervention

## Troubleshooting

### Scraper Issues
- Check Apify API token is valid
- Verify actor ID is correct
- Check MongoDB connection

### Ranker Issues
- Review template keywords
- Check OpenAI API key for translation
- Verify MongoDB indexes

### Generator Issues
- Check profile.yaml is configured
- Verify OpenAI API key
- Check WeasyPrint dependencies (fonts, pango)

### Kubernetes Issues
- Check secrets are created
- Verify image pull policy
- Check resource limits
