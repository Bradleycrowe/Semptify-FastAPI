# Storage services - OAuth2 cloud storage providers
from app.services.storage.base import StorageProvider, StorageFile, StorageToken
from app.services.storage.google_drive import GoogleDriveProvider
from app.services.storage.dropbox import DropboxProvider
from app.services.storage.onedrive import OneDriveProvider
from app.services.storage.r2 import R2Provider


def get_provider(provider_name: str, **kwargs) -> StorageProvider:
    """
    Factory function to get a storage provider by name.
    
    Args:
        provider_name: One of 'google_drive', 'dropbox', 'onedrive', 'r2'
        **kwargs: Provider-specific configuration
    
    Returns:
        StorageProvider instance
    """
    providers = {
        "google_drive": GoogleDriveProvider,
        "googledrive": GoogleDriveProvider,
        "gdrive": GoogleDriveProvider,
        "dropbox": DropboxProvider,
        "onedrive": OneDriveProvider,
        "r2": R2Provider,
        "cloudflare_r2": R2Provider,
    }
    
    provider_class = providers.get(provider_name.lower())
    if not provider_class:
        raise ValueError(f"Unknown storage provider: {provider_name}")
    
    return provider_class(**kwargs)


__all__ = [
    "StorageProvider",
    "StorageFile",
    "StorageToken",
    "GoogleDriveProvider",
    "DropboxProvider",
    "OneDriveProvider",
    "R2Provider",
    "get_provider",
]
