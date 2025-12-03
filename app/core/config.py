"""
Semptify Configuration
Pydantic Settings for environment-based configuration.
Single source of truth for all app settings.
"""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    )
    
    # ==========================================================================
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
    # Security Mode: open (dev/testing) or enforced (production)
    # ==========================================================================
    security_mode: Literal["open", "enforced"] = "enforced"
    secret_key: str = "change-me-in-production-use-secrets"
    
    # Token settings
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    user_token_length: int = 12  # Anonymous user token length
    
    # Rate limiting
    rate_limit_window: int = 60  # seconds
    rate_limit_max_requests: int = 100
    admin_rate_limit_window: int = 60
    admin_rate_limit_max_requests: int = 20
    
    # ==========================================================================
    # Database
    # ==========================================================================
    # SQLite for dev, PostgreSQL for production
    database_url: str = "sqlite+aiosqlite:///./semptify.db"
    # For Postgres: "postgresql+asyncpg://user:pass@host:port/dbname"
    
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
    ai_provider: Literal["openai", "azure", "ollama", "none"] = "none"
    
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    
    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    
    # Ollama (local)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    
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
    # Deployment
    # ==========================================================================
    cors_origins: str = "*"  # Comma-separated list or "*"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

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
