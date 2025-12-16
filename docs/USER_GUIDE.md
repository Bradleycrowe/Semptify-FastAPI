# Semptify 5.0 User Guide

> **Your Tenant Rights Protection Platform**  
> Help tenants with tools and information to uphold tenant rights as a renter, in court if it goes that far - hopefully it won't.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Creating Your First Tenancy Case](#creating-your-first-tenancy-case)
3. [My Tenancy Page - Data Entry](#my-tenancy-page---data-entry)
4. [Legal Analysis Engine](#legal-analysis-engine)
5. [Document Management](#document-management)
6. [Timeline & Calendar](#timeline--calendar)
7. [Eviction Defense Tools](#eviction-defense-tools)
8. [Brain Mesh - System Overview](#brain-mesh---system-overview)
9. [Troubleshooting](#troubleshooting)

---

## Getting Started

### First-Time Setup

1. **Navigate to Semptify**: Open your browser to `http://localhost:8000`
2. **Connect Storage** (Optional but Recommended):
   - Click **"Connect with Google Drive"** (or Dropbox/OneDrive)
   - This enables secure cloud backup of your documents
   - Your data stays in YOUR storage - we never store it on our servers

### Main Navigation

| Page | URL | Purpose |
|------|-----|---------|
| 🏠 Dashboard | `/dashboard.html` | Overview of your cases and deadlines |
| 📋 My Tenancy | `/my_tenancy.html` | Create and manage tenancy cases |
| ⚖️ Legal Analysis | `/legal_analysis.html` | Analyze your case strength |
| 📄 Documents | `/documents.html` | Upload and manage documents |
| 📅 Timeline | `/timeline.html` | Track important dates and events |
| 🛡️ Eviction Defense | `/eviction-defense` | Generate motions and defenses |
| 🧠 Brain Mesh | `/brain.html` | System status and module connections |

---

## Creating Your First Tenancy Case

### What is a Tenancy Case?

A **Tenancy Case** is a container that holds all information about your rental situation:
- Your personal info (tenant)
- Landlord/property manager info
- Property details
- Lease terms
- Payment history
- Documents
- Timeline events
- Legal issues

### Step 1: Go to My Tenancy

Navigate to **`/my_tenancy.html`** or click "My Tenancy" in the navigation.

### Step 2: Create a New Case

1. Click the **"+ New Case"** button (top right)
2. Enter a case name (e.g., "123 Main St Apartment" or "2024 Eviction Defense")
3. Click **Create**

Your new case will appear in the case selector dropdown.

---

## My Tenancy Page - Data Entry

The My Tenancy page is organized into **stages** - complete each stage to build your case:

### Stage 1: Tenant Information (You)

| Field | Description | Example |
|-------|-------------|---------|
| Full Name | Your legal name | John Smith |
| Address | Your current mailing address | 123 Main St, Apt 4B |
| City/State/ZIP | Location | Minneapolis, MN 55401 |
| Phone | Best contact number | (612) 555-1234 |
| Email | Your email address | john.smith@email.com |

**Why it matters**: This information appears on legal documents and court filings.

### Stage 2: Landlord Information

| Field | Description | Example |
|-------|-------------|---------|
| Name | Landlord or property manager | Jane Doe |
| Company Name | Management company (if applicable) | ABC Property Management |
| Address | Their business address | 456 Business Blvd |
| City/State/ZIP | Location | Minneapolis, MN 55402 |
| Phone | Their contact number | (612) 555-5678 |
| Email | Their email | manager@abcproperty.com |

**Tip**: Look on your lease for the correct legal entity name. It might be an LLC.

### Stage 3: Property Details

| Field | Description | Example |
|-------|-------------|---------|
| Street Address | Rental property address | 123 Main Street |
| Unit Number | Apartment/unit number | 4B |
| City/State/ZIP | Property location | Minneapolis, MN 55401 |
| County | Important for court filings | Hennepin |
| Property Type | apartment, house, condo, etc. | apartment |
| Bedrooms | Number of bedrooms | 2 |
| Bathrooms | Number of bathrooms | 1 |
| Square Feet | Size of unit | 850 |

**Why County matters**: Eviction cases are filed in the county where the property is located.

### Stage 4: Lease Terms

| Field | Description | Example |
|-------|-------------|---------|
| Lease Start Date | When your lease began | 2024-01-01 |
| Lease End Date | When your lease expires | 2024-12-31 |
| Monthly Rent | Rent amount | $1,200.00 |
| Security Deposit | Amount held by landlord | $1,200.00 |
| Rent Due Day | Day of month rent is due | 1 |
| Grace Period | Days before late fee applies | 5 |
| Late Fee Amount | Fee charged if late | $50.00 |
| Lease Type | fixed or month-to-month | fixed |
| Notice to Vacate | Days notice required | 30 |

**Critical**: These terms affect your legal rights. Double-check against your actual lease.

### Stage 5: Payment History

Track all rent payments to prove your payment history:

| Field | Description | Example |
|-------|-------------|---------|
| Payment Date | When you paid | 2024-11-01 |
| Due Date | When it was due | 2024-11-01 |
| Amount | Amount paid | $1,200.00 |
| Payment Type | rent, deposit, fee, etc. | rent |
| Payment Method | How you paid | check |
| Status | completed, pending, bounced | completed |
| Receipt Number | Any receipt/confirmation | REC-2024-1101 |
| Check Number | If paid by check | 1234 |

**Important**: Keep records! Payment disputes are common in eviction cases.

### Stage 6: Documents

Upload and organize all relevant documents:

| Category | Examples |
|----------|----------|
| lease | Signed lease agreement |
| notice | Any notices received (eviction, rent increase, etc.) |
| communication | Emails, texts, letters with landlord |
| receipt | Rent receipts, payment confirmations |
| photo | Photos of property condition, repairs needed |
| court | Court filings, summons, complaints |
| other | Anything else relevant |

### Stage 7: Timeline Events

Document important events chronologically:

| Event Type | Examples |
|------------|----------|
| notice | Received 14-day notice on Nov 1 |
| filing | Landlord filed eviction on Nov 15 |
| hearing | Court hearing scheduled Dec 1 |
| deadline | Answer due by Nov 22 |
| milestone | Lease signed, moved in, etc. |

### Stage 8: Issues & Problems

Document any problems with the rental:

| Field | Description |
|-------|-------------|
| Category | maintenance, habitability, lease_violation, harassment |
| Severity | low, medium, high, critical |
| Title | Brief description |
| Description | Detailed explanation |
| Location | Where in the property |
| Is Habitability Issue? | Affects safety/livability |
| Is Lease Violation? | Landlord violated lease |
| Violates Statute | Legal code violated (if known) |

**Habitability Issues** (landlord MUST fix):
- No heat in winter
- No running water
- Broken locks/security
- Pest infestation
- Mold problems
- Electrical hazards

---

## Legal Analysis Engine

### Accessing Legal Analysis

Navigate to **`/legal_analysis.html`** after creating your tenancy case.

### Step 1: Select Your Case

1. Use the dropdown menu labeled **"Select Case to Analyze"**
2. Choose your tenancy case from the list
3. If no cases appear, go back to My Tenancy and create one first

### Step 2: Run Quick Health Check

Click **"🔍 Quick Check"** to get an instant assessment:

| Check | What It Analyzes |
|-------|------------------|
| 📊 Evidence | Do you have enough documents to support your case? |
| 🔄 Consistency | Is your story consistent across documents and timeline? |
| ⏱️ Timeline | Are all deadlines accounted for? Any conflicts? |
| 📋 Documentation | Is your documentation complete? |

### Understanding the Results

**Health Status Colors:**
- 🟢 **Green (Healthy)**: This area is strong
- 🟡 **Yellow (Warning)**: Needs attention
- 🔴 **Red (Critical)**: Major issue to address

### Step 3: Deep Analysis (Tabs)

#### Evidence Tab
Shows all your evidence organized by type:
- Documents
- Photos
- Communications
- Receipts

**Tip**: Upload more documents to strengthen weak areas.

#### Timeline Tab
Visual representation of your case chronology:
- Notices received
- Deadlines
- Court dates
- Important events

#### Issues Tab
Problems identified with your case:
- Missing documents
- Timeline gaps
- Conflicting information
- Expired deadlines

#### Motions Tab
Suggested legal motions based on your situation:
- Motion to Dismiss
- Motion for Continuance
- Request for Jury Trial
- Counterclaims

### Step 4: Export Report

Click **"📄 Export Full Report"** to generate a PDF summary of your legal analysis.

---

## Document Management

### Uploading Documents

1. Go to **`/documents.html`** or **`/document_intake.html`**
2. Click **"Upload Document"** or drag-and-drop files
3. Supported formats: PDF, DOC, DOCX, JPG, PNG, TXT

### Document Processing

Semptify automatically:
- Extracts text (OCR for images)
- Identifies document type
- Extracts key dates, names, amounts
- Detects potential legal issues
- Links to your tenancy case

### Document Categories

| Category | Use For |
|----------|---------|
| lease | Lease agreements, renewals |
| notice | Eviction notices, rent increase notices |
| court_filing | Summons, complaints, motions |
| communication | Emails, letters, text screenshots |
| receipt | Payment receipts, bank statements |
| photo | Property condition photos |
| inspection | Inspection reports |
| other | Everything else |

### Document Registry

The Document Registry (**`/document_intake.html`** → Registry tab) provides:
- Chain of custody tracking
- Forgery detection scores
- Document verification
- Duplicate detection

---

## Timeline & Calendar

### Timeline Page (`/timeline.html`)

Shows all events in chronological order:
- Past events (what happened)
- Upcoming deadlines (what's due)
- Future hearings (what's scheduled)

### Calendar Page (`/calendar.html`)

Monthly/weekly view of:
- Court dates
- Filing deadlines
- Notice periods
- Payment due dates

### Adding Events

1. Click **"+ Add Event"**
2. Select event type:
   - Notice
   - Filing
   - Hearing
   - Deadline
   - Milestone
3. Enter date, time, and description
4. Link to relevant documents (optional)

### Deadline Alerts

Semptify calculates important deadlines:
- **14-day notice period** (MN non-payment)
- **Answer due date** (typically 7-14 days after service)
- **Appeal deadlines**
- **Redemption periods**

---

## Eviction Defense Tools

### Accessing Eviction Defense

Navigate to **`/eviction-defense`** for specialized tools.

### Motion Generator

Generate legal motions based on your case:

1. Select motion type
2. Review auto-filled information
3. Edit as needed
4. Download or print

**Common Motions:**
- Motion to Dismiss (procedural defects)
- Motion for Continuance (more time needed)
- Answer with Affirmative Defenses
- Demand for Jury Trial
- Counterclaim (landlord owes you money)

### Defense Strategies

Based on your case data, Semptify suggests defenses:

| Defense | When It Applies |
|---------|-----------------|
| Improper Notice | Notice period too short or wrong form |
| Retaliation | Eviction after you complained about repairs |
| Habitability | Landlord failed to maintain safe conditions |
| Payment Defense | You paid but landlord claims you didn't |
| Discrimination | Protected class targeting |
| Procedural | Court rules not followed |

### Minnesota-Specific Information

Semptify includes Minnesota tenant rights:
- **Minn. Stat. § 504B** - Landlord-Tenant laws
- Required notice periods
- Tenant remedies
- Court procedures

---

## Brain Mesh - System Overview

### What is Brain Mesh?

The **Brain Mesh** (`/brain.html`) is Semptify's central nervous system showing how all modules connect.

### Module Status

| Module | Function |
|--------|----------|
| 📄 Documents | Document storage and analysis |
| ⏱️ Timeline | Event tracking |
| 🏠 Tenancy | Case management |
| ⚖️ Legal | Legal analysis engine |
| 🤖 Copilot | AI assistance |
| 📊 Progress | Task tracking |

### Status Indicators

- 🟢 **Active**: Module running normally
- 🟡 **Idle**: Module available but not in use
- 🔴 **Error**: Module has a problem

### Real-Time Updates

Brain Mesh shows live updates:
- Document uploads
- Analysis completions
- Timeline changes
- System events

---

## Troubleshooting

### Common Issues

#### "No cases found" in Legal Analysis

**Solution**: Create a case first in My Tenancy (`/my_tenancy.html`)

#### Documents not appearing

**Solutions**:
1. Refresh the page
2. Check if document finished processing (status should be "ready")
3. Verify the document is linked to your case

#### Timeline dates showing "Invalid Date" or "NaN"

**Solution**: This has been fixed. Clear your browser cache and refresh.

#### Analysis shows all red/critical

**Solutions**:
1. Add more documents to your case
2. Complete all stages in My Tenancy
3. Add timeline events
4. Document any issues/problems

#### Can't select a case

**Solutions**:
1. Make sure you're logged in (storage connected)
2. Create a case first
3. Check browser console for errors (F12)

### Getting Help

1. **API Documentation**: Visit `/api/docs` for technical details
2. **System Status**: Check `/brain.html` for module health
3. **Logs**: Check browser console (F12 → Console)

---

## Quick Reference Card

### Key URLs

| Page | URL |
|------|-----|
| Dashboard | `/dashboard.html` |
| My Tenancy | `/my_tenancy.html` |
| Legal Analysis | `/legal_analysis.html` |
| Documents | `/documents.html` |
| Document Intake | `/document_intake.html` |
| Timeline | `/timeline.html` |
| Calendar | `/calendar.html` |
| Eviction Defense | `/eviction-defense` |
| Brain Mesh | `/brain.html` |
| API Docs | `/api/docs` |

### Workflow Summary

```
1. Create Case (My Tenancy)
      ↓
2. Add Your Info (Tenant details)
      ↓
3. Add Landlord Info
      ↓
4. Add Property Details
      ↓
5. Enter Lease Terms
      ↓
6. Upload Documents
      ↓
7. Add Timeline Events
      ↓
8. Document Issues
      ↓
9. Run Legal Analysis
      ↓
10. Generate Motions (if needed)
```

### Emergency Checklist

If you receive an **eviction notice**:

- [ ] **Don't panic** - you have legal rights
- [ ] **Read the notice carefully** - note the dates
- [ ] **Create a case** in Semptify immediately
- [ ] **Upload the notice** as a document
- [ ] **Calculate your deadlines** (use Timeline)
- [ ] **Gather evidence** of payments, communications
- [ ] **Run Legal Analysis** to find defenses
- [ ] **Consider legal aid** - see resources below

### Legal Aid Resources (Minnesota)

- **Legal Aid Society of Minneapolis**: 612-334-5970
- **Mid-Minnesota Legal Aid**: 612-332-1441
- **HOME Line (Tenant Hotline)**: 612-728-5767
- **Volunteer Lawyers Network**: 612-752-6677

---

## Version Information

- **Semptify Version**: 5.0
- **Guide Last Updated**: December 2024
- **Platform**: FastAPI + SQLite

---

*Semptify is designed to help tenants understand and exercise their legal rights. This tool provides information and organization - it is not a substitute for legal advice from a licensed attorney.*
