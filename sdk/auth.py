"""
Semptify SDK - Authentication Client

Handles OAuth flow and user authentication.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from .base import BaseClient


@dataclass
class UserInfo:
    """User information."""
    user_id: str
    provider: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str = "user"


@dataclass
class StorageProvider:
    """Storage provider information."""
    id: str
    name: str
    icon: str
    connected: bool = False


class AuthClient(BaseClient):
    """Client for authentication operations."""
    
    def get_providers(self) -> List[StorageProvider]:
        """
        Get available storage providers.
        
        Returns:
            List of available storage providers
        """
        response = self.get("/storage/providers")
        # Handle HTML response (provider selection page)
        if "content" in response:
            # Return known providers
            return [
                StorageProvider(id="google_drive", name="Google Drive", icon="google"),
                StorageProvider(id="dropbox", name="Dropbox", icon="dropbox"),
                StorageProvider(id="onedrive", name="OneDrive", icon="microsoft"),
            ]
        return [StorageProvider(**p) for p in response.get("providers", [])]
    
    def get_auth_url(self, provider: str) -> str:
        """
        Get the OAuth authorization URL for a provider.
        
        Args:
            provider: The storage provider (google_drive, dropbox, onedrive)
            
        Returns:
            The OAuth authorization URL
        """
        response = self.client.get(f"/storage/auth/{provider}", follow_redirects=False)
        if response.status_code in [302, 307]:
            return response.headers.get("location", "")
        return self._handle_response(response).get("auth_url", "")
    
    def complete_oauth(self, provider: str, code: str, state: str) -> UserInfo:
        """
        Complete OAuth flow with authorization code.
        
        Args:
            provider: The storage provider
            code: The authorization code from OAuth callback
            state: The state parameter from OAuth callback
            
        Returns:
            User information after successful authentication
        """
        response = self.get(
            f"/storage/callback/{provider}",
            params={"code": code, "state": state}
        )
        self.set_user_id(response.get("user_id", ""))
        return UserInfo(
            user_id=response.get("user_id", ""),
            provider=provider,
            email=response.get("email"),
            display_name=response.get("display_name"),
        )
    
    def get_current_user(self) -> Optional[UserInfo]:
        """
        Get the currently authenticated user.
        
        Returns:
            Current user info or None if not authenticated
        """
        try:
            response = self.get("/api/auth/me")
            return UserInfo(
                user_id=response.get("user_id", ""),
                provider=response.get("provider", ""),
                email=response.get("email"),
                display_name=response.get("display_name"),
                avatar_url=response.get("avatar_url"),
                role=response.get("role", "user"),
            )
        except Exception:
            return None
    
    def logout(self) -> bool:
        """
        Log out the current user.
        
        Returns:
            True if logout was successful
        """
        try:
            self.post("/api/auth/logout")
            self.user_id = None
            return True
        except Exception:
            return False
    
    def validate_session(self) -> bool:
        """
        Validate the current session.
        
        Returns:
            True if session is valid
        """
        try:
            response = self.post("/api/auth/validate")
            return response.get("valid", False)
        except Exception:
            return False
    
    def switch_role(self, role: str) -> UserInfo:
        """
        Switch the current user's role.
        
        Args:
            role: The new role (tenant, landlord, legal, etc.)
            
        Returns:
            Updated user information
        """
        response = self.post("/storage/role", json={"role": role})
        return UserInfo(
            user_id=response.get("user_id", self.user_id or ""),
            provider=response.get("provider", ""),
            role=response.get("role", role),
        )
