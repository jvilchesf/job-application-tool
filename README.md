# LinkedIn Job Application Tool

Automated LinkedIn job application pipeline that scrapes job postings, ranks them based on keyword matching, and generates tailored CVs and cover letters using LLM.

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   SCRAPER    │───▶│    RANKER    │───▶│  GENERATOR   │───▶│  APPLICANT   │
│              │    │              │    │              │    │              │
│ Apify API    │    │ Template     │    │ LLM Resume   │    │ Future       │
│ LinkedIn     │    │ Scoring      │    │ LLM Cover    │    │ Auto-apply   │
│ Normalize    │    │ Translate    │    │ PDF Build    │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │     MongoDB      │
                    │                  │
                    │ jobs collection  │
                    │ applications     │
                    └──────────────────┘
```

## Services

### Scraper
Fetches LinkedIn job postings using [Apify](https://apify.com/) LinkedIn Jobs Scraper API.
- Runs on configurable schedule (default: every 6 hours)
- Normalizes job data and stores in MongoDB
- Deduplicates jobs by LinkedIn ID

### Ranker
Scores jobs using template-based keyword matching.
- Configurable trigger and support keywords
- Translates non-English job descriptions using OpenAI
- Marks jobs as `qualified` or `disqualified` based on score thresholds

### Generator
Creates tailored resumes and cover letters for qualified jobs.
- Uses OpenAI GPT-4o for content generation
- Generates PDF documents using WeasyPrint
- Stores generated content in MongoDB

### Applicant (Future)
Placeholder for automated job application submission.

## Project Structure

```
job-application-tool/
├── src/
│   ├── shared/           # Shared utilities, config, database, models
│   ├── scraper/          # Apify LinkedIn scraper service
│   ├── ranker/           # Template-based job scoring
│   ├── generator/        # CV and cover letter generation
│   └── applicant/        # Future auto-apply service
├── config/
│   ├── profile.yaml      # Your professional profile
│   └── templates.yaml    # Job scoring templates
├── deployments/
│   ├── scraper/          # Kubernetes manifests for scraper
│   ├── ranker/           # Kubernetes manifests for ranker
│   ├── generator/        # Kubernetes manifests for generator
│   └── applicant/        # Kubernetes manifests for applicant
├── docker/
│   ├── Dockerfile.scraper
│   ├── Dockerfile.ranker
│   ├── Dockerfile.generator
│   └── Dockerfile.applicant
├── scripts/
│   ├── build-and-push-image.sh
│   ├── deploy.sh
│   └── db/
│       └── init_mongodb.js
├── .env.example
├── pyproject.toml
└── Makefile
```

## Quick Start

### Prerequisites
- Python 3.12+
- Docker
- MongoDB (local or container)
- Apify API token
- OpenAI API key

### 1. Clone and Setup

```bash
git clone git@github.com:jvilchesf/job-application-tool.git
cd job-application-tool

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your API keys
# Required:
#   - APIFY_API_TOKEN
#   - OPENAI_API_KEY
#   - MONGODB_URI
```

### 3. Start MongoDB

```bash
# Using Docker
docker run -d --name mongodb -p 27017:27017 -v mongodb_data:/data/db mongo:7

# Initialize collections and indexes
docker exec -i mongodb mongosh < scripts/db/init_mongodb.js
```

### 4. Configure Your Profile

Edit `config/profile.yaml` with your professional information:
- Personal details
- Work experience
- Education
- Skills and certifications

### 5. Configure Scoring Templates

Edit `config/templates.yaml` to define job matching criteria:
- Trigger keywords (high-value matches)
- Support keywords (supporting matches)
- Negative keywords (disqualifiers)

### 6. Run Services Locally

```bash
# Run scraper (one-time)
make run-scraper

# Run ranker
make run-ranker

# Run generator
make run-generator
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name | `job_application` |
| `APIFY_API_TOKEN` | Apify API token | Required |
| `APIFY_ACTOR_ID` | LinkedIn scraper actor ID | `KfYqwOhOXqkqO4DF8` |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | Model for generation | `gpt-4o` |
| `SCRAPER_SEARCH_URL` | LinkedIn search URL | See .env.example |
| `SCRAPER_MAX_JOBS` | Max jobs per scrape | `100` |
| `RANKER_MIN_SCORE` | Minimum score to qualify | `30` |
| `RANKER_MIN_TRIGGERS` | Minimum trigger matches | `2` |

### Scoring Templates

Templates define how jobs are scored:

```yaml
templates:
  security_engineer:
    trigger_keywords:
      - "security engineer"
      - "cybersecurity"
      - "SIEM"
    support_keywords:
      - "Python"
      - "AWS"
      - "Kubernetes"
    negative_keywords:
      - "senior manager"
      - "director"
    trigger_weight: 10
    support_weight: 4
    negative_weight: -15
```

**Scoring Logic:**
- Each trigger keyword match: +10 points (1.5x bonus in title)
- Each support keyword match: +4 points
- Each negative keyword match: -15 points
- Job qualifies if: `trigger_hits >= 2 AND total_score >= 30`

## Kubernetes Deployment

### Build and Deploy

```bash
# Build Docker image for a service
make build SERVICE=scraper

# Deploy to Kubernetes
make deploy SERVICE=scraper

# Build and deploy all services
make build-deploy SERVICE=scraper
make build-deploy SERVICE=ranker
make build-deploy SERVICE=generator
```

### Create Secrets

```bash
kubectl create namespace job-application

kubectl create secret generic job-application-secrets \
  --namespace job-application \
  --from-literal=APIFY_API_TOKEN=your_token \
  --from-literal=OPENAI_API_KEY=your_key
```

## Database Schema

### Jobs Collection

| Field | Type | Description |
|-------|------|-------------|
| `linkedin_id` | string | Unique LinkedIn job ID |
| `title` | string | Job title |
| `company` | string | Company name |
| `location` | string | Job location |
| `description` | string | Job description |
| `status` | enum | `scraped`, `qualified`, `disqualified`, `generated`, `applied` |
| `score` | int | Ranking score |
| `matched_triggers` | array | Matched trigger keywords |
| `matched_support` | array | Matched support keywords |

### Applications Collection

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | string | Reference to job |
| `resume_content` | string | Generated resume (markdown) |
| `cover_letter_content` | string | Generated cover letter |
| `resume_path` | string | Path to PDF |
| `status` | enum | `pending`, `submitted`, `failed` |

## Makefile Commands

```bash
make run-scraper      # Run scraper locally
make run-ranker       # Run ranker locally
make run-generator    # Run generator locally

make build SERVICE=x  # Build Docker image
make deploy SERVICE=x # Deploy to Kubernetes
make build-deploy     # Build and deploy

make test             # Run tests
make lint             # Run linter
make format           # Format code
```

## License

MIT
