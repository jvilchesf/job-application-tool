# Unix Server Setup Instructions

Complete setup guide for deploying the Job Application Tool on a Unix server.

## Quick Start (Copy & Paste)

Run this entire block to set up everything automatically:

```bash
# =============================================================================
# FULL AUTOMATED SETUP - Run as a single block
# =============================================================================

set -e  # Exit on any error

echo "=== Installing system dependencies ==="

# Detect OS and install dependencies
if [ -f /etc/debian_version ]; then
    # Debian/Ubuntu
    sudo apt-get update
    sudo apt-get install -y \
        python3.12 python3.12-venv python3.12-dev \
        curl git docker.io docker-compose \
        libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
        libffi-dev libcairo2 libpangoft2-1.0-0 \
        fonts-dejavu-core
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker $USER
elif [ -f /etc/redhat-release ]; then
    # RHEL/CentOS/Fedora
    sudo dnf install -y \
        python3.12 python3.12-devel \
        curl git docker docker-compose \
        pango cairo gdk-pixbuf2 \
        dejavu-fonts-all
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker $USER
fi

echo "=== Installing uv (Python package manager) ==="
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"

echo "=== Installing kubectl ==="
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

echo "=== Installing kind (Kubernetes in Docker) ==="
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

echo "=== Installing k9s ==="
curl -sS https://webinstall.dev/k9s | bash
export PATH="$HOME/.local/bin:$PATH"

echo "=== Cloning repository ==="
cd ~
git clone https://github.com/jvilchesf/job-application-tool.git
cd job-application-tool

echo "=== Setting up Python environment ==="
uv sync

echo "=== Setting up PostgreSQL with Docker ==="
docker run -d \
    --name job-app-postgres \
    -e POSTGRES_PASSWORD=postgres123secure \
    -e POSTGRES_DB=jobapp \
    -p 5432:5432 \
    -v pgdata:/var/lib/postgresql/data \
    --restart unless-stopped \
    postgres:16-alpine

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to start..."
sleep 10

echo "=== Creating database schema ==="
docker exec -i job-app-postgres psql -U postgres -d jobapp << 'EOSQL'
-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    linkedin_id VARCHAR(255) UNIQUE,
    title VARCHAR(500) NOT NULL,
    company VARCHAR(500),
    location VARCHAR(500),
    description TEXT,
    url TEXT,
    apply_url TEXT,
    salary VARCHAR(255),
    employment_type VARCHAR(100),
    experience_level VARCHAR(100),
    posted_at TIMESTAMP WITH TIME ZONE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'scraped',
    llm_match_score INTEGER,
    llm_match_reasoning TEXT,
    generated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Applications table
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    job_title VARCHAR(500),
    company VARCHAR(500),
    resume_content TEXT,
    cover_letter_content TEXT,
    resume_path TEXT,
    cover_letter_path TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    notes TEXT,
    applied_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_jobs_linkedin_id ON jobs(linkedin_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_llm_score ON jobs(llm_match_score);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
EOSQL

echo "=== Creating .env file ==="
cat > .env << 'ENVFILE'
# =============================================================================
# Job Application Tool - Environment Configuration
# =============================================================================

# PostgreSQL Database
DATABASE_URL=postgresql://postgres:postgres123secure@localhost:5432/jobapp

# Apify Configuration (LinkedIn Jobs Scraper)
APIFY_API_TOKEN=your_apify_token_here
APIFY_ACTOR_ID=bebity~linkedin-jobs-scraper

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Resend Email Configuration
RESEND_API_KEY=your_resend_api_key_here
RESEND_FROM_EMAIL=jobs@yourdomain.com
RESEND_TO_EMAIL=your_email@example.com

# Scraper Settings
SCRAPER_JOB_TITLES=CISO,Security Manager,IT Security Manager,Head of Cyber Security
SCRAPER_LOCATION=Switzerland

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=text
ENVFILE

echo ""
echo "=============================================="
echo "Setup complete!"
echo "=============================================="
echo ""
echo "NEXT STEPS:"
echo "1. Edit .env file with your API keys:"
echo "   nano .env"
echo ""
echo "2. Required API keys:"
echo "   - APIFY_API_TOKEN: Get from https://apify.com/"
echo "   - OPENAI_API_KEY: Get from https://platform.openai.com/"
echo "   - RESEND_API_KEY: Get from https://resend.com/"
echo ""
echo "3. Run the pipeline:"
echo "   PYTHONPATH=src uv run python -m pipeline.main --titles 'CISO,Security Manager' --max-jobs 5 --dry-run"
echo ""
echo "4. Run with emails (after configuring .env):"
echo "   PYTHONPATH=src uv run python -m pipeline.main --titles 'CISO,Security Manager' --date-posted past-24h --max-jobs 10"
echo ""
```

---

## Manual Step-by-Step Setup

### 1. System Dependencies

#### Debian/Ubuntu:
```bash
sudo apt-get update
sudo apt-get install -y \
    python3.12 python3.12-venv python3.12-dev \
    curl git docker.io docker-compose \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 libpangoft2-1.0-0 \
    fonts-dejavu-core

sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker
```

#### RHEL/CentOS/Fedora:
```bash
sudo dnf install -y \
    python3.12 python3.12-devel \
    curl git docker docker-compose \
    pango cairo gdk-pixbuf2 \
    dejavu-fonts-all

sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Install uv (Python Package Manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

### 3. Install Kubernetes Tools (Optional)

```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# kind (Kubernetes in Docker)
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# k9s (Kubernetes TUI)
curl -sS https://webinstall.dev/k9s | bash
```

### 4. Clone Repository

```bash
git clone https://github.com/jvilchesf/job-application-tool.git
cd job-application-tool
```

### 5. Setup Python Environment

```bash
uv sync
```

### 6. Setup PostgreSQL Database

```bash
# Run PostgreSQL in Docker
docker run -d \
    --name job-app-postgres \
    -e POSTGRES_PASSWORD=postgres123secure \
    -e POSTGRES_DB=jobapp \
    -p 5432:5432 \
    -v pgdata:/var/lib/postgresql/data \
    --restart unless-stopped \
    postgres:16-alpine

# Wait for startup
sleep 10

# Create schema
docker exec -i job-app-postgres psql -U postgres -d jobapp < scripts/001_create_jobs_table.sql
```

### 7. Configure Environment

Create `.env` file:
```bash
cat > .env << 'EOF'
DATABASE_URL=postgresql://postgres:postgres123secure@localhost:5432/jobapp
APIFY_API_TOKEN=your_apify_token_here
OPENAI_API_KEY=your_openai_api_key_here
RESEND_API_KEY=your_resend_api_key_here
RESEND_FROM_EMAIL=jobs@yourdomain.com
RESEND_TO_EMAIL=your_email@example.com
SCRAPER_JOB_TITLES=CISO,Security Manager,IT Security Manager
SCRAPER_LOCATION=Switzerland
LOG_LEVEL=INFO
LOG_FORMAT=text
EOF
```

### 8. Test the Pipeline

```bash
# Dry run (no emails)
PYTHONPATH=src uv run python -m pipeline.main \
    --titles "CISO,Security Manager" \
    --date-posted past-24h \
    --max-jobs 5 \
    --dry-run

# Full run with emails
PYTHONPATH=src uv run python -m pipeline.main \
    --titles "CISO,Security Manager,IT Security Manager,Head of Cyber Security" \
    --date-posted past-24h \
    --max-hours-old 24 \
    --max-jobs 10
```

---

## Running as a Cron Job

Add to crontab for hourly runs:
```bash
crontab -e
```

Add this line:
```cron
0 * * * * cd ~/job-application-tool && PYTHONPATH=src ~/.local/bin/uv run python -m pipeline.main --titles "CISO,Security Manager,IT Security Manager" --date-posted past-24h --max-hours-old 2 --max-jobs 10 >> ~/job-app.log 2>&1
```

---

## Required API Keys

| Service | Purpose | Get from |
|---------|---------|----------|
| Apify | LinkedIn job scraping | https://apify.com/ |
| OpenAI | LLM matching & CV tailoring | https://platform.openai.com/ |
| Resend | Email delivery | https://resend.com/ |

---

## Useful Commands

```bash
# Check database
docker exec -it job-app-postgres psql -U postgres -d jobapp -c "SELECT COUNT(*) FROM jobs;"

# View logs
docker logs job-app-postgres

# Stop database
docker stop job-app-postgres

# Start database
docker start job-app-postgres

# View job stats
docker exec -it job-app-postgres psql -U postgres -d jobapp -c "SELECT status, COUNT(*) FROM jobs GROUP BY status;"
```
