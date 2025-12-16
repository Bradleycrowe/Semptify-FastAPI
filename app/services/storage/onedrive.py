"""
Semptify 5.0 - OneDrive Storage Provider
Async OneDrive client using Microsoft Graph API.
"""

from typing import Optional
from datetime import datetime, timezone
import json

import httpx

from app.services.storage.base import StorageProvider, StorageFile


class OneDriveProvider(StorageProvider):
    """
    OneDrive storage provider using Microsoft Graph API.
    Uses OAuth2 access token for API calls.
    """
    
    GRAPH_URL = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, access_token: str, refresh_token: Optional[str] = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
    
    @property
    def provider_name(self) -> str:
        return "onedrive"
    
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    async def is_connected(self) -> bool:
        """Check if OneDrive is accessible."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.GRAPH_URL}/me/drive",
                    headers=self._headers(),
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False
    
    def _encode_path(self, path: str) -> str:
        """Encode path for Graph API."""
        if not path or path == "/":
            return "root"
        path = path.strip("/")
        return f"root:/{path}:"
    
    async def upload_file(
        self,
        file_content: bytes,
        destination_path: str,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> StorageFile:
        """Upload file to OneDrive AppFolder (Semptify app-specific folder)."""
        import logging
        logger = logging.getLogger(__name__)
        
        # For small files (< 4MB), use simple upload
        if len(file_content) < 4 * 1024 * 1024:
            # Using AppFolder scope - files go to /Apps/Semptify/ folder
            # This uses the special/approot endpoint instead of root
            path = f"{destination_path}/{filename}".strip("/")
            # AppFolder endpoint: /me/drive/special/approot:/path:/content
            url = f"{self.GRAPH_URL}/me/drive/special/approot:/{path}:/content"
            
            logger.info(f"Uploading to OneDrive AppFolder: {path}")
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": mime_type or "application/octet-stream",
                    },
                    content=file_content,
                    timeout=60.0,
                )
                
                logger.info(f"OneDrive upload response: {response.status_code}")
                
                if response.status_code in (200, 201):
                    data = response.json()
                    return StorageFile(
                        id=data.get("id", ""),
                        name=filename,
                        path=f"/{path}",
                        size=data.get("size", len(file_content)),
                        mime_type=data.get("file", {}).get("mimeType", mime_type or "application/octet-stream"),
                        modified_at=datetime.fromisoformat(
                            data.get("lastModifiedDateTime", "").replace("Z", "+00:00")
                        ) if data.get("lastModifiedDateTime") else datetime.now(timezone.utc),
                    )
                else:
                    logger.error(f"OneDrive upload failed: {response.status_code} - {response.text}")
                    raise Exception(f"OneDrive upload failed: {response.status_code} - {response.text[:200]}")

        raise Exception("File too large for simple upload (>4MB)")

    async def download_file(self, file_path: str) -> bytes:
        """Download file from OneDrive AppFolder."""
        path = file_path.strip("/")
        # Use AppFolder endpoint
        url = f"{self.GRAPH_URL}/me/drive/special/approot:/{path}:/content"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._headers(),
                follow_redirects=True,
                timeout=60.0,
            )
            
            if response.status_code == 200:
                return response.content
        
        raise Exception(f"Download failed: {file_path}")
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from OneDrive AppFolder."""
        path = file_path.strip("/")
        # Use AppFolder endpoint
        url = f"{self.GRAPH_URL}/me/drive/special/approot:/{path}"
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                url,
                headers=self._headers(),
                timeout=10.0,
            )
            
            return response.status_code == 204
    
    async def list_files(
        self,
        folder_path: str = "/",
        recursive: bool = False,
    ) -> list[StorageFile]:
        """List files in OneDrive AppFolder."""
        files = []
        
        # Use AppFolder endpoint (special/approot)
        if folder_path in ("/", ""):
            url = f"{self.GRAPH_URL}/me/drive/special/approot/children"
        else:
            path = folder_path.strip("/")
            url = f"{self.GRAPH_URL}/me/drive/special/approot:/{path}:/children"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._headers(),
                timeout=30.0,
            )
            
            if response.status_code == 200:
                data = response.json()
                for item in data.get("value", []):
                    is_folder = "folder" in item
                    storage_file = StorageFile(
                        id=item.get("id", ""),
                        name=item["name"],
                        path=item.get("parentReference", {}).get("path", "") + "/" + item["name"],
                        size=item.get("size", 0),
                        mime_type=item.get("file", {}).get("mimeType", "folder" if is_folder else "application/octet-stream"),
                        modified_at=datetime.fromisoformat(
                            item.get("lastModifiedDateTime", "").replace("Z", "+00:00")
                        ) if item.get("lastModifiedDateTime") else datetime.now(timezone.utc),
                        is_folder=is_folder,
                    )
                    files.append(storage_file)

                    # Recursive listing
                    if recursive and is_folder:
                        sub_path = f"{folder_path}/{item['name']}".strip("/")
                        sub_files = await self.list_files(sub_path, recursive=True)
                        files.extend(sub_files)

                # Handle pagination
                while data.get("@odata.nextLink"):
                    response = await client.get(
                        data["@odata.nextLink"],
                        headers=self._headers(),
                        timeout=30.0,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get("value", []):
                            is_folder = "folder" in item
                            files.append(StorageFile(
                                id=item.get("id", ""),
                                name=item["name"],
                                path=item.get("parentReference", {}).get("path", "") + "/" + item["name"],
                                size=item.get("size", 0),
                                mime_type=item.get("file", {}).get("mimeType", "folder" if is_folder else "application/octet-stream"),
                                modified_at=datetime.fromisoformat(
                                    item.get("lastModifiedDateTime", "").replace("Z", "+00:00")
                                ) if item.get("lastModifiedDateTime") else datetime.now(timezone.utc),
                                is_folder=is_folder,
                            ))
                    else:
                        break

        return files

    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists in OneDrive AppFolder."""
        path = file_path.strip("/")
        # Use AppFolder endpoint
        url = f"{self.GRAPH_URL}/me/drive/special/approot:/{path}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=self._headers(),
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False
    
    async def create_folder(self, folder_path: str) -> bool:
        """Create folder in OneDrive AppFolder."""
        # Check if already exists
        if await self.file_exists(folder_path):
            return True
        
        # Split path to get parent and folder name
        parts = folder_path.strip("/").split("/")
        folder_name = parts[-1]
        parent_path = "/".join(parts[:-1])
        
        # Use AppFolder endpoint
        if parent_path:
            # Ensure parent exists
            await self.create_folder(parent_path)
            url = f"{self.GRAPH_URL}/me/drive/special/approot:/{parent_path}:/children"
        else:
            url = f"{self.GRAPH_URL}/me/drive/special/approot/children"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self._headers(),
                json={
                    "name": folder_name,
                    "folder": {},
                    "@microsoft.graph.conflictBehavior": "fail",
                },
                timeout=10.0,
            )
            
            # 409 = already exists (race condition), which is fine
            return response.status_code in (200, 201, 409)
