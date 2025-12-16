# Semptify Production Deployment Guide

This guide covers deploying Semptify FastAPI to production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Docker Deployment](#docker-deployment)
4. [Manual Deployment](#manual-deployment)
5. [Database Setup](#database-setup)
6. [Security Checklist](#security-checklist)
7. [Monitoring & Logging](#monitoring--logging)
8. [Backup & Recovery](#backup--recovery)
9. [Scaling](#scaling)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **Python**: 3.11+ (3.12 recommended)
- **RAM**: Minimum 2GB, recommended 4GB+
- **Storage**: 10GB+ for application and uploads
- **OS**: Linux (Ubuntu 22.04+), Windows Server 2019+, or Docker

### Required Services

- **Database**: SQLite (development) or PostgreSQL 14+ (production)
- **Redis**: 7.0+ (optional, for sessions and caching)
- **AI Provider**: OpenAI API key or Azure OpenAI endpoint

---

## Environment Configuration

### Step 1: Create .env File

```bash
cp .env.example .env
```

### Step 2: Configure Required Variables

```env
# === CRITICAL: Generate a unique secret key ===
SECRET_KEY=your-unique-64-character-secret-key-here

# Application
APP_NAME=Semptify
APP_VERSION=5.0.0
ENVIRONMENT=production

# Security
SECURITY_MODE=enforced    # enforced = all security features active
DEBUG_MODE=false

# Database (PostgreSQL for production)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/semptify

# Redis (recommended for production)
REDIS_URL=redis://localhost:6379/0

# AI Provider (at least one required)
OPENAI_API_KEY=sk-your-openai-api-key
# Or Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-azure-openai-key

# CORS (production domains only)
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### Step 3: Generate SECRET_KEY

```bash
# Linux/Mac
openssl rand -hex 32

# Python
python -c "import secrets; print(secrets.token_hex(32))"

# PowerShell
-join ((1..32) | ForEach-Object { '{0:X2}' -f (Get-Random -Max 256) })
```

---

## Docker Deployment

### Quick Start

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f app
```

### Production docker-compose.yml

The included `docker-compose.yml` provides:
- **app**: Semptify FastAPI application
- **db**: PostgreSQL 16 with health checks
- **redis**: Redis 7 for sessions/caching

### Custom Configuration

```yaml
# Override for production
# docker-compose.override.yml
version: '3.9'
services:
  app:
    environment:
      - WORKERS=4
      - LOG_JSON_FORMAT=true
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

### Health Checks

```bash
# Liveness check (is the app running?)
curl http://localhost:8000/livez

# Readiness check (is the app ready to serve?)
curl http://localhost:8000/healthz

# Full health status
curl http://localhost:8000/api/health
```

---

## Manual Deployment

### Step 1: Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Initialize Database

```bash
# Run migrations
alembic upgrade head

# Or for fresh SQLite setup
python -c "from app.core.database import init_db; import asyncio; asyncio.run(init_db())"
```

### Step 4: Validate Configuration

```bash
python scripts/validate.py
```

### Step 5: Start Application

```bash
# Development
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Production with Gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## Database Setup

### PostgreSQL Setup

```sql
-- Create database and user
CREATE DATABASE semptify;
CREATE USER semptify_user WITH ENCRYPTED PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE semptify TO semptify_user;

-- Enable required extensions
\c semptify
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### Running Migrations

```bash
# Check current version
alembic current

# Upgrade to latest
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Generate new migration
alembic revision --autogenerate -m "description of changes"
```

### Connection Pooling

The application uses SQLAlchemy connection pooling:
- **PostgreSQL**: QueuePool with 5-20 connections
- **SQLite**: NullPool (single connection)

Configure in `.env`:
```env
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
```

---

## Security Checklist

### Pre-Deployment

- [ ] Generate unique `SECRET_KEY` (minimum 32 characters)
- [ ] Set `SECURITY_MODE=enforced`
- [ ] Set `DEBUG_MODE=false`
- [ ] Configure `CORS_ORIGINS` with specific domains (not `*`)
- [ ] Enable HTTPS only
- [ ] Set secure database password

### Application Security

- [ ] Rate limiting is active (60 req/min default)
- [ ] Security headers middleware enabled (CSP, HSTS, X-Frame-Options)
- [ ] Input validation active on all endpoints
- [ ] SQL injection protection via SQLAlchemy ORM

### Infrastructure Security

- [ ] Firewall configured (only ports 80, 443 exposed)
- [ ] Database not exposed to public internet
- [ ] Redis password authentication enabled
- [ ] Log files have restricted permissions
- [ ] Backup encryption enabled

### Verification

```bash
# Check security headers
curl -I https://yourdomain.com/healthz

# Expected headers:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block
# Referrer-Policy: strict-origin-when-cross-origin
# Content-Security-Policy: default-src 'self'...
# Strict-Transport-Security: max-age=31536000 (when HSTS enabled)
```

---

## Monitoring & Logging

### Structured Logging

Production uses JSON logging for easy parsing:

```env
LOG_LEVEL=INFO
LOG_JSON_FORMAT=true
```

Log format:
```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "message": "Request completed",
  "request_id": "abc-123",
  "method": "GET",
  "path": "/api/health",
  "status_code": 200,
  "duration_ms": 45
}
```

### Log Locations

- **Application logs**: `logs/semptify.log`
- **Docker logs**: `docker logs semptify-app`
- **Uvicorn access logs**: stdout

### Health Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /healthz` | Full health check | `{"status": "healthy", ...}` |
| `GET /livez` | Liveness probe | `{"status": "alive"}` |
| `GET /api/version` | Version info | `{"version": "5.0.0", ...}` |

### Recommended Monitoring

1. **Prometheus** + **Grafana** for metrics
2. **ELK Stack** (Elasticsearch, Logstash, Kibana) for logs
3. **Sentry** for error tracking
4. **Uptime monitoring** (Pingdom, UptimeRobot)

---

## Backup & Recovery

### Automated Backups

```bash
# Run backup script
python scripts/backup.py --backup-dir /path/to/backups

# Backup with custom retention
python scripts/backup.py --backup-dir /backups --keep 30
```

### What Gets Backed Up

1. **Database**: Full PostgreSQL dump or SQLite copy
2. **Uploads**: All user-uploaded files
3. **Configuration**: Non-sensitive .env backup

### Restore Process

```bash
# Restore from backup
python scripts/backup.py --restore /path/to/backup/backup_20240115_103000

# PostgreSQL restore
pg_restore -d semptify /path/to/backup/db_backup.dump
```

### Backup Schedule (Recommended)

| Type | Frequency | Retention |
|------|-----------|-----------|
| Database | Every 6 hours | 7 days |
| Full backup | Daily | 30 days |
| Weekly archive | Weekly | 90 days |

---

## Scaling

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
services:
  app:
    deploy:
      replicas: 3
```

### Load Balancing

Use nginx or Traefik as reverse proxy:

```nginx
upstream semptify {
    server app1:8000;
    server app2:8000;
    server app3:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://semptify;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Request-Id $request_id;
    }
}
```

### Database Scaling

For high traffic:
1. Use PostgreSQL read replicas
2. Increase connection pool size
3. Add Redis caching layer

---

## Troubleshooting

### Common Issues

#### Application Won't Start

```bash
# Check validation
python scripts/validate.py

# Common fixes:
# - Ensure .env exists with required variables
# - Check database connectivity
# - Verify AI provider credentials
```

#### Database Connection Errors

```bash
# Test PostgreSQL connection
psql -h localhost -U semptify_user -d semptify

# Check connection string format
# postgresql+asyncpg://user:pass@host:5432/dbname
```

#### Rate Limiting Issues

```bash
# Check current limits
curl -I http://localhost:8000/api/health

# Look for headers:
# X-RateLimit-Limit: 60
# X-RateLimit-Remaining: 59
# X-RateLimit-Reset: 1705315800
```

#### High Memory Usage

1. Reduce worker count: `WORKERS=2`
2. Lower connection pool: `DATABASE_POOL_SIZE=5`
3. Enable request timeouts (already configured)

### Useful Commands

```bash
# Check running processes
docker-compose ps

# View real-time logs
docker-compose logs -f app

# Restart application only
docker-compose restart app

# Full rebuild
docker-compose down && docker-compose up --build -d

# Database shell
docker-compose exec db psql -U postgres -d semptify

# Redis CLI
docker-compose exec redis redis-cli
```

### Getting Help

1. Check application logs: `logs/semptify.log`
2. Run validation: `python scripts/validate.py`
3. Health check: `curl http://localhost:8000/healthz`
4. GitHub Issues: https://github.com/Semptify/Semptify-FastAPI/issues

---

## Quick Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | auto-generated | JWT signing key |
| `DATABASE_URL` | Yes | sqlite | Database connection |
| `SECURITY_MODE` | No | development | Security level |
| `OPENAI_API_KEY` | Yes* | - | OpenAI API key |
| `REDIS_URL` | No | - | Redis connection |
| `CORS_ORIGINS` | No | localhost | Allowed origins |
| `LOG_LEVEL` | No | INFO | Log verbosity |
| `LOG_JSON_FORMAT` | No | false | JSON log output |

### Port Reference

| Service | Port | Purpose |
|---------|------|---------|
| App | 8000 | API server |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache/Sessions |

### API Documentation

- **OpenAPI Docs**: `http://localhost:8000/api/docs`
- **ReDoc**: `http://localhost:8000/api/redoc`
- **OpenAPI JSON**: `http://localhost:8000/api/openapi.json`
