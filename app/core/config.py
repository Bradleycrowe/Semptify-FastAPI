"""
Semptify Configuration
Pydantic Settings for environment-based configuration.
Single source of truth for all app settings.
"""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Use .env file for local development, env vars for production.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )    # ==========================================================================
    # App Identity
    # ==========================================================================
    app_name: str = "Semptify"
    app_version: str = "5.0.0"
    app_description: str = """
## Semptify - Tenant Rights Protection Platform

**FastAPI Edition v5.0** - Zero-knowledge architecture with storage-based authentication.

### Core Mission
Help tenants with tools and information to uphold tenant rights, in court if it goes that far - hopefully it won't.

### Key Features
- 📄 **Document Vault** - Secure, certified document storage with SHA-256 hashing
- ⏰ **Timeline** - Chronological evidence tracking for court preparation  
- 📅 **Calendar** - Deadline management with urgency-based reminders
- 🤖 **AI Copilot** - Tenant rights guidance powered by AI
- 🔴 **Intensity Engine** - Urgency scoring (0-100) based on deadlines and severity
- 🏛️ **Dakota County Module** - Eviction defense forms (EN/ES/SO/AR)

### Authentication
Storage-based authentication using OAuth2 with Google Drive, Dropbox, or OneDrive.
Your data lives in YOUR cloud storage - we never store your files.

### Security Modes
- `open`: Development/testing mode (no auth required)
- `enforced`: Production mode (storage auth required)
"""
    debug: bool = False
    enable_docs: bool = True  # Enable OpenAPI docs (set False in sensitive deployments)
    
    # ==========================================================================
    # Server
    # ==========================================================================
    host: str = "0.0.0.0"
    port: int = 8000
    
    # ==========================================================================
    # Security Mode: "enforced" for production, "open" for testing/development
    # ==========================================================================
    security_mode: Literal["enforced", "open"] = "enforced"
    secret_key: str = ""  # Will be auto-generated if not set
    
    @field_validator("secret_key", mode="before")
    @classmethod
    def generate_secret_key_if_empty(cls, v: str) -> str:
        """Generate a secure secret key if not provided."""
        import secrets
        import os
        if not v or v == "change-me-in-production-use-secrets":
            # Check environment variable directly
            env_key = os.getenv("SECRET_KEY", "")
            if env_key and env_key != "change-me-in-production-use-secrets":
                return env_key
            # Generate a secure random key
            generated = secrets.token_urlsafe(64)
            print(f"⚠️  WARNING: No SECRET_KEY set. Generated temporary key for this session.")
            print(f"   For production, set SECRET_KEY in your .env file:")
            print(f"   SECRET_KEY={generated}")
            return generated
        return v
    
    # Token settings
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    user_token_length: int = 12  # Anonymous user token length
    
    # Rate limiting
    rate_limit_window: int = 60  # seconds
    rate_limit_max_requests: int = 100
    admin_rate_limit_window: int = 60
    admin_rate_limit_max_requests: int = 20
    
    # ==========================================================================
    # Session Storage
    # ==========================================================================
    # Redis URL for session storage (production). Leave empty for in-memory.
    # Example: redis://localhost:6379 or redis://:password@host:6379/0
    redis_url: str = ""
    session_ttl_hours: int = 24  # Session expiry time
    
    # ==========================================================================
    # Database
    # ==========================================================================
    # PostgreSQL (production) - Set DATABASE_URL in .env
    # Example: DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
    database_url: str = "sqlite+aiosqlite:///./semptify.db"
    # For SQLite (dev fallback): "sqlite+aiosqlite:///./semptify.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def convert_to_async_driver(cls, v: str) -> str:
        """
        Automatically convert database URLs to use async drivers.
        Render.com and other providers use postgresql:// but we need postgresql+asyncpg://
        """
        if v and isinstance(v, str):
            # Convert PostgreSQL to asyncpg
            if v.startswith("postgresql://") or v.startswith("postgres://"):
                # Replace postgresql:// or postgres:// with postgresql+asyncpg://
                if v.startswith("postgres://"):
                    v = v.replace("postgres://", "postgresql+asyncpg://", 1)
                else:
                    v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            # Convert SQLite to aiosqlite if not already
            elif v.startswith("sqlite://") and "+aiosqlite" not in v:
                v = v.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return v

    # ==========================================================================
    # File Storage
    # ==========================================================================
    upload_dir: str = "uploads"
    vault_dir: str = "uploads/vault"
    max_upload_size_mb: int = 50
    allowed_extensions: str = "pdf,png,jpg,jpeg,gif,doc,docx,txt,mp3,mp4,wav"
    
    # ==========================================================================
    # AI Provider Configuration
    # ==========================================================================
    ai_provider: Literal["openai", "azure", "ollama", "groq", "anthropic", "gemini", "none"] = "anthropic"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Groq (fast & affordable - FREE tier available)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Anthropic Claude (best accuracy)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Google Gemini (FREE tier: 1,500 requests/day)
    gemini_api_key: str = ""
    google_ai_api_key: str = ""  # Alias for gemini_api_key
    gemini_model: str = "gemini-1.5-flash"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    
    # Ollama (local - 100% FREE)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2:0.5b"
    
    # ==========================================================================
    # External Services
    # ==========================================================================
    github_token: str = ""

    # ==========================================================================
    # Cloud Storage Providers (OAuth2)
    # ==========================================================================
    # Google Drive
    google_drive_client_id: str = ""
    google_drive_client_secret: str = ""

    # Dropbox
    dropbox_app_key: str = ""
    dropbox_app_secret: str = ""

    # OneDrive (Microsoft)
    onedrive_client_id: str = ""
    onedrive_client_secret: str = ""

    # Cloudflare R2 (System storage only)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "semptify-system"
    r2_endpoint: str = ""  # e.g., https://<account_id>.r2.cloudflarestorage.com
    r2_api_token: str = ""  # Cloudflare API token for R2 management

    # ==========================================================================
    # Azure AI Services (Document Intelligence + OpenAI)
    # ==========================================================================
    azure_ai_endpoint: str = ""
    azure_ai_key1: str = ""
    azure_ai_key2: str = ""
    azure_ai_region: str = "eastus"

    # ==========================================================================
    # Observability
    # ==========================================================================
    log_level: str = "INFO"
    log_json_format: bool = False
    enable_metrics: bool = True

    # ==========================================================================
    # Chat Console Auto-Allow Settings
    # ==========================================================================
    session_duration_hours: int = 6
    auto_allow_timeout_ms: int = 500
    auto_allow_enabled: bool = True
    
    # ==========================================================================
    # Deployment
    # ==========================================================================
    cors_origins: str = ""  # Comma-separated list of allowed origins. Leave empty for secure defaults.
    
    @property
    def cors_origins_list(self) -> list[str]:
        """
        Parse CORS origins into a list with secure defaults.
        - If explicit origins set: use those
        - If empty: restrict to localhost only
        """
        if self.cors_origins:
            if self.cors_origins == "*":
                return ["*"]
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        
        # Secure defaults - localhost only (user must configure explicit origins)
        return [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",  # Common frontend dev port
            "http://127.0.0.1:3000",
        ]

    @property
    def allowed_extensions_set(self) -> set[str]:
        """Parse allowed extensions into a set."""
        return {ext.strip().lower() for ext in self.allowed_extensions.split(",")}

    # Aliases for storage router compatibility
    @property
    def GOOGLE_DRIVE_CLIENT_ID(self) -> str:
        return self.google_drive_client_id

    @property
    def GOOGLE_DRIVE_CLIENT_SECRET(self) -> str:
        return self.google_drive_client_secret

    @property
    def DROPBOX_APP_KEY(self) -> str:
        return self.dropbox_app_key

    @property
    def DROPBOX_APP_SECRET(self) -> str:
        return self.dropbox_app_secret

    @property
    def ONEDRIVE_CLIENT_ID(self) -> str:
        return self.onedrive_client_id

    @property
    def ONEDRIVE_CLIENT_SECRET(self) -> str:
        return self.onedrive_client_secret

    @property
    def SECRET_KEY(self) -> str:
        return self.secret_key
@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Use dependency injection: Depends(get_settings)
    """
    return Settings()
