# SEMPTIFY COURT DEFENSE SYSTEM - MASTER BLUEPRINT
## Bi-Directional Data Flow Architecture

---

## 🎯 SYSTEM OVERVIEW

**Goal**: Create a seamless, interconnected legal defense system where all modules communicate bi-directionally, data flows automatically between components, and the user has a unified interactive GUI experience.

**Case**: 19AV-CV-25-3477 | Dakota County District Court | Brad Campbell v. Park Plaza Apartments

---

## 📊 CURRENT ASSETS INVENTORY

### ROUTERS (API Endpoints)
| Router | Purpose | Status |
|--------|---------|--------|
| `auth.py` | User authentication, OAuth | ⚠️ Needs integration |
| `vault.py` | Document storage/retrieval | ✅ Working |
| `timeline.py` | Case timeline events | ✅ Working |
| `calendar.py` | Deadlines, hearings | ⚠️ Needs integration |
| `copilot.py` | AI assistance | ⚠️ Needs API keys |
| `documents.py` | Document processing | ⚠️ Needs integration |
| `form_data.py` | Central data hub | ✅ Created |
| `storage.py` | Cloud storage OAuth | ⚠️ Needs testing |
| `adaptive_ui.py` | Dynamic UI config | ⚠️ Needs integration |
| `context_loop.py` | Event processing engine | ⚠️ Needs integration |
| `intake.py` | Document intake pipeline | ⚠️ Needs integration |
| `registry.py` | Chain of custody | ⚠️ Needs integration |
| `vault_engine.py` | Centralized access | ⚠️ Needs integration |
| `law_library.py` | Legal references | ✅ Working |
| `eviction_defense.py` | Defense toolkit | ✅ Working |
| `zoom_court.py` | Virtual court prep | ✅ Working |
| `eviction/*` | Dakota County flows | ✅ Working |

### SERVICES (Business Logic)
| Service | Purpose | Status |
|---------|---------|--------|
| `form_data.py` | Central data integration | ✅ Created |
| `document_pipeline.py` | Document processing | ⚠️ Needs integration |
| `document_intake.py` | Intake processing | ⚠️ Needs integration |
| `document_registry.py` | Integrity tracking | ⚠️ Needs integration |
| `event_extractor.py` | Extract dates/events | ⚠️ Needs integration |
| `vault_engine.py` | Storage management | ⚠️ Needs integration |
| `context_loop.py` | Processing engine | ⚠️ Needs integration |
| `adaptive_ui.py` | UI generation | ⚠️ Needs integration |
| `law_engine.py` | Legal analysis | ⚠️ Needs integration |
| `azure_ai.py` | Azure AI services | ⚠️ Needs API keys |
| `user_service.py` | User management | ⚠️ Needs integration |

### STATIC PAGES (GUI)
| Page | Purpose | Status |
|------|---------|--------|
| `command_center.html` | Main dashboard | ✅ Created |
| `welcome.html` | Setup wizard | 🔴 Needs rebuild |
| `dashboard.html` | Old dashboard | 🔄 Replace |
| `documents.html` | Document viewer | ⚠️ Needs update |
| `timeline.html` | Timeline view | ⚠️ Needs update |
| `calendar.html` | Calendar view | ⚠️ Needs update |
| `roles.html` | Role config | ⚠️ Needs update |
| `document_intake.html` | Upload interface | ⚠️ Needs update |

---

## 🔄 BI-DIRECTIONAL DATA FLOW ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SEMPTIFY DATA MESH                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────┐            │
│  │   WELCOME    │────▶│   FORM DATA HUB  │◀────│   COPILOT    │            │
│  │   WIZARD     │     │   (Central Bus)   │     │   (AI)       │            │
│  └──────────────┘     └────────┬─────────┘     └──────────────┘            │
│                                │                                             │
│         ┌──────────────────────┼──────────────────────┐                     │
│         │                      │                      │                     │
│         ▼                      ▼                      ▼                     │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   DOCUMENT   │◀───▶│   TIMELINE   │◀───▶│   CALENDAR   │                │
│  │   VAULT      │     │   ENGINE     │     │   SYSTEM     │                │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                    │                    │                         │
│         └────────────────────┼────────────────────┘                         │
│                              │                                              │
│                              ▼                                              │
│                    ┌──────────────────┐                                     │
│                    │   DEFENSE        │                                     │
│                    │   GENERATOR      │                                     │
│                    └────────┬─────────┘                                     │
│                             │                                               │
│         ┌───────────────────┼───────────────────┐                          │
│         │                   │                   │                          │
│         ▼                   ▼                   ▼                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │   ANSWER     │  │   MOTIONS    │  │ COUNTERCLAIM │                     │
│  │   FORM       │  │   FORMS      │  │   FORMS      │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
│                                                                            │
│                              │                                              │
│                              ▼                                              │
│                    ┌──────────────────┐                                     │
│                    │   PDF GENERATOR  │                                     │
│                    │   (Court Ready)  │                                     │
│                    └──────────────────┘                                     │
│                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ✅ MASTER TODO LIST

### PHASE 1: FOUNDATION (Do First)
- [ ] **1.1** Create Setup Wizard Router (`/api/setup/*`)
  - [ ] Profile endpoint (user info)
  - [ ] Case info endpoint (case number, parties)
  - [ ] Storage config endpoint (cloud providers)
  - [ ] Completion status endpoint
  
- [ ] **1.2** Create Setup Wizard Frontend (`setup_wizard.html`)
  - [ ] Step 1: Welcome & Terms
  - [ ] Step 2: Your Information (name, contact)
  - [ ] Step 3: Case Information (case #, court, parties)
  - [ ] Step 4: Storage Setup (Google Drive/OneDrive/Dropbox)
  - [ ] Step 5: Document Upload
  - [ ] Step 6: Document Processing (AI extraction)
  - [ ] Step 7: Review & Confirm
  - [ ] Progress indicator
  - [ ] Save/Resume capability

- [ ] **1.3** Database Schema Updates
  - [ ] User profile table
  - [ ] Setup progress tracking
  - [ ] Case configuration table

### PHASE 2: DATA HUB INTEGRATION
- [ ] **2.1** Connect Document Pipeline to Form Data Hub
  - [ ] On document upload → extract data → update hub
  - [ ] Date extraction → timeline + calendar
  - [ ] Amount extraction → form fields
  - [ ] Party extraction → case info

- [ ] **2.2** Connect Timeline to Form Data Hub
  - [ ] Timeline events ↔ document dates
  - [ ] Auto-create events from documents
  - [ ] Manual events → update documents

- [ ] **2.3** Connect Calendar to Form Data Hub
  - [ ] Deadlines from case dates
  - [ ] Auto-calculate answer deadline (7 days from summons)
  - [ ] Hearing date → calendar event

- [ ] **2.4** Connect Defense Module to Form Data Hub
  - [ ] Selected defenses → answer form
  - [ ] Counterclaims → form fields
  - [ ] Defense recommendations from documents

### PHASE 3: DOCUMENT PROCESSING ENGINE
- [ ] **3.1** Document Intake Pipeline
  - [ ] File upload → vault storage
  - [ ] Hash verification (SHA256)
  - [ ] Type classification (summons, complaint, notice, lease)
  - [ ] OCR/text extraction

- [ ] **3.2** Event Extractor Service
  - [ ] Date pattern recognition
  - [ ] Amount pattern recognition
  - [ ] Party name extraction
  - [ ] Address extraction
  - [ ] Case number extraction

- [ ] **3.3** Document Registry (Chain of Custody)
  - [ ] Timestamp all actions
  - [ ] Hash verification log
  - [ ] Access log
  - [ ] Modification tracking

### PHASE 4: FORM GENERATION
- [ ] **4.1** Answer Form Generator
  - [ ] Pre-fill from Form Data Hub
  - [ ] Defense checkboxes
  - [ ] Signature field
  - [ ] PDF generation

- [ ] **4.2** Motion Generator
  - [ ] Motion to Dismiss
  - [ ] Motion for Continuance
  - [ ] Motion to Stay
  - [ ] Fee Waiver Application

- [ ] **4.3** Counterclaim Generator
  - [ ] Habitability counterclaim
  - [ ] Security deposit counterclaim
  - [ ] Retaliation counterclaim
  - [ ] Discrimination counterclaim

### PHASE 5: AI INTEGRATION
- [ ] **5.1** Copilot Integration
  - [ ] Document analysis
  - [ ] Defense suggestions
  - [ ] Question answering
  - [ ] Form review

- [ ] **5.2** Context Loop Engine
  - [ ] Process all inputs
  - [ ] Generate recommendations
  - [ ] Update form data
  - [ ] Trigger notifications

### PHASE 6: UNIFIED GUI
- [ ] **6.1** Navigation System
  - [ ] Sidebar with all modules
  - [ ] Breadcrumb navigation
  - [ ] Quick actions menu
  - [ ] Status indicators

- [ ] **6.2** Dashboard Widgets
  - [ ] Case status card
  - [ ] Deadline countdown
  - [ ] Document count
  - [ ] Timeline preview
  - [ ] Defense checklist
  - [ ] AI assistant

- [ ] **6.3** Real-time Updates
  - [ ] WebSocket connections
  - [ ] Auto-refresh data
  - [ ] Toast notifications
  - [ ] Progress indicators

### PHASE 7: ZOOM COURT PREPARATION
- [ ] **7.1** Virtual Court Checklist
  - [ ] Technical setup verification
  - [ ] Document preparation
  - [ ] Speaking points
  - [ ] Objection guide

- [ ] **7.2** Court Presentation Mode
  - [ ] Document quick-view
  - [ ] Evidence markers
  - [ ] Timeline reference
  - [ ] Notes panel

---

## 🔧 IMPLEMENTATION ORDER

### TODAY (Priority 1 - Setup Wizard)
1. Create `/api/setup/` router with all endpoints
2. Create `setup_wizard.html` with all 7 steps
3. Connect wizard to Form Data Hub
4. Test complete flow

### NEXT (Priority 2 - Document Flow)
5. Fix document upload → processing → form data flow
6. Implement event extraction from documents
7. Auto-populate timeline and calendar

### THEN (Priority 3 - Forms)
8. Generate pre-filled answer form
9. Generate motion forms
10. PDF generation

### FINALLY (Priority 4 - Polish)
11. AI integration
12. Real-time updates
13. Final testing

---

## 📁 FILE STRUCTURE

```
app/
├── routers/
│   ├── setup.py          # NEW: Setup wizard API
│   ├── form_data.py      # Central data hub
│   ├── vault.py          # Document storage
│   ├── timeline.py       # Timeline events
│   ├── calendar.py       # Calendar/deadlines
│   └── eviction/         # Defense flows
│
├── services/
│   ├── setup_service.py  # NEW: Setup wizard logic
│   ├── form_data.py      # Data integration
│   ├── document_pipeline.py
│   ├── event_extractor.py
│   └── pdf_generator.py  # NEW: PDF output
│
├── models/
│   └── models.py         # Database models
│
static/
├── setup_wizard.html     # NEW: Setup wizard UI
├── command_center.html   # Main dashboard
├── css/
│   └── semptify.css      # NEW: Unified styles
└── js/
    └── semptify.js       # NEW: Unified JavaScript
```

---

## 🎯 SUCCESS CRITERIA

1. **User can complete setup wizard** in one sitting
2. **Documents upload and auto-process** without manual intervention
3. **Form data auto-populates** from uploaded documents
4. **Timeline auto-generates** from document dates
5. **Calendar shows all deadlines** calculated from case dates
6. **Answer form pre-fills** with all case information
7. **All modules communicate** bi-directionally
8. **Single source of truth** in Form Data Hub

---

## 🚀 READY TO BUILD

Starting with Phase 1: Setup Wizard
- Router: `/api/setup/`
- Frontend: `setup_wizard.html`
- Integration: Form Data Hub connection

**LET'S GO!**
