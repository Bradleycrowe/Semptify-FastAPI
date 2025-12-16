"""
Semptify SDK - Main Client

Unified client for all Semptify API operations.
"""

from typing import Optional, Dict, Any
import httpx

from .auth import AuthClient, UserInfo
from .documents import DocumentClient
from .timeline import TimelineClient
from .copilot import CopilotClient
from .complaints import ComplaintClient
from .briefcase import BriefcaseClient
from .vault import VaultClient
from .exceptions import SemptifyError, AuthenticationError


class SemptifyClient:
    """
    Main Semptify SDK client.
    
    Provides unified access to all Semptify API services.
    
    Example:
        ```python
        from sdk import SemptifyClient
        
        # Initialize client
        client = SemptifyClient("http://localhost:8000")
        
        # Authenticate via OAuth
        auth_url = client.auth.get_auth_url("google")
        # ... user completes OAuth flow ...
        client.auth.complete_oauth("google", code)
        
        # Upload a document
        doc = client.documents.upload("lease.pdf")
        
        # Get AI analysis
        analysis = client.copilot.analyze_case()
        
        # Check deadlines
        deadlines = client.timeline.get_deadlines()
        ```
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        user_id: Optional[str] = None,
    ):
        """
        Initialize the Semptify client.
        
        Args:
            base_url: Base URL of the Semptify API
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            user_id: Optional user ID for multi-user scenarios
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.user_id = user_id
        
        # Initialize HTTP clients
        self._client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        
        # Initialize service clients (lazy)
        self._auth: Optional[AuthClient] = None
        self._documents: Optional[DocumentClient] = None
        self._timeline: Optional[TimelineClient] = None
        self._copilot: Optional[CopilotClient] = None
        self._complaints: Optional[ComplaintClient] = None
        self._briefcase: Optional[BriefcaseClient] = None
        self._vault: Optional[VaultClient] = None
        
        # Current user info
        self._current_user: Optional[UserInfo] = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get default headers for requests."""
        headers = {
            "Accept": "application/json",
            "User-Agent": "Semptify-SDK/5.0.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    @property
    def client(self) -> httpx.Client:
        """Get or create the sync HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client
    
    @property
    def async_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._async_client
    
    def _create_service_client(self, client_class):
        """Create a service client with shared HTTP client."""
        instance = client_class.__new__(client_class)
        instance.base_url = self.base_url
        instance.timeout = self.timeout
        instance.user_id = self.user_id
        instance._client = None
        instance._async_client = None
        # Share the HTTP clients
        instance.client = self.client
        instance.async_client = self.async_client
        return instance
    
    @property
    def auth(self) -> AuthClient:
        """Authentication service client."""
        if self._auth is None:
            self._auth = self._create_service_client(AuthClient)
        return self._auth
    
    @property
    def documents(self) -> DocumentClient:
        """Document management service client."""
        if self._documents is None:
            self._documents = self._create_service_client(DocumentClient)
        return self._documents
    
    @property
    def timeline(self) -> TimelineClient:
        """Timeline and deadline service client."""
        if self._timeline is None:
            self._timeline = self._create_service_client(TimelineClient)
        return self._timeline
    
    @property
    def copilot(self) -> CopilotClient:
        """AI copilot service client."""
        if self._copilot is None:
            self._copilot = self._create_service_client(CopilotClient)
        return self._copilot
    
    @property
    def complaints(self) -> ComplaintClient:
        """Complaint management service client."""
        if self._complaints is None:
            self._complaints = self._create_service_client(ComplaintClient)
        return self._complaints
    
    @property
    def briefcase(self) -> BriefcaseClient:
        """Briefcase management service client."""
        if self._briefcase is None:
            self._briefcase = self._create_service_client(BriefcaseClient)
        return self._briefcase
    
    @property
    def vault(self) -> VaultClient:
        """Vault (secure storage) service client."""
        if self._vault is None:
            self._vault = self._create_service_client(VaultClient)
        return self._vault
    
    @property
    def current_user(self) -> Optional[UserInfo]:
        """Get the current authenticated user."""
        return self._current_user
    
    def login(self, provider: str, code: str) -> UserInfo:
        """
        Complete OAuth login.
        
        Args:
            provider: OAuth provider (google, dropbox, onedrive)
            code: OAuth authorization code
            
        Returns:
            Authenticated user information
        """
        self._current_user = self.auth.complete_oauth(provider, code)
        self.user_id = self._current_user.id
        return self._current_user
    
    def logout(self) -> bool:
        """
        Logout the current user.
        
        Returns:
            True if logout successful
        """
        result = self.auth.logout()
        self._current_user = None
        self.user_id = None
        return result
    
    def validate_session(self) -> bool:
        """
        Validate the current session.
        
        Returns:
            True if session is valid
        """
        if self.auth.validate_session():
            self._current_user = self.auth.get_current_user()
            if self._current_user:
                self.user_id = self._current_user.id
            return True
        return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check API health status.
        
        Returns:
            Health status information
        """
        response = self.client.get("/health")
        return response.json()
    
    async def ahealth_check(self) -> Dict[str, Any]:
        """
        Check API health status (async).
        
        Returns:
            Health status information
        """
        response = await self.async_client.get("/health")
        return response.json()
    
    def close(self):
        """Close HTTP clients and cleanup resources."""
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._async_client.aclose())
                else:
                    loop.run_until_complete(self._async_client.aclose())
            except RuntimeError:
                pass
            self._async_client = None
    
    async def aclose(self):
        """Close HTTP clients and cleanup resources (async)."""
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.aclose()
        return False
    
    def __repr__(self) -> str:
        """String representation."""
        user_info = f", user={self._current_user.email}" if self._current_user else ""
        return f"SemptifyClient(base_url={self.base_url!r}{user_info})"
