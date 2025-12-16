"""
Semptify Python SDK

A comprehensive Python client for the Semptify 5.0 API.
Provides typed access to all Semptify services for tenant rights protection.

Usage:
    from sdk import SemptifyClient
    
    client = SemptifyClient(base_url="http://localhost:8000")
    client.auth.login(provider="google_drive")
    
    # Upload a document
    doc = client.documents.upload("eviction_notice.pdf")
    
    # Get AI analysis
    analysis = client.copilot.analyze(doc.id)
"""

from .client import SemptifyClient
from .auth import AuthClient
from .documents import DocumentClient
from .timeline import TimelineClient
from .copilot import CopilotClient
from .complaints import ComplaintClient
from .briefcase import BriefcaseClient
from .vault import VaultClient
from .exceptions import (
    SemptifyError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
)

__version__ = "5.0.0"
__all__ = [
    "SemptifyClient",
    "AuthClient",
    "DocumentClient",
    "TimelineClient",
    "CopilotClient",
    "ComplaintClient",
    "BriefcaseClient",
    "VaultClient",
    "SemptifyError",
    "AuthenticationError",
    "NotFoundError",
    "ValidationError",
    "RateLimitError",
    "ServerError",
]
