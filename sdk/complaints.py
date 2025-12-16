"""
Semptify SDK - Complaints Client

Handles complaint filing, management, and tracking with regulatory agencies.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from .base import BaseClient


class ComplaintStatus(str, Enum):
    """Complaint status values."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    UNDER_REVIEW = "under_review"
    INVESTIGATION = "investigation"
    RESOLVED = "resolved"
    CLOSED = "closed"
    APPEALED = "appealed"


class AgencyType(str, Enum):
    """Regulatory agency types."""
    HUD = "hud"
    STATE_HOUSING = "state_housing"
    LOCAL_CODE = "local_code"
    FAIR_HOUSING = "fair_housing"
    TENANT_PROTECTION = "tenant_protection"
    HEALTH_DEPARTMENT = "health_department"


@dataclass
class Complaint:
    """Complaint information."""
    id: str
    complaint_type: str
    status: str
    title: str
    description: Optional[str] = None
    agency: Optional[str] = None
    agency_case_number: Optional[str] = None
    filed_date: Optional[date] = None
    last_updated: Optional[datetime] = None
    violations: List[str] = None
    documents: List[str] = None
    
    def __post_init__(self):
        if self.violations is None:
            self.violations = []
        if self.documents is None:
            self.documents = []


@dataclass
class ComplaintTemplate:
    """Complaint template information."""
    id: str
    name: str
    description: str
    agency_type: str
    required_fields: List[str]
    optional_fields: List[str]
    instructions: str


@dataclass
class Agency:
    """Regulatory agency information."""
    id: str
    name: str
    agency_type: str
    jurisdiction: str
    contact_info: Dict[str, str]
    filing_methods: List[str]
    estimated_response_time: Optional[str] = None


class ComplaintClient(BaseClient):
    """Client for complaint filing and management."""
    
    def create(
        self,
        complaint_type: str,
        title: str,
        description: str,
        violations: List[str],
        agency: Optional[str] = None,
        property_address: Optional[str] = None,
        landlord_info: Optional[Dict[str, str]] = None,
        incident_dates: Optional[List[str]] = None,
    ) -> Complaint:
        """
        Create a new complaint.
        
        Args:
            complaint_type: Type of complaint (habitability, discrimination, retaliation, etc.)
            title: Complaint title
            description: Detailed description
            violations: List of specific violations
            agency: Target regulatory agency
            property_address: Property address
            landlord_info: Landlord contact information
            incident_dates: Dates of incidents
            
        Returns:
            Created complaint
        """
        data = {
            "complaint_type": complaint_type,
            "title": title,
            "description": description,
            "violations": violations,
        }
        
        if agency:
            data["agency"] = agency
        if property_address:
            data["property_address"] = property_address
        if landlord_info:
            data["landlord_info"] = landlord_info
        if incident_dates:
            data["incident_dates"] = incident_dates
        
        response = self.post("/api/complaints", json=data)
        
        return Complaint(
            id=response.get("id", ""),
            complaint_type=response.get("complaint_type", complaint_type),
            status=response.get("status", "draft"),
            title=response.get("title", title),
            description=response.get("description", description),
            agency=response.get("agency"),
            violations=response.get("violations", violations),
        )
    
    def get_complaint(self, complaint_id: str) -> Complaint:
        """
        Get a complaint by ID.
        
        Args:
            complaint_id: The complaint ID
            
        Returns:
            Complaint details
        """
        response = self.get(f"/api/complaints/{complaint_id}")
        
        return Complaint(
            id=response.get("id", complaint_id),
            complaint_type=response.get("complaint_type", ""),
            status=response.get("status", ""),
            title=response.get("title", ""),
            description=response.get("description"),
            agency=response.get("agency"),
            agency_case_number=response.get("agency_case_number"),
            filed_date=date.fromisoformat(response["filed_date"]) if response.get("filed_date") else None,
            violations=response.get("violations", []),
            documents=response.get("documents", []),
        )
    
    def list_complaints(
        self,
        status: Optional[str] = None,
        complaint_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Complaint]:
        """
        List complaints.
        
        Args:
            status: Filter by status
            complaint_type: Filter by type
            limit: Maximum number to return
            
        Returns:
            List of complaints
        """
        params = {"limit": limit}
        if status:
            params["status"] = status
        if complaint_type:
            params["complaint_type"] = complaint_type
        
        response = self.get("/api/complaints", params=params)
        complaints = response if isinstance(response, list) else response.get("complaints", [])
        
        return [
            Complaint(
                id=c.get("id", ""),
                complaint_type=c.get("complaint_type", ""),
                status=c.get("status", ""),
                title=c.get("title", ""),
                description=c.get("description"),
                agency=c.get("agency"),
            )
            for c in complaints
        ]
    
    def update(
        self,
        complaint_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        violations: Optional[List[str]] = None,
        status: Optional[str] = None,
    ) -> Complaint:
        """
        Update a complaint.
        
        Args:
            complaint_id: The complaint ID
            title: Updated title
            description: Updated description
            violations: Updated violations list
            status: Updated status
            
        Returns:
            Updated complaint
        """
        data = {}
        if title:
            data["title"] = title
        if description:
            data["description"] = description
        if violations:
            data["violations"] = violations
        if status:
            data["status"] = status
        
        response = self.patch(f"/api/complaints/{complaint_id}", json=data)
        
        return Complaint(
            id=response.get("id", complaint_id),
            complaint_type=response.get("complaint_type", ""),
            status=response.get("status", status or ""),
            title=response.get("title", title or ""),
            description=response.get("description", description),
            violations=response.get("violations", violations or []),
        )
    
    def submit(self, complaint_id: str, agency: str) -> Dict[str, Any]:
        """
        Submit a complaint to a regulatory agency.
        
        Args:
            complaint_id: The complaint ID
            agency: Target agency identifier
            
        Returns:
            Submission confirmation with tracking info
        """
        return self.post(
            f"/api/complaints/{complaint_id}/submit",
            json={"agency": agency},
        )
    
    def add_document(self, complaint_id: str, document_id: str) -> bool:
        """
        Add a document to a complaint.
        
        Args:
            complaint_id: The complaint ID
            document_id: Document ID to attach
            
        Returns:
            True if added successfully
        """
        self.post(
            f"/api/complaints/{complaint_id}/documents",
            json={"document_id": document_id},
        )
        return True
    
    def get_templates(
        self,
        agency_type: Optional[str] = None,
        complaint_type: Optional[str] = None,
    ) -> List[ComplaintTemplate]:
        """
        Get available complaint templates.
        
        Args:
            agency_type: Filter by agency type
            complaint_type: Filter by complaint type
            
        Returns:
            List of complaint templates
        """
        params = {}
        if agency_type:
            params["agency_type"] = agency_type
        if complaint_type:
            params["complaint_type"] = complaint_type
        
        response = self.get("/api/complaints/templates", params=params)
        templates = response if isinstance(response, list) else response.get("templates", [])
        
        return [
            ComplaintTemplate(
                id=t.get("id", ""),
                name=t.get("name", ""),
                description=t.get("description", ""),
                agency_type=t.get("agency_type", ""),
                required_fields=t.get("required_fields", []),
                optional_fields=t.get("optional_fields", []),
                instructions=t.get("instructions", ""),
            )
            for t in templates
        ]
    
    def get_agencies(
        self,
        jurisdiction: Optional[str] = None,
        agency_type: Optional[str] = None,
    ) -> List[Agency]:
        """
        Get list of regulatory agencies.
        
        Args:
            jurisdiction: Filter by jurisdiction
            agency_type: Filter by agency type
            
        Returns:
            List of agencies
        """
        params = {}
        if jurisdiction:
            params["jurisdiction"] = jurisdiction
        if agency_type:
            params["agency_type"] = agency_type
        
        response = self.get("/api/complaints/agencies", params=params)
        agencies = response if isinstance(response, list) else response.get("agencies", [])
        
        return [
            Agency(
                id=a.get("id", ""),
                name=a.get("name", ""),
                agency_type=a.get("agency_type", ""),
                jurisdiction=a.get("jurisdiction", ""),
                contact_info=a.get("contact_info", {}),
                filing_methods=a.get("filing_methods", []),
                estimated_response_time=a.get("estimated_response_time"),
            )
            for a in agencies
        ]
    
    def delete_complaint(self, complaint_id: str) -> bool:
        """
        Delete a complaint.
        
        Args:
            complaint_id: The complaint ID
            
        Returns:
            True if deleted successfully
        """
        self.delete(f"/api/complaints/{complaint_id}")
        return True
    
    def generate_pdf(self, complaint_id: str) -> bytes:
        """
        Generate a PDF version of the complaint.
        
        Args:
            complaint_id: The complaint ID
            
        Returns:
            PDF content as bytes
        """
        response = self.client.get(f"/api/complaints/{complaint_id}/pdf")
        return response.content
