"""
Semptify SDK - Briefcase Client

Handles briefcase management for organizing case documents and evidence.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from .base import BaseClient


@dataclass
class BriefcaseItem:
    """Item in a briefcase."""
    id: str
    item_type: str  # document, note, link, evidence
    title: str
    description: Optional[str] = None
    document_id: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    tags: List[str] = None
    added_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class Briefcase:
    """Briefcase for organizing case materials."""
    id: str
    name: str
    description: Optional[str] = None
    case_type: Optional[str] = None
    status: str = "active"
    item_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    shared_with: List[str] = None
    
    def __post_init__(self):
        if self.shared_with is None:
            self.shared_with = []


@dataclass
class BriefcaseExport:
    """Briefcase export information."""
    export_id: str
    format: str
    status: str
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None


class BriefcaseClient(BaseClient):
    """Client for briefcase operations."""
    
    def create(
        self,
        name: str,
        description: Optional[str] = None,
        case_type: Optional[str] = None,
    ) -> Briefcase:
        """
        Create a new briefcase.
        
        Args:
            name: Briefcase name
            description: Description of the briefcase
            case_type: Type of case (habitability, discrimination, etc.)
            
        Returns:
            Created briefcase
        """
        data = {"name": name}
        if description:
            data["description"] = description
        if case_type:
            data["case_type"] = case_type
        
        response = self.post("/api/briefcase", json=data)
        
        return Briefcase(
            id=response.get("id", ""),
            name=response.get("name", name),
            description=response.get("description", description),
            case_type=response.get("case_type", case_type),
            status=response.get("status", "active"),
        )
    
    def get_briefcase(self, briefcase_id: str) -> Briefcase:
        """
        Get a briefcase by ID.
        
        Args:
            briefcase_id: The briefcase ID
            
        Returns:
            Briefcase details
        """
        response = self.get(f"/api/briefcase/{briefcase_id}")
        
        return Briefcase(
            id=response.get("id", briefcase_id),
            name=response.get("name", ""),
            description=response.get("description"),
            case_type=response.get("case_type"),
            status=response.get("status", "active"),
            item_count=response.get("item_count", 0),
            shared_with=response.get("shared_with", []),
        )
    
    def list_briefcases(
        self,
        status: Optional[str] = None,
        case_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Briefcase]:
        """
        List briefcases.
        
        Args:
            status: Filter by status
            case_type: Filter by case type
            limit: Maximum number to return
            
        Returns:
            List of briefcases
        """
        params = {"limit": limit}
        if status:
            params["status"] = status
        if case_type:
            params["case_type"] = case_type
        
        response = self.get("/api/briefcase", params=params)
        briefcases = response if isinstance(response, list) else response.get("briefcases", [])
        
        return [
            Briefcase(
                id=b.get("id", ""),
                name=b.get("name", ""),
                description=b.get("description"),
                case_type=b.get("case_type"),
                status=b.get("status", "active"),
                item_count=b.get("item_count", 0),
            )
            for b in briefcases
        ]
    
    def update(
        self,
        briefcase_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Briefcase:
        """
        Update a briefcase.
        
        Args:
            briefcase_id: The briefcase ID
            name: Updated name
            description: Updated description
            status: Updated status
            
        Returns:
            Updated briefcase
        """
        data = {}
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if status:
            data["status"] = status
        
        response = self.patch(f"/api/briefcase/{briefcase_id}", json=data)
        
        return Briefcase(
            id=response.get("id", briefcase_id),
            name=response.get("name", name or ""),
            description=response.get("description", description),
            status=response.get("status", status or "active"),
        )
    
    def delete_briefcase(self, briefcase_id: str) -> bool:
        """
        Delete a briefcase.
        
        Args:
            briefcase_id: The briefcase ID
            
        Returns:
            True if deleted successfully
        """
        self.delete(f"/api/briefcase/{briefcase_id}")
        return True
    
    def add_document(
        self,
        briefcase_id: str,
        document_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> BriefcaseItem:
        """
        Add a document to a briefcase.
        
        Args:
            briefcase_id: The briefcase ID
            document_id: Document ID to add
            title: Custom title for the item
            description: Description of the item
            tags: Tags for organization
            
        Returns:
            Created briefcase item
        """
        data = {"document_id": document_id}
        if title:
            data["title"] = title
        if description:
            data["description"] = description
        if tags:
            data["tags"] = tags
        
        response = self.post(f"/api/briefcase/{briefcase_id}/items", json=data)
        
        return BriefcaseItem(
            id=response.get("id", ""),
            item_type="document",
            title=response.get("title", title or ""),
            description=response.get("description", description),
            document_id=document_id,
            tags=response.get("tags", tags or []),
        )
    
    def add_note(
        self,
        briefcase_id: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
    ) -> BriefcaseItem:
        """
        Add a note to a briefcase.
        
        Args:
            briefcase_id: The briefcase ID
            title: Note title
            content: Note content
            tags: Tags for organization
            
        Returns:
            Created briefcase item
        """
        data = {
            "item_type": "note",
            "title": title,
            "content": content,
        }
        if tags:
            data["tags"] = tags
        
        response = self.post(f"/api/briefcase/{briefcase_id}/items", json=data)
        
        return BriefcaseItem(
            id=response.get("id", ""),
            item_type="note",
            title=response.get("title", title),
            content=response.get("content", content),
            tags=response.get("tags", tags or []),
        )
    
    def add_link(
        self,
        briefcase_id: str,
        title: str,
        url: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> BriefcaseItem:
        """
        Add a link/reference to a briefcase.
        
        Args:
            briefcase_id: The briefcase ID
            title: Link title
            url: URL
            description: Description
            tags: Tags for organization
            
        Returns:
            Created briefcase item
        """
        data = {
            "item_type": "link",
            "title": title,
            "url": url,
        }
        if description:
            data["description"] = description
        if tags:
            data["tags"] = tags
        
        response = self.post(f"/api/briefcase/{briefcase_id}/items", json=data)
        
        return BriefcaseItem(
            id=response.get("id", ""),
            item_type="link",
            title=response.get("title", title),
            url=response.get("url", url),
            description=response.get("description", description),
            tags=response.get("tags", tags or []),
        )
    
    def get_items(
        self,
        briefcase_id: str,
        item_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[BriefcaseItem]:
        """
        Get items in a briefcase.
        
        Args:
            briefcase_id: The briefcase ID
            item_type: Filter by item type
            tags: Filter by tags
            
        Returns:
            List of briefcase items
        """
        params = {}
        if item_type:
            params["item_type"] = item_type
        if tags:
            params["tags"] = ",".join(tags)
        
        response = self.get(f"/api/briefcase/{briefcase_id}/items", params=params)
        items = response if isinstance(response, list) else response.get("items", [])
        
        return [
            BriefcaseItem(
                id=item.get("id", ""),
                item_type=item.get("item_type", ""),
                title=item.get("title", ""),
                description=item.get("description"),
                document_id=item.get("document_id"),
                content=item.get("content"),
                url=item.get("url"),
                tags=item.get("tags", []),
            )
            for item in items
        ]
    
    def remove_item(self, briefcase_id: str, item_id: str) -> bool:
        """
        Remove an item from a briefcase.
        
        Args:
            briefcase_id: The briefcase ID
            item_id: Item ID to remove
            
        Returns:
            True if removed successfully
        """
        self.delete(f"/api/briefcase/{briefcase_id}/items/{item_id}")
        return True
    
    def export(
        self,
        briefcase_id: str,
        format: str = "pdf",
        include_documents: bool = True,
    ) -> BriefcaseExport:
        """
        Export a briefcase.
        
        Args:
            briefcase_id: The briefcase ID
            format: Export format (pdf, zip, docx)
            include_documents: Include full documents in export
            
        Returns:
            Export information with download URL
        """
        response = self.post(
            f"/api/briefcase/{briefcase_id}/export",
            json={"format": format, "include_documents": include_documents},
        )
        
        return BriefcaseExport(
            export_id=response.get("export_id", ""),
            format=response.get("format", format),
            status=response.get("status", "processing"),
            download_url=response.get("download_url"),
        )
    
    def share(
        self,
        briefcase_id: str,
        email: str,
        permission: str = "view",
    ) -> bool:
        """
        Share a briefcase with another user.
        
        Args:
            briefcase_id: The briefcase ID
            email: Email of user to share with
            permission: Permission level (view, edit)
            
        Returns:
            True if shared successfully
        """
        self.post(
            f"/api/briefcase/{briefcase_id}/share",
            json={"email": email, "permission": permission},
        )
        return True
