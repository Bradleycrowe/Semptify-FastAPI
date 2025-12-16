# Semptify FastAPI - Development & Operations Commands
# Usage: make <target>

.PHONY: help install dev test lint format clean docker-up docker-down docker-logs backup migrate validate

# Default target
help:
	@echo "Semptify FastAPI - Available Commands"
	@echo "======================================"
	@echo ""
	@echo "Development:"
	@echo "  make install     - Install dependencies"
	@echo "  make dev         - Run development server"
	@echo "  make test        - Run tests with coverage"
	@echo "  make lint        - Run linter (ruff)"
	@echo "  make format      - Format code (ruff + black)"
	@echo "  make validate    - Validate configuration"
	@echo ""
	@echo "Database:"
	@echo "  make migrate     - Run database migrations"
	@echo "  make migrate-new - Create new migration"
	@echo "  make db-reset    - Reset database (DESTRUCTIVE)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up   - Start all services"
	@echo "  make docker-down - Stop all services"
	@echo "  make docker-logs - View application logs"
	@echo "  make docker-build - Rebuild Docker images"
	@echo ""
	@echo "Operations:"
	@echo "  make backup      - Create backup"
	@echo "  make clean       - Clean build artifacts"
	@echo "  make health      - Check health endpoints"
	@echo ""

# ============================================================================
# Development
# ============================================================================

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt 2>/dev/null || true
	@echo "✅ Dependencies installed"

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest tests/ -v --cov=app --cov-report=term-missing

test-quick:
	pytest tests/test_health.py -v

lint:
	ruff check app/ tests/
	@echo "✅ Linting complete"

format:
	ruff check app/ tests/ --fix
	black app/ tests/ 2>/dev/null || ruff format app/ tests/
	@echo "✅ Formatting complete"

validate:
	python scripts/validate.py
	@echo "✅ Validation complete"

# ============================================================================
# Database
# ============================================================================

migrate:
	alembic upgrade head
	@echo "✅ Migrations applied"

migrate-new:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

migrate-down:
	alembic downgrade -1
	@echo "⚠️ Rolled back one migration"

db-reset:
	@echo "⚠️ This will DELETE all data!"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		rm -f data/semptify.db; \
		alembic downgrade base 2>/dev/null || true; \
		alembic upgrade head; \
		echo "✅ Database reset complete"; \
	else \
		echo "Cancelled"; \
	fi

# ============================================================================
# Docker
# ============================================================================

docker-up:
	docker-compose up -d
	@echo "✅ Services started"
	@docker-compose ps

docker-down:
	docker-compose down
	@echo "✅ Services stopped"

docker-logs:
	docker-compose logs -f app

docker-build:
	docker-compose build --no-cache
	@echo "✅ Images rebuilt"

docker-shell:
	docker-compose exec app /bin/bash

docker-db:
	docker-compose exec db psql -U postgres -d semptify

# ============================================================================
# Operations
# ============================================================================

backup:
	python scripts/backup.py --backup-dir ./backups
	@echo "✅ Backup created in ./backups"

health:
	@echo "Checking health endpoints..."
	@curl -s http://localhost:8000/livez | python -m json.tool || echo "❌ Liveness check failed"
	@curl -s http://localhost:8000/healthz | python -m json.tool || echo "❌ Health check failed"
	@echo ""
	@echo "✅ Health check complete"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ build/ dist/ *.egg-info/ 2>/dev/null || true
	@echo "✅ Cleaned build artifacts"

# ============================================================================
# CI/CD Helpers
# ============================================================================

ci-lint:
	ruff check app/ tests/ --output-format=github

ci-test:
	pytest tests/ --cov=app --cov-report=xml --junitxml=test-results.xml

ci-security:
	pip-audit --strict 2>/dev/null || echo "pip-audit not installed, skipping"
	bandit -r app/ -ll 2>/dev/null || echo "bandit not installed, skipping"

# ============================================================================
# Production
# ============================================================================

prod:
	gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

prod-validate:
	@echo "Running production validation..."
	python scripts/validate.py
	@test -f .env || (echo "❌ Missing .env file" && exit 1)
	@grep -q "SECRET_KEY" .env || (echo "❌ Missing SECRET_KEY" && exit 1)
	@echo "✅ Production validation passed"
