"""
Semptify Database Models
SQLAlchemy ORM models for all entities.

All datetime columns use DateTime(timezone=True) for proper UTC handling.
Use utc_now() from app.core.utc for all timestamp defaults.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utc import utc_now


# Type alias for timezone-aware DateTime columns
DateTimeTZ = DateTime(timezone=True)


# =============================================================================
# User Model (Storage-Based Auth)
# =============================================================================

class User(Base):
    """
    User account - storage-based authentication.
    
    Identity comes from cloud storage (Google Drive, Dropbox, OneDrive).
    The user_id is derived from provider:storage_user_id hash.
    
    This table stores:
    - Which provider they primarily use (for re-auth)
    - Their preferred role (to restore on return)
    - Profile info from the storage provider
    """
    __tablename__ = "users"

    # Primary key: derived from provider:storage_user_id hash (24 chars)
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    
    # Storage provider info (to know where to look for token on return)
    primary_provider: Mapped[str] = mapped_column(String(20), index=True)  # google_drive, dropbox, onedrive
    storage_user_id: Mapped[str] = mapped_column(String(100))  # ID in the storage provider
    
    # Role preference (restored on return)
    default_role: Mapped[str] = mapped_column(String(20), default="user")  # user, manager, advocate, legal, admin
    
    # Profile (from storage provider)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Intensity Engine (tenant-specific feature)
    intensity_level: Mapped[str] = mapped_column(String(10), default="low")  # low, medium, high
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now, onupdate=utc_now)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)

    # Relationships
    documents: Mapped[list["Document"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    rent_payments: Mapped[list["RentPayment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    linked_providers: Mapped[list["LinkedProvider"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# =============================================================================
# Linked Storage Providers (Multi-Provider Support)
# =============================================================================

class LinkedProvider(Base):
    """
    Additional storage providers linked to a user account.
    
    A user authenticates with one provider initially (becomes primary).
    They can later link additional providers for backup/sync.
    """
    __tablename__ = "linked_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(24), ForeignKey("users.id"), index=True)
    
    # Provider info
    provider: Mapped[str] = mapped_column(String(20))  # google_drive, dropbox, onedrive
    storage_user_id: Mapped[str] = mapped_column(String(100))  # ID in this provider
    
    # Profile from this provider
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    linked_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="linked_providers")
# =============================================================================
# Document Vault
# =============================================================================

class Document(Base):
    """
    Document stored in the vault with certification.
    
    Privilege Levels:
    - is_privileged=False: Normal tenant document (visible to tenant, advocate, attorney)
    - is_privileged=True: Attorney-client privileged (visible ONLY to creating attorney + client)
    - is_work_product=True: Attorney work product (protected from discovery)
    """
    __tablename__ = "documents"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # File info
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(100))
    
    # Certification
    sha256_hash: Mapped[str] = mapped_column(String(64))
    certificate_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Metadata
    document_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # lease, notice, photo, etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # comma-separated
    
    # ==========================================================================
    # ATTORNEY-CLIENT PRIVILEGE FLAGS
    # ==========================================================================
    is_privileged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    """Attorney-client privileged document. Only visible to creating attorney and the client."""
    
    is_work_product: Mapped[bool] = mapped_column(Boolean, default=False)
    """Attorney work product. Protected from discovery even in litigation."""
    
    created_by_role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    """Role of user who created this document (user, advocate, legal, admin)."""
    
    attorney_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    """If privileged, the attorney who created it (for privilege verification)."""
    
    privilege_waived: Mapped[bool] = mapped_column(Boolean, default=False)
    """If True, client has explicitly waived privilege on this document."""
    
    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="documents")


# =============================================================================
# Timeline Events
# =============================================================================

class TimelineEvent(Base):
    """
    Events in the tenant's timeline.
    """
    __tablename__ = "timeline_events"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # Event details
    event_type: Mapped[str] = mapped_column(String(50))  # notice, payment, maintenance, communication, court
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # When it happened
    event_date: Mapped[datetime] = mapped_column(DateTimeTZ, index=True)
    
    # Linked document (optional) - stores doc ID from file-based pipeline, not FK
    document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Importance for court
    is_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="timeline_events")


# =============================================================================
# Rent Ledger
# =============================================================================

class RentPayment(Base):
    """
    Rent payment record for the ledger.
    """
    __tablename__ = "rent_payments"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # Payment details
    amount: Mapped[int] = mapped_column(Integer)  # Store in cents to avoid float issues
    payment_date: Mapped[datetime] = mapped_column(DateTimeTZ)
    due_date: Mapped[datetime] = mapped_column(DateTimeTZ)
    
    # Status
    status: Mapped[str] = mapped_column(String(20))  # paid, late, partial, missed
    
    # Method and confirmation
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confirmation_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Linked receipt document (stores doc ID from file-based pipeline, not FK)
    receipt_document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="rent_payments")


# =============================================================================
# Calendar / Deadlines
# =============================================================================

class CalendarEvent(Base):
    """
    Calendar event or deadline.
    """
    __tablename__ = "calendar_events"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # Event details
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timing
    start_datetime: Mapped[datetime] = mapped_column(DateTimeTZ)
    end_datetime: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Type and urgency
    event_type: Mapped[str] = mapped_column(String(50))  # deadline, hearing, reminder, appointment
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)  # Affects intensity engine
    
    # Reminders (days before)
    reminder_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)


# =============================================================================
# Complaints
# =============================================================================

class Complaint(Base):
    """
    Formal complaint being filed with regulatory agencies.
    Extended for Complaint Wizard with full draft support.
    """
    __tablename__ = "complaints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)

    # Agency info
    agency_id: Mapped[str] = mapped_column(String(50), index=True)  # e.g., mn_ag_consumer, hud_fair_housing

    # Type and status
    complaint_type: Mapped[str] = mapped_column(String(50))  # habitability, discrimination, retaliation, etc.
    status: Mapped[str] = mapped_column(String(20))  # draft, ready, filed, acknowledged, investigating, resolved, closed

    # Subject and description
    subject: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[str] = mapped_column(String(500), default="")
    detailed_description: Mapped[Text] = mapped_column(Text, default="")

    # Incident info
    incident_dates: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of dates
    damages_claimed: Mapped[Optional[float]] = mapped_column(nullable=True)
    relief_sought: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Target/Respondent info
    target_type: Mapped[str] = mapped_column(String(50), default="landlord")  # landlord, property_manager, hoa
    target_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Evidence
    attached_document_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of doc IDs
    timeline_included: Mapped[bool] = mapped_column(Boolean, default=False)

    # Filing info
    filed_with: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Agency name
    filing_date: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)
    case_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confirmation_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now, onupdate=utc_now)
# =============================================================================
# Witness Statements
# =============================================================================

class WitnessStatement(Base):
    """
    Third-party witness statement.
    """
    __tablename__ = "witness_statements"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # Witness info
    witness_name: Mapped[str] = mapped_column(String(255))
    witness_relationship: Mapped[str] = mapped_column(String(100))  # neighbor, family, friend, professional
    witness_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Statement
    statement_text: Mapped[Text] = mapped_column(Text)
    statement_date: Mapped[datetime] = mapped_column(DateTimeTZ)
    
    # Verification
    is_notarized: Mapped[bool] = mapped_column(Boolean, default=False)
    document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # File-based doc ID
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)


# =============================================================================
# Certified Mail Tracking
# =============================================================================

class CertifiedMail(Base):
    """
    Certified mail tracking record.
    """
    __tablename__ = "certified_mail"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)

    # Mail details
    tracking_number: Mapped[str] = mapped_column(String(50))
    recipient_name: Mapped[str] = mapped_column(String(255))
    recipient_address: Mapped[str] = mapped_column(Text)
    
    # Purpose
    mail_type: Mapped[str] = mapped_column(String(50))  # notice, demand_letter, complaint, other
    subject: Mapped[str] = mapped_column(String(255))

    # Status tracking
    status: Mapped[str] = mapped_column(String(50))  # sent, in_transit, delivered, returned
    sent_date: Mapped[datetime] = mapped_column(DateTimeTZ)
    delivered_date: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)

    # Linked document (copy of what was sent) - stores file-based doc ID
    document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)


# =============================================================================
# Session (Persistent OAuth Sessions)
# =============================================================================

class Session(Base):
    """
    Persistent OAuth session.
    
    Replaces in-memory SESSIONS dict so sessions survive server restarts.
    Tokens are stored encrypted using the user's derived key.
    """
    __tablename__ = "sessions"

    # Primary key is the user_id (one session per user)
    user_id: Mapped[str] = mapped_column(String(24), primary_key=True)

    # Provider info
    provider: Mapped[str] = mapped_column(String(20))  # google_drive, dropbox, onedrive

    # Encrypted tokens (encrypted with user-specific key)
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Session metadata
    authenticated_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)
    last_activity: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now, onupdate=utc_now)

    # Role authorization tracking
    role_authorized_at: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)


# =============================================================================
# Storage Config (User's Storage Settings)
# =============================================================================

class StorageConfig(Base):
    """
    User's storage configuration.
    
    Persists storage-related settings so they survive across sessions:
    - Which cloud providers are connected
    - R2 bucket settings
    - Sync preferences
    - Default vault structure
    
    This is the key model that was missing - without it, users lose
    their storage configuration when sessions expire.
    """
    __tablename__ = "storage_configs"

    # Primary key is the user_id (one config per user)
    user_id: Mapped[str] = mapped_column(String(24), primary_key=True)

    # Primary storage provider (where auth_token.enc lives)
    primary_provider: Mapped[str] = mapped_column(String(20))  # google_drive, dropbox, onedrive

    # R2 Configuration (for document storage)
    r2_bucket_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    r2_account_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    r2_access_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    r2_secret_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Vault structure preferences
    vault_folder_path: Mapped[str] = mapped_column(String(500), default="/Semptify")  # Root folder in cloud storage
    auto_organize: Mapped[bool] = mapped_column(Boolean, default=True)  # Auto-organize by document type

    # Sync settings
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    last_sync: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)

    # Connected providers (JSON list of provider names)
    connected_providers: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # e.g., "google_drive,dropbox"

    # Feature flags
    backup_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Secondary provider for backup

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now, onupdate=utc_now)


# =============================================================================
# Fraud Analysis Results
# =============================================================================

class FraudAnalysisResult(Base):
    """
    Results from fraud pattern analysis on landlord/property.
    """
    __tablename__ = "fraud_analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # Analysis target
    analysis_type: Mapped[str] = mapped_column(String(50))  # hud, mortgage, habitability, eviction
    target_entity: Mapped[str] = mapped_column(String(255), index=True)  # landlord/company name
    property_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Results
    risk_score: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown")  # low, medium, high, critical
    findings: Mapped[Text] = mapped_column(Text, default="")  # JSON formatted findings
    indicators: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of indicators
    recommendations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Evidence links
    evidence_doc_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of doc IDs
    related_complaints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="completed")
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now, onupdate=utc_now)


# =============================================================================
# Press Release Records
# =============================================================================

class PressReleaseRecord(Base):
    """
    Press release generation and media campaign tracking.
    """
    __tablename__ = "press_release_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # Content
    release_type: Mapped[str] = mapped_column(String(50))  # discrimination, code_violations, fraud, etc.
    title: Mapped[str] = mapped_column(String(500))
    headline: Mapped[str] = mapped_column(String(500))
    language: Mapped[str] = mapped_column(String(10), default="en")  # en, es, hmn, so
    content: Mapped[Text] = mapped_column(Text, default="")
    
    # Targeting
    target_outlets: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of outlets
    target_region: Mapped[str] = mapped_column(String(100), default="Minnesota")
    
    # Media kit reference
    media_kit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, published, sent
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now, onupdate=utc_now)


# =============================================================================
# Research Profiles
# =============================================================================

class ResearchProfile(Base):
    """
    Landlord/entity research profile with aggregated findings.
    """
    __tablename__ = "research_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # Entity identification
    entity_type: Mapped[str] = mapped_column(String(50))  # landlord, llc, property_manager
    entity_name: Mapped[str] = mapped_column(String(255), index=True)
    property_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # Research data (JSON format)
    assessor_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorder_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ucc_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dispatch_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    news_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sos_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bankruptcy_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    insurance_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Aggregated findings
    normalized_profile: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    fraud_flags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    
    # Sources tracking
    sources_checked: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress, complete, stale

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now, onupdate=utc_now)


# =============================================================================
# Contact Manager
# =============================================================================

class Contact(Base):
    """
    Contact management for case-related people and organizations.
    Tracks landlords, attorneys, witnesses, inspectors, agencies, etc.
    """
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)

    # Contact Type
    contact_type: Mapped[str] = mapped_column(String(50), index=True)
    # Types: landlord, property_manager, attorney, witness, inspector, 
    #        agency, court, legal_aid, tenant_org, other

    # Role in case
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Roles: opposing_party, opposing_counsel, my_witness, their_witness,
    #        inspector, caseworker, judge, mediator, etc.

    # Basic Info
    name: Mapped[str] = mapped_column(String(255), index=True)
    organization: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Contact Details
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone_alt: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fax: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    zip_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Additional Info
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Comma-separated

    # Source tracking (where did this contact come from?)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Sources: manual, extracted, imported, agency_lookup

    source_document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Interaction tracking
    last_contact_date: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now, onupdate=utc_now)


class ContactInteraction(Base):
    """
    Log of interactions with contacts (calls, emails, meetings).
    """
    __tablename__ = "contact_interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    contact_id: Mapped[str] = mapped_column(String(36), ForeignKey("contacts.id"), index=True)

    # Interaction details
    interaction_type: Mapped[str] = mapped_column(String(50))
    # Types: phone_call, email, letter, in_person, court_appearance, voicemail

    direction: Mapped[str] = mapped_column(String(20))  # incoming, outgoing

    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Dates
    interaction_date: Mapped[datetime] = mapped_column(DateTimeTZ)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Attachments/Documents
    related_document_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    # Follow-up
    follow_up_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_up_date: Mapped[Optional[datetime]] = mapped_column(DateTimeTZ, nullable=True)
    follow_up_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTimeTZ, default=utc_now)
