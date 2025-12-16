"""
Audit Logging for Semptify.

Tracks sensitive operations for compliance, security, and debugging.

Usage:
    from app.core.audit import audit_log, AuditAction
    
    # Log an action
    await audit_log(
        action=AuditAction.DOCUMENT_ACCESS,
        user_id="user123",
        resource_type="document",
        resource_id="doc456",
        details={"filename": "lease.pdf"}
    )
    
    # Decorator for automatic logging
    @audit_logged(AuditAction.DOCUMENT_DELETE)
    async def delete_document(doc_id: str, user_id: str):
        ...
"""

import json
import logging
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar
from uuid import uuid4

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AuditAction(str, Enum):
    """Enumeration of auditable actions."""
    
    # Authentication
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    TOKEN_REFRESH = "auth.token.refresh"
    PASSWORD_CHANGE = "auth.password.change"
    
    # User Management
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role.change"
    
    # Document Operations
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_ACCESS = "document.access"
    DOCUMENT_DOWNLOAD = "document.download"
    DOCUMENT_DELETE = "document.delete"
    DOCUMENT_SHARE = "document.share"
    
    # Vault Operations
    VAULT_UNLOCK = "vault.unlock"
    VAULT_LOCK = "vault.lock"
    VAULT_FILE_ADD = "vault.file.add"
    VAULT_FILE_REMOVE = "vault.file.remove"
    
    # Legal Actions
    CASE_CREATE = "case.create"
    CASE_UPDATE = "case.update"
    CASE_DELETE = "case.delete"
    COMPLAINT_FILE = "complaint.file"
    FORM_SUBMIT = "form.submit"
    
    # AI Operations
    AI_QUERY = "ai.query"
    AI_DOCUMENT_ANALYSIS = "ai.document.analysis"
    AI_LEGAL_ADVICE = "ai.legal.advice"
    
    # System Operations
    CONFIG_CHANGE = "system.config.change"
    BACKUP_CREATE = "system.backup.create"
    BACKUP_RESTORE = "system.backup.restore"
    DATA_EXPORT = "system.data.export"
    DATA_IMPORT = "system.data.import"
    
    # Security Events
    RATE_LIMIT_EXCEEDED = "security.rate_limit"
    INVALID_TOKEN = "security.invalid_token"
    UNAUTHORIZED_ACCESS = "security.unauthorized"
    SUSPICIOUS_ACTIVITY = "security.suspicious"


class AuditEntry:
    """Represents a single audit log entry."""
    
    def __init__(
        self,
        action: AuditAction,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        success: bool = True,
        error_message: str | None = None,
    ):
        self.id = str(uuid4())
        self.timestamp = datetime.utcnow()
        self.action = action
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.details = details or {}
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.success = success
        self.error_message = error_message
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "success": self.success,
            "error_message": self.error_message,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """
    Manages audit logging with multiple backends.
    
    Backends:
    - File: JSON lines file (default)
    - Database: SQLAlchemy table (optional)
    - External: Webhook/API (optional)
    """
    
    def __init__(self):
        self._log_dir = Path("logs/audit")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._current_file: Path | None = None
        self._file_handle = None
        self._db_enabled = False
        self._webhook_url: str | None = None
    
    def _get_log_file(self) -> Path:
        """Get current log file (rotated daily)."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        return self._log_dir / f"audit_{date_str}.jsonl"
    
    async def log(self, entry: AuditEntry) -> None:
        """Log an audit entry."""
        # Always log to file
        await self._log_to_file(entry)
        
        # Log to database if enabled
        if self._db_enabled:
            await self._log_to_database(entry)
        
        # Send to webhook if configured
        if self._webhook_url:
            await self._log_to_webhook(entry)
        
        # Also log to standard logger for visibility
        log_level = logging.WARNING if not entry.success else logging.INFO
        logger.log(
            log_level,
            "AUDIT: %s | user=%s | resource=%s/%s | success=%s",
            entry.action.value,
            entry.user_id or "anonymous",
            entry.resource_type or "-",
            entry.resource_id or "-",
            entry.success,
        )
    
    async def _log_to_file(self, entry: AuditEntry) -> None:
        """Write audit entry to JSON lines file."""
        try:
            log_file = self._get_log_file()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
        except Exception as e:
            logger.error("Failed to write audit log: %s", e)
    
    async def _log_to_database(self, entry: AuditEntry) -> None:
        """Write audit entry to database."""
        # TODO: Implement database logging when audit table is created
        pass
    
    async def _log_to_webhook(self, entry: AuditEntry) -> None:
        """Send audit entry to external webhook."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(
                    self._webhook_url,
                    json=entry.to_dict(),
                    timeout=5.0,
                )
        except Exception as e:
            logger.error("Failed to send audit to webhook: %s", e)
    
    def enable_database_logging(self) -> None:
        """Enable database logging backend."""
        self._db_enabled = True
    
    def set_webhook(self, url: str) -> None:
        """Configure webhook for external audit logging."""
        self._webhook_url = url
    
    async def query(
        self,
        action: AuditAction | None = None,
        user_id: str | None = None,
        resource_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query audit logs from files.
        
        Note: For production, use database backend for efficient querying.
        """
        results = []
        
        # Determine which files to search
        files_to_search = sorted(self._log_dir.glob("audit_*.jsonl"), reverse=True)
        
        for log_file in files_to_search:
            if len(results) >= limit:
                break
            
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if len(results) >= limit:
                            break
                        
                        entry = json.loads(line)
                        
                        # Apply filters
                        if action and entry.get("action") != action.value:
                            continue
                        if user_id and entry.get("user_id") != user_id:
                            continue
                        if resource_type and entry.get("resource_type") != resource_type:
                            continue
                        
                        entry_time = datetime.fromisoformat(entry.get("timestamp", ""))
                        if start_date and entry_time < start_date:
                            continue
                        if end_date and entry_time > end_date:
                            continue
                        
                        results.append(entry)
            except Exception as e:
                logger.error("Error reading audit file %s: %s", log_file, e)
        
        return results


# Global audit logger instance
_audit_logger = AuditLogger()


async def audit_log(
    action: AuditAction,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    success: bool = True,
    error_message: str | None = None,
) -> None:
    """
    Log an audit event.
    
    Usage:
        await audit_log(
            action=AuditAction.DOCUMENT_UPLOAD,
            user_id="user123",
            resource_type="document",
            resource_id="doc456",
            details={"filename": "lease.pdf", "size": 1024}
        )
    """
    entry = AuditEntry(
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        error_message=error_message,
    )
    await _audit_logger.log(entry)


def audit_logged(
    action: AuditAction,
    resource_type: str | None = None,
    extract_user_id: Callable[..., str | None] | None = None,
    extract_resource_id: Callable[..., str | None] | None = None,
):
    """
    Decorator to automatically log function execution.
    
    Usage:
        @audit_logged(AuditAction.DOCUMENT_DELETE, resource_type="document")
        async def delete_document(doc_id: str, user_id: str):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Extract IDs if extractors provided
            user_id = extract_user_id(*args, **kwargs) if extract_user_id else kwargs.get("user_id")
            resource_id = extract_resource_id(*args, **kwargs) if extract_resource_id else kwargs.get("resource_id", kwargs.get("doc_id"))
            
            success = True
            error_msg = None
            result = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_msg = str(e)
                raise
            finally:
                await audit_log(
                    action=action,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details={"function": func.__name__},
                    success=success,
                    error_message=error_msg,
                )
        
        return wrapper
    
    return decorator


async def query_audit_logs(
    action: AuditAction | None = None,
    user_id: str | None = None,
    resource_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query audit logs."""
    return await _audit_logger.query(
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


# Convenience functions for common audit events
async def audit_login(user_id: str, success: bool, ip_address: str | None = None, error: str | None = None) -> None:
    """Log login attempt."""
    await audit_log(
        action=AuditAction.LOGIN_SUCCESS if success else AuditAction.LOGIN_FAILURE,
        user_id=user_id,
        ip_address=ip_address,
        success=success,
        error_message=error,
    )


async def audit_document_access(user_id: str, doc_id: str, action: str = "view", filename: str | None = None) -> None:
    """Log document access."""
    await audit_log(
        action=AuditAction.DOCUMENT_ACCESS,
        user_id=user_id,
        resource_type="document",
        resource_id=doc_id,
        details={"action": action, "filename": filename},
    )


async def audit_security_event(event_type: AuditAction, ip_address: str | None = None, details: dict | None = None) -> None:
    """Log security event."""
    await audit_log(
        action=event_type,
        ip_address=ip_address,
        details=details,
        success=False,
    )
