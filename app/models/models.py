"""
Semptify Database Models
SQLAlchemy ORM models for all entities.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

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
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="linked_providers")
# =============================================================================
# Document Vault
# =============================================================================

class Document(Base):
    """
    Document stored in the vault with certification.
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
    
    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
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
    event_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    
    # Linked document (optional)
    document_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)
    
    # Importance for court
    is_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
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
    payment_date: Mapped[datetime] = mapped_column(DateTime)
    due_date: Mapped[datetime] = mapped_column(DateTime)
    
    # Status
    status: Mapped[str] = mapped_column(String(20))  # paid, late, partial, missed
    
    # Method and confirmation
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confirmation_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Linked receipt document
    receipt_document_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
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
    start_datetime: Mapped[datetime] = mapped_column(DateTime)
    end_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Type and urgency
    event_type: Mapped[str] = mapped_column(String(50))  # deadline, hearing, reminder, appointment
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)  # Affects intensity engine
    
    # Reminders (days before)
    reminder_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# =============================================================================
# Complaints
# =============================================================================

class Complaint(Base):
    """
    Formal complaint being filed.
    """
    __tablename__ = "complaints"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # Type and status
    complaint_type: Mapped[str] = mapped_column(String(50))  # habitability, discrimination, retaliation, etc.
    status: Mapped[str] = mapped_column(String(20))  # draft, submitted, acknowledged, resolved
    
    # Target
    target_type: Mapped[str] = mapped_column(String(50))  # landlord, property_manager, hoa
    target_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Description
    summary: Mapped[str] = mapped_column(String(500))
    detailed_description: Mapped[Text] = mapped_column(Text)
    
    # Filing info
    filed_with: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Agency/court name
    filing_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    case_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    statement_date: Mapped[datetime] = mapped_column(DateTime)
    
    # Verification
    is_notarized: Mapped[bool] = mapped_column(Boolean, default=False)
    document_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    sent_date: Mapped[datetime] = mapped_column(DateTime)
    delivered_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Linked document (copy of what was sent)
    document_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    authenticated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Role authorization tracking
    role_authorized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


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
    last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Connected providers (JSON list of provider names)
    connected_providers: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # e.g., "google_drive,dropbox"

    # Feature flags
    backup_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Secondary provider for backup

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)