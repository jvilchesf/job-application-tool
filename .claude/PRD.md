# Product Requirements Document: LinkedIn Job Application Tool

## Executive Summary

The LinkedIn Job Application Tool is an automated job application pipeline that scrapes LinkedIn job postings via Apify API, ranks them using template-based keyword matching, and generates tailored CVs and cover letters using LLM. The system is designed as a microservices architecture with four independent services (Scraper, Ranker, Generator, Applicant) communicating through a shared MongoDB database.

The core innovation lies in combining automated job discovery with intelligent filtering and personalized document generation. Instead of manually searching and applying to jobs, users configure their preferences once and the system continuously finds, evaluates, and prepares applications for matching positions.

## Mission

**Automate the job search and application process to help professionals find and apply to relevant positions efficiently, with tailored application materials that highlight their most relevant experience.**

### Core Principles

1. **Relevance First**: Template-based scoring ensures only truly matching jobs proceed to application generation
2. **Personalization**: LLM-generated CVs and cover letters are tailored to each specific job posting
3. **Transparency**: Users can see exactly why jobs were qualified/disqualified and review all generated materials
4. **Modularity**: Each service operates independently, allowing selective deployment and easy maintenance
5. **Cost Efficiency**: Use Apify for scraping (avoid browser automation complexity) and OpenAI for generation

## Target Users

### Primary User Persona: Job Seeker in Tech

**Profile:**
- Software engineers, security professionals, DevOps engineers
- Currently employed but passively looking for opportunities
- Limited time to manually search and apply to jobs
- Located in Switzerland or similar competitive job markets

**Technical Comfort Level:**
- Can run Python scripts and Docker containers
- Comfortable with environment variables and YAML configuration
- Has access to Kubernetes cluster (Kind) for deployment
- Familiar with MongoDB basics

**Key Needs:**
- Automated discovery of relevant job postings
- Filtering based on specific technical skills and preferences
- Personalized application materials without manual rewriting
- Track application status across multiple positions

**Pain Points:**
- Manually searching LinkedIn daily is time-consuming
- Generic CVs don't highlight relevant experience for each role
- Writing cover letters for each application is tedious
- Missing good opportunities due to delayed discovery

## MVP Scope

### In Scope: Core Functionality

**Scraper Service**
- [x] Apify API integration for LinkedIn job scraping
- [x] Configurable search URL and job limits
- [x] Job deduplication by LinkedIn ID
- [x] Scheduled execution (CronJob)
- [x] MongoDB storage with proper schema

**Ranker Service**
- [x] Template-based keyword scoring
- [x] Trigger keywords (high-value matches)
- [x] Support keywords (supporting matches)
- [x] Negative keywords (disqualifiers)
- [x] LLM-based translation for non-English descriptions
- [x] Configurable score thresholds

**Generator Service**
- [x] LLM-powered resume generation
- [x] LLM-powered cover letter generation
- [x] PDF generation using WeasyPrint
- [x] Profile-based personalization from YAML config
- [x] Keyword incorporation from ranking results

**Infrastructure**
- [x] MongoDB database with collections and indexes
- [x] Docker containers for each service
- [x] Kubernetes deployments with Kustomize
- [x] Environment-based configuration
- [x] Makefile for common operations

### Out of Scope: Future Enhancements

**Applicant Service (Phase 2)**
- [ ] LinkedIn Easy Apply automation
- [ ] Company website form filling
- [ ] Email-based applications
- [ ] Application status tracking

**Advanced Features**
- [ ] Web-based dashboard UI
- [ ] Multiple profile support
- [ ] A/B testing for CV variations
- [ ] Interview scheduling integration
- [ ] Salary data aggregation
- [ ] Company research integration

## Technical Architecture

### Services Overview

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   SCRAPER    │───▶│    RANKER    │───▶│  GENERATOR   │───▶│  APPLICANT   │
│              │    │              │    │              │    │              │
│ Apify API    │    │ Template     │    │ LLM Resume   │    │ Future       │
│ LinkedIn     │    │ Scoring      │    │ LLM Cover    │    │ Auto-apply   │
│ Normalize    │    │ Translate    │    │ PDF Build    │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │
       └───────────────────┴───────────────────┴───────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │     MongoDB      │
                          │                  │
                          │ jobs collection  │
                          │ applications     │
                          └──────────────────┘
```

### Data Flow

1. **Scraper** runs every 6 hours, fetches jobs from LinkedIn via Apify, stores with status `scraped`
2. **Ranker** runs every 2 hours, processes `scraped` jobs, updates to `qualified` or `disqualified`
3. **Generator** runs every 3 hours, processes `qualified` jobs, creates applications, updates to `generated`
4. **Applicant** (future) will process `generated` jobs, submit applications, update to `applied`

### Job Status Flow

```
scraped → qualified → generated → applied
    ↓         ↓           ↓          ↓
disqualified  error     error     rejected/interview
```

## Environment Variables

### Required Configuration

| Variable | Description | Service |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | All |
| `MONGODB_DATABASE` | Database name | All |
| `APIFY_API_TOKEN` | Apify API authentication | Scraper |
| `APIFY_ACTOR_ID` | LinkedIn scraper actor ID | Scraper |
| `OPENAI_API_KEY` | OpenAI API authentication | Ranker, Generator |
| `OPENAI_MODEL` | Model for generation (gpt-4o) | Generator |
| `OPENAI_MODEL_MINI` | Model for translation (gpt-4o-mini) | Ranker |

### Optional Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SCRAPER_SEARCH_URL` | LinkedIn search URL | Security Engineer Switzerland |
| `SCRAPER_MAX_JOBS` | Maximum jobs per scrape | 100 |
| `SCRAPER_INTERVAL_HOURS` | Scrape frequency | 6 |
| `RANKER_MIN_SCORE` | Minimum score to qualify | 30 |
| `RANKER_MIN_TRIGGERS` | Minimum trigger matches | 2 |
| `LOG_LEVEL` | Logging verbosity | INFO |
| `LOG_FORMAT` | Log format (json/text) | json |

## Database Schema

### Jobs Collection

```javascript
{
  _id: ObjectId,
  linkedin_id: string,        // Unique LinkedIn job ID
  url: string,                // Job posting URL
  title: string,              // Job title
  company: string,            // Company name
  location: string,           // Job location
  description: string,        // Full job description
  description_translated: string,  // Translated description (if applicable)
  salary: string,             // Salary information (if available)
  employment_type: string,    // Full-time, Part-time, Contract
  experience_level: string,   // Entry, Mid, Senior
  posted_date: Date,          // When job was posted
  apply_url: string,          // Direct application URL

  // Ranking data
  score: int,                 // Total ranking score
  matched_triggers: [string], // Matched trigger keywords
  matched_support: [string],  // Matched support keywords

  // Status tracking
  status: enum,               // scraped, qualified, disqualified, generated, applied, error
  ranked_at: Date,
  generated_at: Date,
  applied_at: Date,
  error: string,              // Error message if status is error

  // Timestamps
  created_at: Date,
  updated_at: Date
}
```

### Applications Collection

```javascript
{
  _id: ObjectId,
  job_id: string,             // Reference to jobs collection
  job_title: string,          // Denormalized for display
  company: string,            // Denormalized for display

  // Generated content
  resume_content: string,     // Resume in markdown
  cover_letter_content: string,  // Cover letter text
  resume_path: string,        // Path to PDF file
  cover_letter_path: string,  // Path to PDF file

  // Status
  status: enum,               // pending, submitted, failed, withdrawn
  submitted_at: Date,
  response_received_at: Date,
  notes: string,

  // Timestamps
  created_at: Date,
  updated_at: Date
}
```

## Scoring Algorithm

### Template Structure

```yaml
templates:
  security_engineer:
    trigger_keywords:      # High-value matches (+10 points each)
      - "security engineer"
      - "cybersecurity"
      - "SIEM"
    support_keywords:      # Supporting matches (+4 points each)
      - "Python"
      - "AWS"
    negative_keywords:     # Disqualifiers (-15 points each)
      - "senior manager"
```

### Scoring Logic

1. Match trigger keywords in title and description
2. Title matches get 1.5x bonus
3. Match support keywords
4. Match negative keywords (subtract from score)
5. Calculate total: `trigger_score + support_score + negative_score`
6. Job qualifies if: `trigger_hits >= 2 AND total_score >= 30`

## File Structure

```
job-application-tool/
├── .claude/                  # Claude Code context
│   ├── PRD.md               # This document
│   ├── plans/               # Development phase plans
│   ├── commands/            # Custom Claude commands
│   └── reference/           # Technical references
├── src/
│   ├── shared/              # Shared utilities
│   │   ├── config.py        # Pydantic settings
│   │   ├── database.py      # MongoDB operations
│   │   └── models.py        # Pydantic models
│   ├── scraper/             # Scraper service
│   │   ├── apify_client.py  # Apify API client
│   │   └── main.py          # CLI entry point
│   ├── ranker/              # Ranker service
│   │   ├── templates.py     # Template matching
│   │   ├── translator.py    # LLM translation
│   │   └── main.py          # CLI entry point
│   ├── generator/           # Generator service
│   │   ├── profile.py       # Profile loader
│   │   ├── llm.py           # LLM generation
│   │   ├── pdf.py           # PDF generation
│   │   └── main.py          # CLI entry point
│   └── applicant/           # Applicant service (future)
│       └── main.py          # Placeholder
├── config/
│   ├── profile.yaml         # User professional profile
│   └── templates.yaml       # Scoring templates
├── deployments/             # Kubernetes manifests
│   ├── scraper/
│   ├── ranker/
│   ├── generator/
│   └── applicant/
├── docker/                  # Dockerfiles
├── scripts/                 # Utility scripts
│   └── db/                  # Database scripts
├── .env.example
├── pyproject.toml
├── Makefile
└── README.md
```

## Success Metrics

### MVP Success Criteria

1. **Scraper**: Successfully fetches and stores 50+ unique jobs per run
2. **Ranker**: Correctly qualifies/disqualifies jobs based on template criteria
3. **Generator**: Produces coherent, job-specific CVs and cover letters
4. **System**: Runs autonomously for 1 week without manual intervention

### Future Metrics

- Application submission success rate
- Interview conversion rate
- Time saved vs manual application process
- Cost per application (API usage)
