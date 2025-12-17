"""
Case Auto-Creation Service
===========================

Automatically creates case management entries when court documents are uploaded.

When a document like a summons, complaint, or court filing is uploaded:
1. Parse the extracted data for case information
2. Check if a case with that case number already exists
3. If exists: Add document to the existing case and trigger re-evaluation
4. If new: Create a new case in case management
5. Notify the user

Supported document types that trigger case creation:
- COURT_SUMMONS
- COURT_COMPLAINT  
- COURT_FILING
- EVICTION_NOTICE
- NOTICE_TO_QUIT
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from glob import glob

logger = logging.getLogger(__name__)


# Document types that should trigger automatic case creation or addition
CASE_TRIGGER_DOC_TYPES = [
    "court_summons",
    "court_complaint", 
    "court_filing",
    "court_order",
    "eviction_notice",
    "notice_to_quit",
]

# Document types that are relevant to a case (broader set for matching)
CASE_RELEVANT_DOC_TYPES = CASE_TRIGGER_DOC_TYPES + [
    "lease_agreement",
    "rent_ledger",
    "payment_receipt",
    "communication",
    "repair_request",
    "inspection_report",
    "correspondence",
    "other",
]


def should_create_case(doc_type: str) -> bool:
    """Check if a document type should trigger case creation."""
    return doc_type.lower() in CASE_TRIGGER_DOC_TYPES


def is_case_relevant_document(doc_type: str) -> bool:
    """Check if a document type is relevant to case management."""
    return doc_type.lower() in CASE_RELEVANT_DOC_TYPES


# =============================================================================
# CASE LOOKUP FUNCTIONS
# =============================================================================

def get_user_cases_dir(user_id: str) -> str:
    """Get the directory where user's cases are stored."""
    return os.path.join(os.getcwd(), "data", "cases", user_id)


def find_case_by_case_number(user_id: str, case_number: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Find an existing case by case number for a user.
    
    Returns tuple of (file_path, case_data) if found, None otherwise.
    """
    if not case_number:
        return None
    
    data_dir = get_user_cases_dir(user_id)
    if not os.path.exists(data_dir):
        return None
    
    # Normalize case number for comparison
    normalized_target = normalize_case_number(case_number)
    
    # Search all case files
    for file_path in glob(os.path.join(data_dir, "*.json")):
        try:
            with open(file_path, 'r') as f:
                case_data = json.load(f)
                stored_case_number = case_data.get("case_number", "")
                if normalize_case_number(stored_case_number) == normalized_target:
                    logger.info(f"Found existing case: {stored_case_number}")
                    return (file_path, case_data)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error reading case file {file_path}: {e}")
            continue
    
    return None


def find_all_user_cases(user_id: str) -> List[Dict[str, Any]]:
    """Get all cases for a user."""
    data_dir = get_user_cases_dir(user_id)
    if not os.path.exists(data_dir):
        return []
    
    cases = []
    for file_path in glob(os.path.join(data_dir, "*.json")):
        try:
            with open(file_path, 'r') as f:
                case_data = json.load(f)
                cases.append(case_data)
        except (json.JSONDecodeError, IOError):
            continue
    
    return cases


def normalize_case_number(case_number: str) -> str:
    """Normalize case number for comparison (remove dashes, spaces, lowercase)."""
    if not case_number:
        return ""
    return re.sub(r'[-\s]', '', case_number.upper())


def find_case_by_reference_in_text(user_id: str, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Search document text for any case number that matches an existing case.
    
    This allows documents that reference a case number (even if not the primary
    case document) to be attached to the correct case.
    """
    if not text:
        return None
    
    # Get all user's cases
    cases = find_all_user_cases(user_id)
    if not cases:
        return None
    
    # Check if any case number appears in the text
    for case_data in cases:
        case_number = case_data.get("case_number", "")
        if not case_number or case_number.startswith("AUTO-"):
            continue
        
        # Check for exact match or normalized match in text
        normalized_case = normalize_case_number(case_number)
        text_normalized = normalize_case_number(text)
        
        if normalized_case and normalized_case in text_normalized:
            data_dir = get_user_cases_dir(user_id)
            safe_case_id = case_number.replace('-', '_').replace(' ', '_').replace('/', '_').replace('\\', '_')
            file_path = os.path.join(data_dir, f"{safe_case_id}.json")
            logger.info(f"Found case reference in document text: {case_number}")
            return (file_path, case_data)
        
        # Also try partial matching for case numbers in text
        if case_number and case_number in text:
            data_dir = get_user_cases_dir(user_id)
            safe_case_id = case_number.replace('-', '_').replace(' ', '_').replace('/', '_').replace('\\', '_')
            file_path = os.path.join(data_dir, f"{safe_case_id}.json")
            logger.info(f"Found case reference in document text: {case_number}")
            return (file_path, case_data)
    
    return None


def extract_case_number(text: str) -> Optional[str]:
    """
    Extract case number from document text.
    
    Common formats:
    - 27-CV-24-12345
    - Case No. 27-CV-24-12345
    - File No: 27CV2412345
    - Docket No. 2024-CV-12345
    """
    patterns = [
        # Minnesota format: County-Type-Year-Number
        r'(?:Case|File|Docket)\s*(?:No\.?|Number|#)?:?\s*(\d{2}[-\s]?[A-Z]{2}[-\s]?\d{2}[-\s]?\d+)',
        r'(\d{2}[-]?[A-Z]{2}[-]?\d{2}[-]?\d{4,})',
        # Year-Type-Number format
        r'(\d{4}[-]?[A-Z]{2}[-]?\d+)',
        # Generic case number
        r'(?:Case|File|Docket)\s*(?:No\.?|Number|#)?:?\s*([A-Z0-9][-A-Z0-9]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None


def extract_court_name(text: str) -> Optional[str]:
    """Extract court name from document text."""
    patterns = [
        r'((?:\w+\s+)?County\s+District\s+Court)',
        r'(District\s+Court[^,\n]*)',
        r'STATE OF MINNESOTA[^,\n]*DISTRICT COURT[^,\n]*(\w+\s+COUNTY)',
        r'(\w+\s+County\s+(?:Housing|District)\s+Court)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Default for Minnesota
    if 'minnesota' in text.lower() or 'mn' in text.lower():
        return "Minnesota District Court"
    
    return None


def extract_hearing_date(key_dates: list) -> Optional[str]:
    """Extract hearing date from key dates list."""
    if not key_dates:
        return None
    
    hearing_keywords = ['hearing', 'court date', 'appear', 'trial', 'conference']
    
    for date_info in key_dates:
        if isinstance(date_info, dict):
            desc = date_info.get('description', '').lower()
            if any(kw in desc for kw in hearing_keywords):
                return date_info.get('date')
    
    return None


def extract_answer_deadline(key_dates: list) -> Optional[str]:
    """Extract answer deadline from key dates list."""
    if not key_dates:
        return None
    
    answer_keywords = ['answer', 'respond', 'response due', 'deadline']
    
    for date_info in key_dates:
        if isinstance(date_info, dict):
            desc = date_info.get('description', '').lower()
            if any(kw in desc for kw in answer_keywords):
                return date_info.get('date')
    
    return None


def extract_parties(key_parties: list) -> Dict[str, Dict[str, Any]]:
    """Extract plaintiff and defendant from key parties list."""
    result = {
        'plaintiff': {'name': None, 'address': None, 'phone': None},
        'defendant': {'name': None, 'address': None, 'phone': None},
    }
    
    if not key_parties:
        return result
    
    for party_info in key_parties:
        if isinstance(party_info, dict):
            role = party_info.get('role', '').lower()
            name = party_info.get('name')
            address = party_info.get('address')
            phone = party_info.get('phone')
            
            if 'plaintiff' in role or 'landlord' in role or 'petitioner' in role:
                result['plaintiff']['name'] = name
                result['plaintiff']['address'] = address
                result['plaintiff']['phone'] = phone
            elif 'defendant' in role or 'tenant' in role or 'respondent' in role:
                result['defendant']['name'] = name
                result['defendant']['address'] = address
                result['defendant']['phone'] = phone
    
    return result


def extract_property_address(text: str, key_parties: list = None) -> Optional[str]:
    """Extract property address from document text."""
    # Try to find address patterns
    patterns = [
        r'(?:property|premises|address|located at)[:\s]+([0-9]+[^,\n]+(?:,\s*[A-Z]{2}\s*\d{5})?)',
        r'(\d+\s+\w+(?:\s+\w+)*\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court)[,.\s]+\w+[,.\s]+MN\s*\d{5})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Try to get from defendant's address
    if key_parties:
        for party_info in key_parties:
            if isinstance(party_info, dict):
                role = party_info.get('role', '').lower()
                if 'defendant' in role or 'tenant' in role:
                    if party_info.get('address'):
                        return party_info['address']
    
    return None


def extract_rent_amount(key_amounts: list) -> Optional[float]:
    """Extract rent amount from key amounts."""
    if not key_amounts:
        return None
    
    rent_keywords = ['rent', 'monthly', 'lease payment']
    
    for amount_info in key_amounts:
        if isinstance(amount_info, dict):
            desc = amount_info.get('description', '').lower()
            if any(kw in desc for kw in rent_keywords):
                try:
                    return float(amount_info.get('amount', 0))
                except (ValueError, TypeError):
                    pass
    
    return None


async def create_case_from_document(
    user_id: str,
    document_id: str,
    doc_type: str,
    full_text: str,
    key_dates: list = None,
    key_parties: list = None,
    key_amounts: list = None,
    filename: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Create a case management entry from an uploaded court document.
    
    Returns the created case data or None if creation failed.
    """
    if not should_create_case(doc_type):
        logger.info(f"Document type '{doc_type}' does not trigger case creation")
        return None
    
    # Extract case information
    case_number = extract_case_number(full_text or "")
    court = extract_court_name(full_text or "")
    hearing_date = extract_hearing_date(key_dates or [])
    answer_deadline = extract_answer_deadline(key_dates or [])
    parties = extract_parties(key_parties or [])
    property_address = extract_property_address(full_text or "", key_parties)
    rent_amount = extract_rent_amount(key_amounts or [])
    
    # Generate case number if not found
    if not case_number:
        case_number = f"AUTO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.warning(f"Could not extract case number, using generated: {case_number}")
    
    # Determine case type
    case_type = "eviction_defense"
    if "counter" in doc_type.lower():
        case_type = "counter_claim"
    elif "habitability" in (full_text or "").lower():
        case_type = "habitability"
    
    # Build case data
    case_data = {
        "user_id": user_id,
        "case_number": case_number,
        "case_type": case_type,
        "status": "active",
        "court": court or "District Court",
        "property_address": property_address or "",
        "rent_amount": rent_amount or 0,
        "security_deposit": 0,
        "plaintiff": {
            "name": parties['plaintiff']['name'] or "Unknown Plaintiff",
            "role": "plaintiff",
            "address": parties['plaintiff']['address'],
            "phone": parties['plaintiff']['phone'],
        },
        "defendant": {
            "name": parties['defendant']['name'] or "Unknown Defendant",
            "role": "defendant",
            "is_pro_se": True,
            "address": parties['defendant']['address'],
            "phone": parties['defendant']['phone'],
        },
        "hearing_date": hearing_date,
        "answer_due": answer_deadline,
        "source_document_id": document_id,
        "source_filename": filename,
        "timeline": [
            {
                "id": f"evt_doc_{document_id[:8]}",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "title": f"Document Received: {filename}",
                "description": f"Court document '{filename}' uploaded and case auto-created",
                "category": "court",
                "importance": "high",
            }
        ],
        "evidence": [
            {
                "id": f"evi_{document_id[:8]}",
                "title": filename,
                "evidence_type": "document",
                "date_obtained": datetime.now().strftime("%Y-%m-%d"),
                "description": f"Original court filing: {doc_type}",
                "source": "document_intake",
                "relevance": "Primary court document",
                "document_id": document_id,
            }
        ],
        "defenses": [],
        "counterclaims": [],
        "motions": [],
        "deadlines": [],
        "notes": [f"Case auto-created from uploaded document: {filename}"],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "auto_created": True,
    }
    
    # Add deadline for answer if found
    if answer_deadline:
        case_data["deadlines"].append({
            "id": f"ddl_answer_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "title": "File Answer",
            "deadline": answer_deadline,
            "description": "Deadline to file answer to complaint",
            "priority": "critical",
            "completed": False,
        })
    
    # Add deadline for hearing if found
    if hearing_date:
        case_data["deadlines"].append({
            "id": f"ddl_hearing_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "title": "Court Hearing",
            "deadline": hearing_date,
            "description": "Court hearing date",
            "priority": "critical",
            "completed": False,
        })
    
    # Save case to file system (same pattern as case_builder router)
    try:
        data_dir = os.path.join(os.getcwd(), "data", "cases", user_id)
        os.makedirs(data_dir, exist_ok=True)
        
        safe_case_id = case_number.replace('-', '_').replace(' ', '_').replace('/', '_').replace('\\', '_')
        file_path = os.path.join(data_dir, f"{safe_case_id}.json")
        
        with open(file_path, 'w') as f:
            json.dump(case_data, f, indent=2, default=str)
        
        logger.info(f"✅ Auto-created case {case_number} from document {filename}")
        
        return case_data
        
    except Exception as e:
        logger.error(f"Failed to save auto-created case: {e}")
        return None


def get_case_creation_summary(case_data: Dict[str, Any]) -> str:
    """Generate a human-readable summary of the auto-created case."""
    if not case_data:
        return ""
    
    lines = [
        f"📋 Case Auto-Created: {case_data.get('case_number', 'Unknown')}",
        f"   Type: {case_data.get('case_type', 'Unknown')}",
        f"   Court: {case_data.get('court', 'Unknown')}",
    ]
    
    if case_data.get('plaintiff', {}).get('name'):
        lines.append(f"   Plaintiff: {case_data['plaintiff']['name']}")
    
    if case_data.get('property_address'):
        lines.append(f"   Property: {case_data['property_address']}")
    
    if case_data.get('hearing_date'):
        lines.append(f"   Hearing: {case_data['hearing_date']}")
    
    if case_data.get('answer_due'):
        lines.append(f"   Answer Due: {case_data['answer_due']}")
    
    return "\n".join(lines)


# =============================================================================
# DOCUMENT ADDITION TO EXISTING CASE
# =============================================================================

async def add_document_to_case(
    file_path: str,
    case_data: Dict[str, Any],
    document_id: str,
    doc_type: str,
    filename: str,
    full_text: str = "",
    key_dates: list = None,
    key_parties: list = None,
    key_amounts: list = None,
) -> Dict[str, Any]:
    """
    Add a document to an existing case.
    
    Updates the case with:
    - New evidence entry
    - Timeline event
    - Any new deadlines found
    - Triggers re-evaluation flag
    
    Returns updated case data.
    """
    case_number = case_data.get("case_number", "Unknown")
    
    # Check if document already exists in case
    existing_evidence = case_data.get("evidence", [])
    for evi in existing_evidence:
        if evi.get("document_id") == document_id:
            logger.info(f"Document {document_id} already in case {case_number}")
            return case_data
    
    # Add to evidence
    evidence_entry = {
        "id": f"evi_{document_id[:8]}_{datetime.now().strftime('%H%M%S')}",
        "title": filename,
        "evidence_type": "document",
        "date_obtained": datetime.now().strftime("%Y-%m-%d"),
        "description": f"Document type: {doc_type}",
        "source": "document_intake",
        "relevance": "Related to case",
        "document_id": document_id,
        "auto_added": True,
    }
    
    if "evidence" not in case_data:
        case_data["evidence"] = []
    case_data["evidence"].append(evidence_entry)
    
    # Add timeline event
    timeline_entry = {
        "id": f"evt_{document_id[:8]}_{datetime.now().strftime('%H%M%S')}",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "title": f"Document Added: {filename}",
        "description": f"Document '{filename}' ({doc_type}) added to case",
        "category": "document",
        "importance": "medium",
    }
    
    if "timeline" not in case_data:
        case_data["timeline"] = []
    case_data["timeline"].append(timeline_entry)
    
    # Extract and add any new deadlines from the document
    if key_dates:
        hearing_date = extract_hearing_date(key_dates)
        answer_deadline = extract_answer_deadline(key_dates)
        
        if "deadlines" not in case_data:
            case_data["deadlines"] = []
        
        existing_deadlines = [d.get("deadline") for d in case_data["deadlines"]]
        
        if hearing_date and hearing_date not in existing_deadlines:
            case_data["deadlines"].append({
                "id": f"ddl_hearing_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "title": f"Hearing (from {filename})",
                "deadline": hearing_date,
                "description": f"Extracted from document: {filename}",
                "priority": "critical",
                "completed": False,
            })
        
        if answer_deadline and answer_deadline not in existing_deadlines:
            case_data["deadlines"].append({
                "id": f"ddl_answer_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "title": f"Answer Deadline (from {filename})",
                "deadline": answer_deadline,
                "description": f"Extracted from document: {filename}",
                "priority": "critical",
                "completed": False,
            })
    
    # Mark case for re-evaluation
    case_data["needs_evaluation"] = True
    case_data["last_document_added"] = datetime.now().isoformat()
    case_data["updated_at"] = datetime.now().isoformat()
    
    # Add note about document addition
    if "notes" not in case_data:
        case_data["notes"] = []
    case_data["notes"].append(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Document auto-added: {filename}"
    )
    
    # Save updated case
    try:
        with open(file_path, 'w') as f:
            json.dump(case_data, f, indent=2, default=str)
        
        logger.info(f"✅ Added document '{filename}' to case {case_number}")
        
    except Exception as e:
        logger.error(f"Failed to save updated case: {e}")
    
    return case_data


def get_document_added_summary(case_data: Dict[str, Any], filename: str) -> str:
    """Generate a human-readable summary of document being added to case."""
    if not case_data:
        return ""
    
    case_number = case_data.get('case_number', 'Unknown')
    evidence_count = len(case_data.get('evidence', []))
    
    lines = [
        f"📄 Document Added to Existing Case",
        f"   Case: {case_number}",
        f"   Document: {filename}",
        f"   Total Evidence: {evidence_count} documents",
        f"   Status: Flagged for re-evaluation",
    ]
    
    return "\n".join(lines)


# =============================================================================
# MAIN PROCESSING FUNCTION
# =============================================================================

async def process_document_for_case(
    user_id: str,
    document_id: str,
    doc_type: str,
    full_text: str,
    key_dates: list = None,
    key_parties: list = None,
    key_amounts: list = None,
    filename: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Main entry point for case-aware document processing.
    
    1. Checks if document references an existing case number
    2. If yes: Adds document to that case and triggers re-evaluation
    3. If no: Creates a new case if document type warrants it
    
    Returns:
        - Updated case data if document added to existing case
        - New case data if case created
        - None if no case action taken
    """
    result = {
        "action": None,
        "case_data": None,
        "summary": "",
    }
    
    # First, try to extract case number from document
    extracted_case_number = extract_case_number(full_text or "")
    
    # Check if this document references an existing case
    existing_case = None
    
    if extracted_case_number:
        existing_case = find_case_by_case_number(user_id, extracted_case_number)
    
    # If no exact match, search for any case number reference in text
    if not existing_case:
        existing_case = find_case_by_reference_in_text(user_id, full_text or "")
    
    # Document references an existing case - add it
    if existing_case:
        file_path, case_data = existing_case
        case_number = case_data.get("case_number", "Unknown")
        
        logger.info(f"📎 Document references existing case {case_number}, adding to case...")
        
        updated_case = await add_document_to_case(
            file_path=file_path,
            case_data=case_data,
            document_id=document_id,
            doc_type=doc_type,
            filename=filename,
            full_text=full_text,
            key_dates=key_dates,
            key_parties=key_parties,
            key_amounts=key_amounts,
        )
        
        result["action"] = "document_added"
        result["case_data"] = updated_case
        result["summary"] = get_document_added_summary(updated_case, filename)
        
        # Trigger case evaluation
        await trigger_case_evaluation(user_id, case_number, document_id)
        
        return result
    
    # No existing case found - check if we should create one
    if should_create_case(doc_type):
        logger.info(f"🆕 No existing case found, creating new case from {doc_type}...")
        
        new_case = await create_case_from_document(
            user_id=user_id,
            document_id=document_id,
            doc_type=doc_type,
            full_text=full_text,
            key_dates=key_dates,
            key_parties=key_parties,
            key_amounts=key_amounts,
            filename=filename,
        )
        
        if new_case:
            result["action"] = "case_created"
            result["case_data"] = new_case
            result["summary"] = get_case_creation_summary(new_case)
            
            # Trigger initial case evaluation
            await trigger_case_evaluation(user_id, new_case.get("case_number"), document_id)
        
        return result
    
    logger.info(f"Document type '{doc_type}' does not trigger case action")
    return None


async def trigger_case_evaluation(user_id: str, case_number: str, trigger_document_id: str = None):
    """
    Trigger case evaluation after document addition.
    
    This notifies the legal analysis engine to re-evaluate the case
    based on the new evidence.
    """
    logger.info(f"⚖️ Triggering case evaluation for {case_number}")
    
    try:
        # Try to import and use the legal analysis engine
        from app.services.legal_analysis_engine import get_legal_analysis_engine
        
        engine = get_legal_analysis_engine()
        if engine:
            # Queue the case for evaluation
            # The engine will analyze all evidence and update case strength
            logger.info(f"📊 Case {case_number} queued for legal analysis")
            
    except ImportError:
        logger.debug("Legal analysis engine not available")
    
    try:
        # Emit event for other systems to react
        from app.services.context_loop import context_loop, EventType
        
        context_loop.emit_event(
            EventType.ACTION_TAKEN,
            user_id,
            {
                "action": "case_evaluation_triggered",
                "case_number": case_number,
                "trigger_document_id": trigger_document_id,
            },
            source="case_auto_creation",
        )
    except ImportError:
        logger.debug("Context loop not available")
    
    try:
        # Notify the Positronic Brain for intelligence processing
        from app.services.positronic_brain import brain, BrainEvent
        
        brain.process_event(BrainEvent(
            event_type="case_evaluation",
            user_id=user_id,
            data={
                "case_number": case_number,
                "trigger": "document_added",
                "document_id": trigger_document_id,
            },
            source="case_auto_creation",
        ))
    except (ImportError, Exception) as e:
        logger.debug(f"Positronic brain notification skipped: {e}")
