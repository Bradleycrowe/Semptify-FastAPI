# Semptify Python SDK

A comprehensive Python client library for the Semptify 5.0 API. Provides typed access to all Semptify services for tenant rights protection.

## Installation

```bash
pip install semptify-sdk
# Or install from source:
pip install -e ./sdk
```

## Quick Start

```python
from sdk import SemptifyClient

# Initialize the client
client = SemptifyClient(base_url="http://localhost:8000")

# Authenticate via OAuth
auth_url = client.auth.get_auth_url("google")
# User completes OAuth flow and returns with code
client.login("google", code="auth_code_from_callback")

# Upload a document
doc = client.documents.upload("lease_agreement.pdf")

# Process through intake engine
intake_doc = client.documents.intake_upload("eviction_notice.pdf")

# Get AI-powered case analysis
analysis = client.copilot.analyze_case()

# Check upcoming deadlines
deadlines = client.timeline.get_deadlines(days_ahead=30)

# File a complaint
complaint = client.complaints.create(
    complaint_type="habitability",
    title="Mold and Water Damage",
    description="Persistent mold issue not addressed by landlord",
    violations=["failure_to_repair", "health_hazard"]
)
```

## Features

### Authentication (`client.auth`)

```python
# Get available storage providers
providers = client.auth.get_providers()

# Get OAuth URL for a provider
url = client.auth.get_auth_url("google")

# Complete OAuth flow
user = client.auth.complete_oauth("google", code)

# Get current user
user = client.auth.get_current_user()

# Logout
client.auth.logout()
```

### Document Management (`client.documents`)

```python
# Upload a document
doc = client.documents.upload(
    file="path/to/document.pdf",
    document_type="lease",
    tags=["important", "contract"]
)

# Upload through intake engine for auto-processing
intake_doc = client.documents.intake_upload("document.pdf")

# Get document
doc = client.documents.get_document("doc_id")

# List documents
docs = client.documents.list_documents(document_type="lease")

# Download document
content = client.documents.download("doc_id", "output.pdf")

# Get critical issues from processed documents
issues = client.documents.get_critical_issues()

# Get upcoming deadlines
deadlines = client.documents.get_upcoming_deadlines(days=14)
```

### Timeline & Deadlines (`client.timeline`)

```python
from datetime import date

# Add an event
event = client.timeline.add_event(
    event_type="notice_received",
    title="3-Day Notice Received",
    event_date=date.today(),
    importance="critical"
)

# Get events
events = client.timeline.get_events(
    start_date=date(2024, 1, 1),
    event_type="notice_received"
)

# Get upcoming deadlines
deadlines = client.timeline.get_deadlines(days_ahead=30)

# Calculate statute of limitations
statute = client.timeline.calculate_statute(
    violation_type="habitability",
    jurisdiction="california",
    incident_date=date(2024, 1, 15)
)

# Get timeline summary
summary = client.timeline.get_timeline_summary()
```

### AI Copilot (`client.copilot`)

```python
# Chat with the copilot
response = client.copilot.chat(
    message="What are my options for responding to this eviction notice?",
    conversation_type="case_strategy"
)

# Get comprehensive case analysis
analysis = client.copilot.analyze_case(
    include_documents=True,
    include_timeline=True
)

# Analyze a specific document
doc_analysis = client.copilot.analyze_document(
    document_id="doc_123",
    analysis_type="comprehensive"
)

# Draft a letter
letter = client.copilot.draft_letter(
    letter_type="demand",
    recipient="Landlord",
    key_points=["Repair request ignored", "Health hazard"],
    tone="firm"
)

# Get recommendations
recommendations = client.copilot.get_recommendations(urgency="high")
```

### Complaint Management (`client.complaints`)

```python
# Create a complaint
complaint = client.complaints.create(
    complaint_type="habitability",
    title="Mold and Water Damage",
    description="...",
    violations=["failure_to_repair"]
)

# Get complaint
complaint = client.complaints.get_complaint("complaint_id")

# List complaints
complaints = client.complaints.list_complaints(status="submitted")

# Submit to agency
result = client.complaints.submit("complaint_id", agency="hud")

# Add document to complaint
client.complaints.add_document("complaint_id", "doc_id")

# Get available templates
templates = client.complaints.get_templates(agency_type="hud")

# Get regulatory agencies
agencies = client.complaints.get_agencies(jurisdiction="california")

# Generate PDF
pdf_content = client.complaints.generate_pdf("complaint_id")
```

### Briefcase (`client.briefcase`)

```python
# Create a briefcase
briefcase = client.briefcase.create(
    name="Habitability Case",
    case_type="habitability"
)

# Add document
item = client.briefcase.add_document(
    briefcase_id="bc_123",
    document_id="doc_456",
    tags=["evidence"]
)

# Add note
note = client.briefcase.add_note(
    briefcase_id="bc_123",
    title="Inspection Notes",
    content="..."
)

# Get items
items = client.briefcase.get_items("bc_123", item_type="document")

# Export briefcase
export = client.briefcase.export("bc_123", format="pdf")

# Share briefcase
client.briefcase.share("bc_123", email="lawyer@example.com")
```

### Vault (Secure Storage) (`client.vault`)

```python
from sdk.vault import VaultPermission

# Add item to vault
item = client.vault.add_item(
    name="Sensitive Document",
    document_id="doc_123",
    encrypt=True
)

# Grant access
access = client.vault.grant_access(
    item_id="item_123",
    email="user@example.com",
    permission=VaultPermission.VIEW,
    expires_in_days=7
)

# Get audit log
audit = client.vault.get_audit_log(item_id="item_123")

# Get vault stats
stats = client.vault.get_stats()

# Lock/unlock vault
client.vault.lock()
client.vault.unlock(password="optional")
```

## Error Handling

```python
from sdk.exceptions import (
    SemptifyError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
    StorageRequiredError,
)

try:
    doc = client.documents.get_document("invalid_id")
except NotFoundError as e:
    print(f"Document not found: {e.message}")
except AuthenticationError as e:
    print(f"Authentication failed: {e.message}")
except StorageRequiredError as e:
    print(f"Storage connection required: {e.redirect_url}")
except ValidationError as e:
    print(f"Validation error: {e.errors}")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after} seconds")
except ServerError as e:
    print(f"Server error: {e.message}")
except SemptifyError as e:
    print(f"API error: {e.message}")
```

## Async Support

All client methods have async variants prefixed with `a`:

```python
import asyncio

async def main():
    async with SemptifyClient() as client:
        # Async operations
        health = await client.ahealth_check()
        
        # Or use async client methods directly
        response = await client.auth.async_client.get("/api/auth/providers")

asyncio.run(main())
```

## Context Manager

```python
# Sync context manager
with SemptifyClient() as client:
    docs = client.documents.list_documents()

# Async context manager
async with SemptifyClient() as client:
    docs = await client.documents.alist_documents()
```

## Configuration

```python
client = SemptifyClient(
    base_url="http://localhost:8000",  # API base URL
    api_key="your_api_key",             # Optional API key
    timeout=30.0,                       # Request timeout
    user_id="user_123",                 # Optional user ID
)
```

## Data Classes

The SDK provides typed data classes for all responses:

- `UserInfo` - User information
- `Document` - Document metadata
- `IntakeDocument` - Intake processing results
- `TimelineEvent` - Timeline event
- `Deadline` - Deadline information
- `StatuteInfo` - Statute of limitations
- `Complaint` - Complaint details
- `Briefcase` - Briefcase details
- `BriefcaseItem` - Briefcase item
- `VaultItem` - Vault item
- `VaultAccess` - Access record
- `CaseAnalysis` - AI case analysis
- `DraftResponse` - AI-generated draft

## Version

SDK version: 5.0.0
