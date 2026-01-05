# =============================================================================
# LinkedIn Job Application Tool - Makefile
# =============================================================================

.PHONY: install run-scraper run-ranker run-generator run-applicant \
        build deploy build-deploy test lint format clean help

# Default service for build/deploy commands
SERVICE ?= scraper

# -----------------------------------------------------------------------------
# Development Commands
# -----------------------------------------------------------------------------

## Install all dependencies
install:
	uv sync

## Install with dev dependencies
install-dev:
	uv sync --dev

# -----------------------------------------------------------------------------
# Run Services Locally
# -----------------------------------------------------------------------------

## Run scraper service (continuous daemon)
run-scraper:
	cd services/scraper/src && uv run python main.py

## Run ranker service
run-ranker:
	cd services/ranker/src && uv run python main.py

## Run generator service
run-generator:
	cd services/generator/src && uv run python main.py

## Run applicant service
run-applicant:
	cd services/applicant/src && uv run python main.py

# -----------------------------------------------------------------------------
# Docker Build Commands
# -----------------------------------------------------------------------------

## Build Docker image for a service (use SERVICE=<name>)
build:
	./scripts/build-and-push-image.sh $(SERVICE)

## Build all service images
build-all:
	./scripts/build-and-push-image.sh scraper
	./scripts/build-and-push-image.sh ranker
	./scripts/build-and-push-image.sh generator
	./scripts/build-and-push-image.sh applicant

# -----------------------------------------------------------------------------
# Kubernetes Deployment Commands
# -----------------------------------------------------------------------------

## Deploy a service to Kubernetes (use SERVICE=<name>)
deploy:
	./scripts/deploy.sh $(SERVICE)

## Deploy all services
deploy-all:
	./scripts/deploy.sh scraper
	./scripts/deploy.sh ranker
	./scripts/deploy.sh generator
	./scripts/deploy.sh applicant

## Build and deploy a service
build-deploy: build deploy

## Build and deploy all services
build-deploy-all: build-all deploy-all

# -----------------------------------------------------------------------------
# Database Commands
# -----------------------------------------------------------------------------

## Initialize MongoDB collections and indexes
init-db:
	./scripts/db/init_collections.sh

# -----------------------------------------------------------------------------
# Testing & Quality
# -----------------------------------------------------------------------------

## Run all tests
test:
	uv run pytest tests/ -v

## Run tests for a specific service
test-service:
	uv run pytest tests/$(SERVICE)/ -v

## Run linting
lint:
	uv run ruff check .

## Run auto-formatting
format:
	uv run ruff format .
	uv run ruff check --fix .

# -----------------------------------------------------------------------------
# Utility Commands
# -----------------------------------------------------------------------------

## Clean build artifacts and caches
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ .coverage htmlcov/

## Show project structure
tree:
	tree -I '__pycache__|.git|.venv|node_modules' -L 3

# -----------------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------------

## Show this help message
help:
	@echo "LinkedIn Job Application Tool - Available Commands"
	@echo "=================================================="
	@echo ""
	@echo "Development:"
	@echo "  make install          - Install dependencies"
	@echo "  make install-dev      - Install with dev dependencies"
	@echo ""
	@echo "Run Services:"
	@echo "  make run-scraper      - Run scraper (continuous daemon)"
	@echo "  make run-ranker       - Run ranker service"
	@echo "  make run-generator    - Run generator service"
	@echo "  make run-applicant    - Run applicant service"
	@echo ""
	@echo "Docker:"
	@echo "  make build SERVICE=x  - Build Docker image for service x"
	@echo "  make build-all        - Build all service images"
	@echo ""
	@echo "Kubernetes:"
	@echo "  make deploy SERVICE=x - Deploy service x to K8s"
	@echo "  make deploy-all       - Deploy all services"
	@echo "  make build-deploy     - Build and deploy SERVICE"
	@echo ""
	@echo "Database:"
	@echo "  make init-db          - Initialize MongoDB collections"
	@echo ""
	@echo "Quality:"
	@echo "  make test             - Run all tests"
	@echo "  make lint             - Run linting"
	@echo "  make format           - Auto-format code"
	@echo ""
	@echo "Utility:"
	@echo "  make clean            - Clean build artifacts"
	@echo "  make tree             - Show project structure"
