"""
Semptify 5.0 - Google Drive Storage Provider
Async Google Drive client using httpx and Google OAuth2.
"""

from typing import Optional
from datetime import datetime, timezone
import json

import httpx

from app.services.storage.base import StorageProvider, StorageFile


class GoogleDriveProvider(StorageProvider):
    """
    Google Drive storage provider.
    Uses OAuth2 access token for API calls.
    """
    
    BASE_URL = "https://www.googleapis.com/drive/v3"
    UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3"
    
    def __init__(self, access_token: str, refresh_token: Optional[str] = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._folder_cache: dict[str, str] = {}  # path -> folder_id
    
    @property
    def provider_name(self) -> str:
        return "google_drive"
    
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
    
    async def is_connected(self) -> bool:
        """Check if Google Drive is accessible."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/about",
                    headers=self._headers(),
                    params={"fields": "user"},
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False
    
    async def _get_folder_id(self, folder_path: str) -> Optional[str]:
        """Get folder ID by path, creating folders if needed."""
        if folder_path in self._folder_cache:
            return self._folder_cache[folder_path]
        
        # Root folder
        if folder_path in ("/", ""):
            return "root"
        
        # Split path and traverse/create
        parts = folder_path.strip("/").split("/")
        parent_id = "root"
        current_path = ""
        
        async with httpx.AsyncClient() as client:
            for part in parts:
                current_path = f"{current_path}/{part}"
                
                # Check cache
                if current_path in self._folder_cache:
                    parent_id = self._folder_cache[current_path]
                    continue
                
                # Search for folder
                query = f"name='{part}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                response = await client.get(
                    f"{self.BASE_URL}/files",
                    headers=self._headers(),
                    params={"q": query, "fields": "files(id,name)"},
                    timeout=10.0,
                )
                
                if response.status_code == 200:
                    files = response.json().get("files", [])
                    if files:
                        parent_id = files[0]["id"]
                        self._folder_cache[current_path] = parent_id
                    else:
                        # Create folder
                        create_response = await client.post(
                            f"{self.BASE_URL}/files",
                            headers={**self._headers(), "Content-Type": "application/json"},
                            json={
                                "name": part,
                                "mimeType": "application/vnd.google-apps.folder",
                                "parents": [parent_id],
                            },
                            timeout=10.0,
                        )
                        if create_response.status_code in (200, 201):
                            parent_id = create_response.json()["id"]
                            self._folder_cache[current_path] = parent_id
                        else:
                            return None
                else:
                    return None
        
        return parent_id
    
    async def upload_file(
        self,
        file_content: bytes,
        destination_path: str,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> StorageFile:
        """Upload file to Google Drive."""
        folder_id = await self._get_folder_id(destination_path)
        if not folder_id:
            raise Exception(f"Could not access folder: {destination_path}")
        
        mime_type = mime_type or "application/octet-stream"
        
        # Multipart upload
        metadata = {
            "name": filename,
            "parents": [folder_id],
        }
        
        async with httpx.AsyncClient() as client:
            # Simple upload for files < 5MB
            if len(file_content) < 5 * 1024 * 1024:
                response = await client.post(
                    f"{self.UPLOAD_URL}/files",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": mime_type,
                    },
                    params={
                        "uploadType": "media",
                    },
                    content=file_content,
                    timeout=60.0,
                )
                
                if response.status_code in (200, 201):
                    file_data = response.json()
                    # Update metadata (name and parent)
                    await client.patch(
                        f"{self.BASE_URL}/files/{file_data['id']}",
                        headers={**self._headers(), "Content-Type": "application/json"},
                        params={"addParents": folder_id},
                        json={"name": filename},
                        timeout=10.0,
                    )
                    
                    return StorageFile(
                        id=file_data["id"],
                        name=filename,
                        path=f"{destination_path}/{filename}",
                        size=len(file_content),
                        mime_type=mime_type,
                        modified_at=datetime.now(timezone.utc),
                    )

        raise Exception("Upload failed")

    async def download_file(self, file_path: str) -> bytes:
        """Download file from Google Drive."""
        # Get file ID by searching
        folder_path = "/".join(file_path.split("/")[:-1])
        filename = file_path.split("/")[-1]
        
        folder_id = await self._get_folder_id(folder_path) if folder_path else "root"
        
        async with httpx.AsyncClient() as client:
            # Search for file
            query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
            response = await client.get(
                f"{self.BASE_URL}/files",
                headers=self._headers(),
                params={"q": query, "fields": "files(id)"},
                timeout=10.0,
            )
            
            if response.status_code == 200:
                files = response.json().get("files", [])
                if files:
                    file_id = files[0]["id"]
                    # Download
                    download_response = await client.get(
                        f"{self.BASE_URL}/files/{file_id}",
                        headers=self._headers(),
                        params={"alt": "media"},
                        timeout=60.0,
                    )
                    if download_response.status_code == 200:
                        return download_response.content
        
        raise Exception(f"File not found: {file_path}")
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from Google Drive."""
        folder_path = "/".join(file_path.split("/")[:-1])
        filename = file_path.split("/")[-1]
        
        folder_id = await self._get_folder_id(folder_path) if folder_path else "root"
        
        async with httpx.AsyncClient() as client:
            query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
            response = await client.get(
                f"{self.BASE_URL}/files",
                headers=self._headers(),
                params={"q": query, "fields": "files(id)"},
                timeout=10.0,
            )
            
            if response.status_code == 200:
                files = response.json().get("files", [])
                if files:
                    file_id = files[0]["id"]
                    delete_response = await client.delete(
                        f"{self.BASE_URL}/files/{file_id}",
                        headers=self._headers(),
                        timeout=10.0,
                    )
                    return delete_response.status_code == 204
        
        return False
    
    async def list_files(
        self,
        folder_path: str = "/",
        recursive: bool = False,
    ) -> list[StorageFile]:
        """List files in a Google Drive folder."""
        folder_id = await self._get_folder_id(folder_path)
        if not folder_id:
            return []
        
        files = []
        
        async with httpx.AsyncClient() as client:
            query = f"'{folder_id}' in parents and trashed=false"
            response = await client.get(
                f"{self.BASE_URL}/files",
                headers=self._headers(),
                params={
                    "q": query,
                    "fields": "files(id,name,mimeType,size,modifiedTime)",
                },
                timeout=10.0,
            )
            
            if response.status_code == 200:
                for item in response.json().get("files", []):
                    is_folder = item["mimeType"] == "application/vnd.google-apps.folder"
                    files.append(StorageFile(
                        id=item["id"],
                        name=item["name"],
                        path=f"{folder_path}/{item['name']}",
                        size=int(item.get("size", 0)),
                        mime_type=item["mimeType"],
                        modified_at=datetime.fromisoformat(
                            item.get("modifiedTime", "").replace("Z", "+00:00")
                        ) if item.get("modifiedTime") else datetime.now(timezone.utc),
                        is_folder=is_folder,
                    ))

                    # Recursive listing
                    if recursive and is_folder:
                        sub_files = await self.list_files(
                            f"{folder_path}/{item['name']}",
                            recursive=True
                        )
                        files.extend(sub_files)
        
        return files
    
    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists in Google Drive."""
        try:
            folder_path = "/".join(file_path.split("/")[:-1])
            filename = file_path.split("/")[-1]
            
            folder_id = await self._get_folder_id(folder_path) if folder_path else "root"
            if not folder_id:
                return False
            
            async with httpx.AsyncClient() as client:
                query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
                response = await client.get(
                    f"{self.BASE_URL}/files",
                    headers=self._headers(),
                    params={"q": query, "fields": "files(id)"},
                    timeout=10.0,
                )
                
                if response.status_code == 200:
                    files = response.json().get("files", [])
                    return len(files) > 0
        except Exception:
            pass
        
        return False
    
    async def create_folder(self, folder_path: str) -> bool:
        """Create folder in Google Drive."""
        folder_id = await self._get_folder_id(folder_path)
        return folder_id is not None
