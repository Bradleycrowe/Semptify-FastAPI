"""
Semptify SDK - Base HTTP Client

Provides the core HTTP functionality for all SDK clients.
"""

import httpx
from typing import Optional, Dict, Any, Union
from pathlib import Path
import json

from .exceptions import (
    SemptifyError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
    StorageRequiredError,
)


class BaseClient:
    """Base HTTP client with error handling and authentication."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        user_id: Optional[str] = None,
    ):
        """
        Initialize the base client.
        
        Args:
            base_url: The Semptify API base URL
            timeout: Request timeout in seconds
            user_id: Optional user ID for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_id = user_id
        self._client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.Client:
        """Get or create sync HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                cookies=self._get_cookies(),
            )
        return self._client
    
    @property
    def async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                cookies=self._get_cookies(),
            )
        return self._async_client
    
    def _get_cookies(self) -> Dict[str, str]:
        """Get authentication cookies."""
        cookies = {}
        if self.user_id:
            cookies["semptify_uid"] = self.user_id
        return cookies
    
    def set_user_id(self, user_id: str) -> None:
        """Set the user ID for authentication."""
        self.user_id = user_id
        # Recreate clients with new cookies
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            # Note: async client should be closed with await
            self._async_client = None
    
    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Handle HTTP response and raise appropriate exceptions.
        
        Args:
            response: The HTTP response
            
        Returns:
            Parsed JSON response data
            
        Raises:
            SemptifyError: On API errors
        """
        request_id = response.headers.get("x-request-id")
        
        # Success responses
        if response.status_code < 400:
            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
            return {"content": response.text, "status_code": response.status_code}
        
        # Parse error response
        try:
            data = response.json()
        except json.JSONDecodeError:
            data = {"message": response.text}
        
        # Extract error details
        error_msg = data.get("detail") or data.get("message") or data.get("error") or "Unknown error"
        
        # Handle specific error codes
        if response.status_code == 401:
            if data.get("error") == "storage_required":
                raise StorageRequiredError(
                    message=error_msg,
                    redirect_url=data.get("redirect_url", "/storage/providers"),
                    response_data=data,
                    request_id=request_id,
                )
            raise AuthenticationError(
                message=error_msg,
                status_code=401,
                response_data=data,
                request_id=request_id,
            )
        
        if response.status_code == 403:
            raise AuthenticationError(
                message=error_msg,
                status_code=403,
                response_data=data,
                request_id=request_id,
            )
        
        if response.status_code == 404:
            raise NotFoundError(
                resource_type="Resource",
                response_data=data,
                request_id=request_id,
            )
        
        if response.status_code == 422:
            raise ValidationError(
                message=error_msg,
                errors=data.get("detail", []),
                response_data=data,
                request_id=request_id,
            )
        
        if response.status_code == 429:
            raise RateLimitError(
                message=error_msg,
                retry_after=int(response.headers.get("retry-after", 60)),
                response_data=data,
                request_id=request_id,
            )
        
        if response.status_code >= 500:
            raise ServerError(
                message=error_msg,
                response_data=data,
                request_id=request_id,
            )
        
        raise SemptifyError(
            message=error_msg,
            status_code=response.status_code,
            response_data=data,
            request_id=request_id,
        )
    
    def get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a GET request."""
        response = self.client.get(path, params=params)
        return self._handle_response(response)
    
    def post(
        self,
        path: str,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make a POST request."""
        response = self.client.post(path, json=json, data=data, files=files)
        return self._handle_response(response)
    
    def put(self, path: str, json: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a PUT request."""
        response = self.client.put(path, json=json)
        return self._handle_response(response)
    
    def patch(self, path: str, json: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a PATCH request."""
        response = self.client.patch(path, json=json)
        return self._handle_response(response)
    
    def delete(self, path: str) -> Dict[str, Any]:
        """Make a DELETE request."""
        response = self.client.delete(path)
        return self._handle_response(response)
    
    # Async methods
    async def aget(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an async GET request."""
        response = await self.async_client.get(path, params=params)
        return self._handle_response(response)
    
    async def apost(
        self,
        path: str,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make an async POST request."""
        response = await self.async_client.post(path, json=json, data=data, files=files)
        return self._handle_response(response)
    
    async def aput(self, path: str, json: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an async PUT request."""
        response = await self.async_client.put(path, json=json)
        return self._handle_response(response)
    
    async def adelete(self, path: str) -> Dict[str, Any]:
        """Make an async DELETE request."""
        response = await self.async_client.delete(path)
        return self._handle_response(response)
    
    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
    
    async def aclose(self) -> None:
        """Close the async HTTP client."""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.aclose()
