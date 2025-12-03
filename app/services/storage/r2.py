"""
Semptify 5.0 - Cloudflare R2 Storage Provider
Async S3-compatible client for system storage (admin-only).
"""

from typing import Optional
from datetime import datetime, timezone
import hashlib

import httpx

from app.services.storage.base import StorageProvider, StorageFile


class R2Provider(StorageProvider):
    """
    Cloudflare R2 storage provider using S3-compatible API.
    Used for SYSTEM storage only (admin/internal operations).
    Users do NOT use R2 for their data - they use their own cloud storage.
    """
    
    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
    ):
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self.endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    
    @property
    def provider_name(self) -> str:
        return "r2"
    
    def _sign_request(
        self,
        method: str,
        path: str,
        headers: dict,
        payload_hash: str,
    ) -> dict:
        """
        Sign request using AWS Signature Version 4.
        Simplified implementation - in production use boto3 or aioboto3.
        """
        # For full implementation, use aioboto3 or httpx-auth-aws4
        # This is a placeholder showing the interface
        from datetime import datetime as dt
        import hmac
        import hashlib
        
        amz_date = dt.utcnow().strftime('%Y%m%dT%H%M%SZ')
        date_stamp = dt.utcnow().strftime('%Y%m%d')
        
        region = "auto"
        service = "s3"
        
        # Canonical request components
        canonical_uri = f"/{self.bucket_name}{path}"
        canonical_querystring = ""
        
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        host = f"{self.account_id}.r2.cloudflarestorage.com"
        
        canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
        
        canonical_request = f"{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        
        # String to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        
        # Signing key
        def sign(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        
        k_date = sign(('AWS4' + self.secret_access_key).encode('utf-8'), date_stamp)
        k_region = sign(k_date, region)
        k_service = sign(k_region, service)
        k_signing = sign(k_service, 'aws4_request')
        
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        
        authorization_header = f"{algorithm} Credential={self.access_key_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        
        return {
            "Host": host,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": authorization_header,
        }
    
    async def is_connected(self) -> bool:
        """Check if R2 bucket is accessible."""
        try:
            # Use aioboto3 in production for proper S3 operations
            # This is a simplified check
            path = "/"
            payload_hash = hashlib.sha256(b"").hexdigest()
            headers = self._sign_request("HEAD", path, {}, payload_hash)
            
            async with httpx.AsyncClient() as client:
                response = await client.head(
                    f"{self.endpoint}/{self.bucket_name}",
                    headers=headers,
                    timeout=10.0,
                )
                return response.status_code in (200, 403)  # 403 = exists but may need different perms
        except Exception:
            return False
    
    async def upload_file(
        self,
        file_content: bytes,
        destination_path: str,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> StorageFile:
        """Upload file to R2."""
        path = f"/{destination_path}/{filename}".replace("//", "/")
        payload_hash = hashlib.sha256(file_content).hexdigest()
        
        headers = self._sign_request("PUT", path, {}, payload_hash)
        headers["Content-Type"] = mime_type or "application/octet-stream"
        headers["Content-Length"] = str(len(file_content))
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.endpoint}/{self.bucket_name}{path}",
                headers=headers,
                content=file_content,
                timeout=60.0,
            )
            
            if response.status_code in (200, 201):
                return StorageFile(
                    id=path,
                    name=filename,
                    path=path,
                    size=len(file_content),
                    mime_type=mime_type or "application/octet-stream",
                    modified_at=datetime.now(timezone.utc),
                )

        raise Exception(f"R2 upload failed: {response.status_code}")

    async def download_file(self, file_path: str) -> bytes:
        """Download file from R2."""
        path = file_path if file_path.startswith("/") else f"/{file_path}"
        payload_hash = hashlib.sha256(b"").hexdigest()
        
        headers = self._sign_request("GET", path, {}, payload_hash)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.endpoint}/{self.bucket_name}{path}",
                headers=headers,
                timeout=60.0,
            )
            
            if response.status_code == 200:
                return response.content
        
        raise Exception(f"R2 download failed: {file_path}")
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from R2."""
        path = file_path if file_path.startswith("/") else f"/{file_path}"
        payload_hash = hashlib.sha256(b"").hexdigest()
        
        headers = self._sign_request("DELETE", path, {}, payload_hash)
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.endpoint}/{self.bucket_name}{path}",
                headers=headers,
                timeout=10.0,
            )
            
            return response.status_code in (200, 204)
    
    async def list_files(
        self,
        folder_path: str = "/",
        recursive: bool = False,
    ) -> list[StorageFile]:
        """List files in R2 bucket."""
        # R2 uses prefix-based listing
        prefix = folder_path.strip("/")
        if prefix:
            prefix += "/"
        
        payload_hash = hashlib.sha256(b"").hexdigest()
        headers = self._sign_request("GET", "/", {}, payload_hash)
        
        params = {"prefix": prefix}
        if not recursive:
            params["delimiter"] = "/"
        
        files = []
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.endpoint}/{self.bucket_name}",
                headers=headers,
                params=params,
                timeout=30.0,
            )
            
            if response.status_code == 200:
                # Parse XML response (S3 returns XML)
                # In production, use proper XML parsing or aioboto3
                # This is simplified
                pass
        
        return files
    
    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists in R2."""
        path = file_path if file_path.startswith("/") else f"/{file_path}"
        payload_hash = hashlib.sha256(b"").hexdigest()
        
        headers = self._sign_request("HEAD", path, {}, payload_hash)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.head(
                    f"{self.endpoint}/{self.bucket_name}{path}",
                    headers=headers,
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False
    
    async def create_folder(self, folder_path: str) -> bool:
        """Create folder in R2 (S3 doesn't have folders, just prefixes)."""
        # S3/R2 doesn't have real folders - they're just key prefixes
        # We can create a placeholder object to represent the folder
        path = folder_path.strip("/") + "/.folder"
        
        try:
            await self.upload_file(
                file_content=b"",
                destination_path="",
                filename=path,
                mime_type="application/x-directory",
            )
            return True
        except Exception:
            return False


# Note: For production R2 usage, consider using aioboto3:
# 
# import aioboto3
# 
# session = aioboto3.Session()
# async with session.client(
#     "s3",
#     endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
#     aws_access_key_id=access_key_id,
#     aws_secret_access_key=secret_access_key,
# ) as s3:
#     await s3.put_object(Bucket=bucket, Key=key, Body=data)
