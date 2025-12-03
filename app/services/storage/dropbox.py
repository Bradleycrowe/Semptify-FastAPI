"""
Semptify 5.0 - Dropbox Storage Provider
Async Dropbox client using httpx and Dropbox OAuth2.
"""

from typing import Optional
from datetime import datetime, timezone
import json

import httpx

from app.services.storage.base import StorageProvider, StorageFile


class DropboxProvider(StorageProvider):
    """
    Dropbox storage provider.
    Uses OAuth2 access token for API calls.
    """
    
    API_URL = "https://api.dropboxapi.com/2"
    CONTENT_URL = "https://content.dropboxapi.com/2"
    
    def __init__(self, access_token: str, refresh_token: Optional[str] = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
    
    @property
    def provider_name(self) -> str:
        return "dropbox"
    
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    async def is_connected(self) -> bool:
        """Check if Dropbox is accessible."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.API_URL}/users/get_current_account",
                    headers=self._headers(),
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for Dropbox API (must start with / or be empty for root)."""
        if not path or path == "/":
            return ""
        if not path.startswith("/"):
            path = f"/{path}"
        return path
    
    async def upload_file(
        self,
        file_content: bytes,
        destination_path: str,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> StorageFile:
        """Upload file to Dropbox."""
        full_path = self._normalize_path(f"{destination_path}/{filename}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.CONTENT_URL}/files/upload",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/octet-stream",
                    "Dropbox-API-Arg": json.dumps({
                        "path": full_path,
                        "mode": "overwrite",
                        "autorename": False,
                        "mute": True,
                    }),
                },
                content=file_content,
                timeout=60.0,
            )
            
            if response.status_code == 200:
                data = response.json()
                return StorageFile(
                    id=data.get("id", ""),
                    name=filename,
                    path=full_path,
                    size=data.get("size", len(file_content)),
                    mime_type=mime_type or "application/octet-stream",
                    modified_at=datetime.fromisoformat(
                        data.get("server_modified", "").replace("Z", "+00:00")
                    ) if data.get("server_modified") else datetime.now(timezone.utc),
                )

        raise Exception(f"Upload failed: {response.text if response else 'Unknown error'}")

    async def download_file(self, file_path: str) -> bytes:
        """Download file from Dropbox."""
        full_path = self._normalize_path(file_path)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.CONTENT_URL}/files/download",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Dropbox-API-Arg": json.dumps({"path": full_path}),
                },
                timeout=60.0,
            )
            
            if response.status_code == 200:
                return response.content
        
        raise Exception(f"Download failed: {file_path}")
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from Dropbox."""
        full_path = self._normalize_path(file_path)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_URL}/files/delete_v2",
                headers=self._headers(),
                json={"path": full_path},
                timeout=10.0,
            )
            
            return response.status_code == 200
    
    async def list_files(
        self,
        folder_path: str = "/",
        recursive: bool = False,
    ) -> list[StorageFile]:
        """List files in a Dropbox folder."""
        full_path = self._normalize_path(folder_path)
        files = []
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_URL}/files/list_folder",
                headers=self._headers(),
                json={
                    "path": full_path,
                    "recursive": recursive,
                    "include_deleted": False,
                },
                timeout=30.0,
            )
            
            if response.status_code == 200:
                data = response.json()
                for entry in data.get("entries", []):
                    is_folder = entry[".tag"] == "folder"
                    files.append(StorageFile(
                        id=entry.get("id", ""),
                        name=entry["name"],
                        path=entry["path_display"],
                        size=entry.get("size", 0),
                        mime_type="folder" if is_folder else "application/octet-stream",
                        modified_at=datetime.fromisoformat(
                            entry.get("server_modified", "").replace("Z", "+00:00")
                        ) if entry.get("server_modified") else datetime.now(timezone.utc),
                        is_folder=is_folder,
                    ))
                
                # Handle pagination
                while data.get("has_more"):
                    cursor = data["cursor"]
                    response = await client.post(
                        f"{self.API_URL}/files/list_folder/continue",
                        headers=self._headers(),
                        json={"cursor": cursor},
                        timeout=30.0,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        for entry in data.get("entries", []):
                            is_folder = entry[".tag"] == "folder"
                            files.append(StorageFile(
                                id=entry.get("id", ""),
                                name=entry["name"],
                                path=entry["path_display"],
                                size=entry.get("size", 0),
                                mime_type="folder" if is_folder else "application/octet-stream",
                                modified_at=datetime.fromisoformat(
                                    entry.get("server_modified", "").replace("Z", "+00:00")
                                ) if entry.get("server_modified") else datetime.now(timezone.utc),
                                is_folder=is_folder,
                            ))
                    else:
                        break
        
        return files
    
    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists in Dropbox."""
        full_path = self._normalize_path(file_path)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.API_URL}/files/get_metadata",
                    headers=self._headers(),
                    json={"path": full_path},
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False
    
    async def create_folder(self, folder_path: str) -> bool:
        """Create folder in Dropbox."""
        full_path = self._normalize_path(folder_path)
        
        # Check if already exists
        if await self.file_exists(folder_path):
            return True
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_URL}/files/create_folder_v2",
                headers=self._headers(),
                json={"path": full_path, "autorename": False},
                timeout=10.0,
            )
            
            # 409 means folder already exists (race condition), which is fine
            return response.status_code in (200, 409)
