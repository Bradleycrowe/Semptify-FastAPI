# Semptify 5.0

Tenant rights protection platform - rebuilt with async-first FastAPI architecture.

## Core Promise

**Help tenants with tools and information to uphold tenant rights as a renter, in court if it goes that far - hopefully it won't.**

## 🔐 Storage-Based Authentication

Semptify 5.0 introduces a unique authentication model: **your cloud storage IS your identity**.

### How It Works

1. **Connect Your Storage**: Click "Connect with Google Drive" (or Dropbox/OneDrive)
2. **Authorize Semptify**: Grant access to a private app folder in your storage
3. **Automatic Token**: An encrypted auth token is stored in your storage (`.semptify/auth_token.enc`)
4. **You're In**: If you can access your storage, you're authenticated

### Why Storage-Based Auth?

- **No Passwords**: Can't forget what doesn't exist
- **No Email Verification**: Your storage account already verified you
- **Portable Identity**: Your identity travels with your data
- **Privacy First**: We never store your data on our servers - it lives in YOUR storage
- **Self-Custody**: You own your data, including your auth token

### Supported Storage Providers

| Provider | Status | Features |
|----------|--------|----------|
| Google Drive | ✅ Ready | OAuth2, app folder isolation |
| Dropbox | ✅ Ready | OAuth2, app folder isolation |
| OneDrive | ✅ Ready | OAuth2, app folder isolation |
| Cloudflare R2 | ⚙️ System Only | Admin/internal storage only |

## Quick Start

```powershell
# 1. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment template and configure OAuth credentials
Copy-Item .env.template .env
# Edit .env with your OAuth client IDs/secrets

# 4. Run development server
python -m uvicorn app.main:app --reload --port 8000
```

## API Documentation

When running in debug mode, visit:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Project Structure

```
Semptify-FastAPI/
├── app/
│   ├── main.py              # FastAPI application entry
│   ├── core/
│   │   ├── config.py        # Pydantic settings
│   │   ├── security.py      # Storage-based auth, rate limiting
│   │   └── database.py      # Async SQLAlchemy
│   ├── routers/
│   │   ├── storage.py       # /storage/* - OAuth flows, auth
│   │   ├── vault.py         # /api/vault/* - documents in user storage
│   │   ├── timeline.py      # /api/timeline/*
│   │   ├── calendar.py      # /api/calendar/*
│   │   ├── copilot.py       # /api/copilot/*
│   │   └── health.py        # /healthz, /readyz, /metrics
│   ├── models/
│   │   └── models.py        # SQLAlchemy ORM models
│   └── services/
│       └── storage/         # Cloud storage providers
│           ├── base.py      # StorageProvider interface
│           ├── google_drive.py
│           ├── dropbox.py
│           ├── onedrive.py
│           └── r2.py        # Cloudflare R2 (system only)
├── tests/
├── requirements.txt
├── .env.template
└── README.md
```

## API Endpoints

### Health & Monitoring
- `GET /healthz` - Health check
- `GET /readyz` - Readiness check
- `GET /metrics` - Prometheus metrics

### Storage Authentication (NEW in 5.0)
- `GET /storage/providers` - List available storage providers
- `GET /storage/auth/{provider}` - Start OAuth flow
- `GET /storage/callback/{provider}` - OAuth callback
- `GET /storage/session` - Get current session
- `POST /storage/verify` - Verify storage token
- `POST /storage/logout` - End session

### Document Vault (Cloud Storage)
- `POST /api/vault/upload` - Upload to user's cloud storage
- `GET /api/vault/` - List documents from user's storage
- `GET /api/vault/{id}/download` - Download from user's storage
- `GET /api/vault/{id}/certificate` - Get certification
- `DELETE /api/vault/{id}` - Delete from user's storage

### Timeline
- `POST /api/timeline/` - Create event
- `GET /api/timeline/` - List events
- `GET /api/timeline/{id}` - Get event

### Calendar
- `POST /api/calendar/` - Create event/deadline
- `GET /api/calendar/` - List events
- `GET /api/calendar/upcoming` - Upcoming deadlines

### AI Copilot
- `GET /api/copilot/status` - Check AI availability
- `POST /api/copilot/` - Ask a question

## Authentication Flow

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   User      │         │  Semptify   │         │   Storage   │
│   Browser   │         │   Server    │         │   Provider  │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │ 1. Click "Connect"    │                       │
       ├──────────────────────>│                       │
       │                       │                       │
       │ 2. Redirect to OAuth  │                       │
       │<──────────────────────┤                       │
       │                       │                       │
       │ 3. Authorize app      │                       │
       ├───────────────────────┼──────────────────────>│
       │                       │                       │
       │ 4. Callback with code │                       │
       ├──────────────────────>│                       │
       │                       │                       │
       │                       │ 5. Exchange code      │
       │                       ├──────────────────────>│
       │                       │                       │
       │                       │ 6. Get user info      │
       │                       ├──────────────────────>│
       │                       │                       │
       │                       │ 7. Store encrypted    │
       │                       │    token in storage   │
       │                       ├──────────────────────>│
       │                       │                       │
       │ 8. Set session cookie │                       │
       │<──────────────────────┤                       │
       │                       │                       │
       │ 9. Access protected   │                       │
       │    resources          │                       │
       ├──────────────────────>│                       │
```

## Security Modes

- **`open`**: Development mode - auth checks are bypassed
- **`enforced`**: Production mode - full storage auth required

Set via `SECURITY_MODE` environment variable.

## AI Copilot Providers

Configure `AI_PROVIDER` environment variable:
- `openai` - OpenAI API (requires `OPENAI_API_KEY`)
- `azure` - Azure OpenAI (requires Azure credentials)
- `ollama` - Local Ollama server
- `none` - Disabled

## Running Tests

```powershell
pytest -v
```

## Production Deployment

```powershell
# Using Gunicorn with Uvicorn workers
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Design Principles

1. **Storage = Identity**: Your cloud storage proves who you are
2. **User-Owned Data**: All documents live in USER's storage, not ours
3. **Async-first**: All I/O uses async/await
4. **Type safety**: Pydantic models everywhere
5. **Zero Knowledge**: We can't see your data - it's encrypted in your storage

## Migration from Flask

This is a complete rewrite of Semptify, not a port. The Flask version remains at `../Semptify/` for reference.

Key improvements:
- **Storage-based auth** (no passwords, no email verification)
- **User-owned data** (documents in user's cloud storage)
- Async I/O (non-blocking AI calls, database queries)
- Type-safe API with Pydantic validation
- Auto-generated API documentation
- Cleaner project structure

## Architecture Comparison

| Aspect | Flask (4.x) | FastAPI (5.0) |
|--------|-------------|---------------|
| Authentication | Anonymous tokens in local JSON | Storage-based OAuth2 |
| Document Storage | Local filesystem | User's cloud storage |
| User Data | Server-side | User-owned (self-custody) |
| Database | SQLite (sync) | SQLite/Postgres (async) |
| API Docs | Manual | Auto-generated OpenAPI |
| Type Safety | None | Pydantic everywhere |
