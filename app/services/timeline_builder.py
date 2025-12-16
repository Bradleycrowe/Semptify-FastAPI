"""
Auto-Build Timeline from Documents
==================================

Automatically extracts dates, events, and key information from documents
and populates the timeline. This creates a chronological case history
from uploaded evidence.

Features:
- Extract dates from any document type
- Identify event types (notices, payments, court dates, etc.)
- Link timeline entries to source documents
- Detect deadlines and calculate urgency
- Smart deduplication of events
- Batch processing for multiple documents
"""

import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from uuid import uuid4

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

class TimelineEventType(str, Enum):
    """Types of timeline events."""
    NOTICE = "notice"
    PAYMENT = "payment"
    MAINTENANCE = "maintenance"
    COMMUNICATION = "communication"
    COURT = "court"
    LEASE = "lease"
    INSPECTION = "inspection"
    DEADLINE = "deadline"
    OTHER = "other"


@dataclass
class ExtractedTimelineEvent:
    """An event extracted from a document for the timeline."""
    id: str = field(default_factory=lambda: str(uuid4()))
    event_type: TimelineEventType = TimelineEventType.OTHER
    title: str = ""
    description: str = ""
    event_date: Optional[date] = None
    event_date_text: str = ""  # Original text representation
    is_deadline: bool = False
    is_evidence: bool = False
    urgency: str = "normal"  # critical, high, normal, low
    confidence: float = 0.0
    source_document_id: Optional[str] = None
    source_filename: Optional[str] = None
    extracted_from_text: str = ""  # The sentence/context where found
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value if isinstance(self.event_type, Enum) else self.event_type,
            "title": self.title,
            "description": self.description,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "event_date_text": self.event_date_text,
            "is_deadline": self.is_deadline,
            "is_evidence": self.is_evidence,
            "urgency": self.urgency,
            "confidence": self.confidence,
            "source_document_id": self.source_document_id,
            "source_filename": self.source_filename,
            "extracted_from_text": self.extracted_from_text,
        }


@dataclass
class TimelineBuildResult:
    """Result of building timeline from documents."""
    events: List[ExtractedTimelineEvent] = field(default_factory=list)
    total_documents_processed: int = 0
    total_events_found: int = 0
    total_deadlines_found: int = 0
    earliest_date: Optional[date] = None
    latest_date: Optional[date] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.events],
            "total_documents_processed": self.total_documents_processed,
            "total_events_found": self.total_events_found,
            "total_deadlines_found": self.total_deadlines_found,
            "earliest_date": self.earliest_date.isoformat() if self.earliest_date else None,
            "latest_date": self.latest_date.isoformat() if self.latest_date else None,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# =============================================================================
# DATE PATTERNS
# =============================================================================

# Common date patterns
DATE_PATTERNS = [
    # MM/DD/YYYY or MM-DD-YYYY
    (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', 'mdy'),
    # YYYY-MM-DD (ISO)
    (r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', 'ymd'),
    # Month DD, YYYY
    (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', 'written'),
    # DD Month YYYY
    (r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', 'written_euro'),
    # Mon DD, YYYY (abbreviated)
    (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})', 'abbrev'),
]

MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

# Deadline indicator keywords
DEADLINE_KEYWORDS = [
    'must', 'deadline', 'by', 'before', 'no later than', 'within',
    'due', 'expires', 'expiration', 'vacate', 'respond', 'appear',
    'hearing', 'court date', 'trial', 'file by', 'required by'
]

# Event type indicators
EVENT_TYPE_INDICATORS = {
    TimelineEventType.NOTICE: [
        'notice', 'notify', 'notification', 'informed', 'advise',
        'eviction', 'vacate', 'quit', 'terminate', 'violation'
    ],
    TimelineEventType.PAYMENT: [
        'payment', 'paid', 'rent', 'deposit', 'fee', 'charge',
        'amount', 'balance', 'due', 'received', 'receipt'
    ],
    TimelineEventType.MAINTENANCE: [
        'repair', 'maintenance', 'fix', 'broken', 'damage', 'leak',
        'mold', 'pest', 'hvac', 'plumbing', 'electrical', 'inspection'
    ],
    TimelineEventType.COMMUNICATION: [
        'email', 'letter', 'message', 'called', 'spoke', 'meeting',
        'conversation', 'discussed', 'requested', 'responded'
    ],
    TimelineEventType.COURT: [
        'court', 'hearing', 'trial', 'judge', 'summons', 'complaint',
        'motion', 'order', 'judgment', 'writ', 'file', 'docket'
    ],
    TimelineEventType.LEASE: [
        'lease', 'agreement', 'contract', 'signed', 'executed',
        'amendment', 'addendum', 'renewal', 'termination'
    ],
    TimelineEventType.INSPECTION: [
        'inspection', 'walkthrough', 'checklist', 'move-in', 'move-out',
        'condition', 'inventory'
    ],
}


# =============================================================================
# TIMELINE BUILDER SERVICE
# =============================================================================

class TimelineBuilder:
    """
    Builds timeline events from document text.
    
    Usage:
        builder = TimelineBuilder()
        result = await builder.build_from_text(document_text, filename="notice.pdf")
        # or
        result = await builder.build_from_documents(documents_list)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.min_confidence = self.config.get('min_confidence', 0.5)
        
    async def build_from_text(
        self,
        text: str,
        document_id: Optional[str] = None,
        filename: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> TimelineBuildResult:
        """
        Extract timeline events from document text.
        
        Args:
            text: Document text content
            document_id: Optional ID to link events to source document
            filename: Original filename for context
            document_type: Type of document (lease, notice, etc.)
            
        Returns:
            TimelineBuildResult with extracted events
        """
        result = TimelineBuildResult()
        result.total_documents_processed = 1
        
        if not text or not text.strip():
            result.errors.append("Empty document text")
            return result
        
        try:
            # Extract all dates from text
            date_matches = self._extract_dates(text)
            
            # For each date, create a timeline event with context
            for date_obj, date_text, context, confidence in date_matches:
                event = self._create_event_from_date(
                    date_obj=date_obj,
                    date_text=date_text,
                    context=context,
                    confidence=confidence,
                    document_id=document_id,
                    filename=filename,
                    document_type=document_type,
                )
                
                if event and event.confidence >= self.min_confidence:
                    result.events.append(event)
            
            # Update statistics
            result.total_events_found = len(result.events)
            result.total_deadlines_found = sum(1 for e in result.events if e.is_deadline)
            
            # Find date range
            dates = [e.event_date for e in result.events if e.event_date]
            if dates:
                result.earliest_date = min(dates)
                result.latest_date = max(dates)
            
            # Deduplicate events on same date with similar titles
            result.events = self._deduplicate_events(result.events)
            
            logger.info(f"Extracted {len(result.events)} timeline events from document")
            
        except Exception as e:
            logger.error(f"Error building timeline: {e}")
            result.errors.append(str(e))
        
        return result
    
    async def build_from_documents(
        self,
        documents: List[Dict[str, Any]],
    ) -> TimelineBuildResult:
        """
        Build timeline from multiple documents.
        
        Args:
            documents: List of document dicts with 'text', 'id', 'filename', 'type'
            
        Returns:
            Combined TimelineBuildResult
        """
        combined = TimelineBuildResult()
        
        for doc in documents:
            text = doc.get('text', '')
            doc_id = doc.get('id')
            filename = doc.get('filename')
            doc_type = doc.get('type')
            
            result = await self.build_from_text(
                text=text,
                document_id=doc_id,
                filename=filename,
                document_type=doc_type,
            )
            
            # Merge results
            combined.events.extend(result.events)
            combined.total_documents_processed += 1
            combined.warnings.extend(result.warnings)
            combined.errors.extend(result.errors)
        
        # Update combined statistics
        combined.total_events_found = len(combined.events)
        combined.total_deadlines_found = sum(1 for e in combined.events if e.is_deadline)
        
        dates = [e.event_date for e in combined.events if e.event_date]
        if dates:
            combined.earliest_date = min(dates)
            combined.latest_date = max(dates)
        
        # Sort by date
        combined.events.sort(key=lambda e: e.event_date or date.max)
        
        # Global deduplication
        combined.events = self._deduplicate_events(combined.events)
        
        return combined
    
    def _extract_dates(self, text: str) -> List[Tuple[date, str, str, float]]:
        """
        Extract all dates from text with surrounding context.
        
        Returns:
            List of (date_object, original_text, context_sentence, confidence)
        """
        results = []
        
        # Split into sentences for context
        sentences = re.split(r'[.!?\n]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            for pattern, format_type in DATE_PATTERNS:
                for match in re.finditer(pattern, sentence, re.IGNORECASE):
                    date_obj = self._parse_date_match(match, format_type)
                    if date_obj:
                        # Calculate confidence based on context
                        confidence = self._calculate_date_confidence(sentence, match.group())
                        results.append((date_obj, match.group(), sentence, confidence))
        
        return results
    
    def _parse_date_match(self, match: re.Match, format_type: str) -> Optional[date]:
        """Parse a regex match into a date object."""
        try:
            groups = match.groups()
            
            if format_type == 'mdy':
                month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
            elif format_type == 'ymd':
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            elif format_type == 'written':
                month = MONTH_MAP.get(groups[0].lower(), 0)
                day, year = int(groups[1]), int(groups[2])
            elif format_type == 'written_euro':
                day = int(groups[0])
                month = MONTH_MAP.get(groups[1].lower(), 0)
                year = int(groups[2])
            elif format_type == 'abbrev':
                month = MONTH_MAP.get(groups[0].lower(), 0)
                day, year = int(groups[1]), int(groups[2])
            else:
                return None
            
            # Validate
            if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
                return None
                
            return date(year, month, day)
            
        except (ValueError, IndexError):
            return None
    
    def _calculate_date_confidence(self, context: str, date_text: str) -> float:
        """Calculate confidence score for a date extraction."""
        confidence = 0.6  # Base confidence
        
        context_lower = context.lower()
        
        # Boost for deadline indicators
        if any(kw in context_lower for kw in DEADLINE_KEYWORDS):
            confidence += 0.2
        
        # Boost for specific event type indicators
        for event_type, keywords in EVENT_TYPE_INDICATORS.items():
            if any(kw in context_lower for kw in keywords):
                confidence += 0.1
                break
        
        # Boost for document-specific context
        if any(word in context_lower for word in ['hereby', 'dated', 'on or before', 'effective']):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _create_event_from_date(
        self,
        date_obj: date,
        date_text: str,
        context: str,
        confidence: float,
        document_id: Optional[str] = None,
        filename: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> ExtractedTimelineEvent:
        """Create a timeline event from an extracted date."""
        
        # Determine event type from context
        event_type = self._detect_event_type(context, document_type)
        
        # Determine if it's a deadline
        is_deadline = self._is_deadline(context, date_obj)
        
        # Calculate urgency
        urgency = self._calculate_urgency(date_obj, is_deadline)
        
        # Generate title from context
        title = self._generate_title(context, event_type, date_text)
        
        # Clean up description
        description = self._clean_description(context)
        
        return ExtractedTimelineEvent(
            event_type=event_type,
            title=title,
            description=description,
            event_date=date_obj,
            event_date_text=date_text,
            is_deadline=is_deadline,
            is_evidence=True,  # From document, so it's evidence
            urgency=urgency,
            confidence=confidence,
            source_document_id=document_id,
            source_filename=filename,
            extracted_from_text=context[:500],
        )
    
    def _detect_event_type(
        self, 
        context: str, 
        document_type: Optional[str] = None
    ) -> TimelineEventType:
        """Detect the event type from context and document type."""
        context_lower = context.lower()
        
        # Check document type first
        if document_type:
            doc_type_lower = document_type.lower()
            if 'notice' in doc_type_lower or 'eviction' in doc_type_lower:
                return TimelineEventType.NOTICE
            elif 'payment' in doc_type_lower or 'receipt' in doc_type_lower:
                return TimelineEventType.PAYMENT
            elif 'repair' in doc_type_lower or 'maintenance' in doc_type_lower:
                return TimelineEventType.MAINTENANCE
            elif 'court' in doc_type_lower or 'summons' in doc_type_lower:
                return TimelineEventType.COURT
            elif 'lease' in doc_type_lower:
                return TimelineEventType.LEASE
        
        # Check context keywords
        for event_type, keywords in EVENT_TYPE_INDICATORS.items():
            if any(kw in context_lower for kw in keywords):
                return event_type
        
        return TimelineEventType.OTHER
    
    def _is_deadline(self, context: str, date_obj: date) -> bool:
        """Determine if a date represents a deadline."""
        context_lower = context.lower()
        
        # Check for deadline keywords
        if any(kw in context_lower for kw in DEADLINE_KEYWORDS):
            return True
        
        # Future dates with action verbs are likely deadlines
        if date_obj > date.today():
            action_words = ['must', 'shall', 'required', 'need', 'have to', 'should']
            if any(word in context_lower for word in action_words):
                return True
        
        return False
    
    def _calculate_urgency(self, date_obj: date, is_deadline: bool) -> str:
        """Calculate urgency based on date and deadline status."""
        if not is_deadline:
            return "normal"
        
        days_until = (date_obj - date.today()).days
        
        if days_until < 0:
            return "critical"  # Past deadline!
        elif days_until <= 3:
            return "critical"
        elif days_until <= 7:
            return "high"
        elif days_until <= 14:
            return "normal"
        else:
            return "low"
    
    def _generate_title(
        self, 
        context: str, 
        event_type: TimelineEventType,
        date_text: str
    ) -> str:
        """Generate a concise title for the event."""
        context_lower = context.lower()
        
        # Look for specific event mentions
        title_patterns = [
            (r'(eviction notice|notice to quit|notice to vacate)', 'Eviction Notice'),
            (r'(hearing|court date|trial)', 'Court Hearing'),
            (r'(rent due|payment due)', 'Rent Due'),
            (r'(lease sign|signed lease|executed)', 'Lease Signed'),
            (r'(repair request|maintenance request)', 'Repair Requested'),
            (r'(inspection|walkthrough)', 'Property Inspection'),
            (r'(payment received|rent paid)', 'Payment Made'),
            (r'(move.?in|moved in)', 'Move-In Date'),
            (r'(move.?out|must vacate)', 'Move-Out Date'),
            (r'(summons|served)', 'Summons Served'),
            (r'(complaint filed)', 'Complaint Filed'),
            (r'(deadline|due date|expires)', 'Deadline'),
        ]
        
        for pattern, title in title_patterns:
            if re.search(pattern, context_lower):
                return title
        
        # Fallback to event type
        type_titles = {
            TimelineEventType.NOTICE: "Notice Received",
            TimelineEventType.PAYMENT: "Payment Event",
            TimelineEventType.MAINTENANCE: "Maintenance Event",
            TimelineEventType.COMMUNICATION: "Communication",
            TimelineEventType.COURT: "Court Event",
            TimelineEventType.LEASE: "Lease Event",
            TimelineEventType.INSPECTION: "Inspection",
            TimelineEventType.DEADLINE: "Deadline",
            TimelineEventType.OTHER: f"Event on {date_text}",
        }
        
        return type_titles.get(event_type, f"Event on {date_text}")
    
    def _clean_description(self, context: str) -> str:
        """Clean and format the description."""
        # Remove extra whitespace
        desc = ' '.join(context.split())
        # Truncate if too long
        if len(desc) > 500:
            desc = desc[:497] + "..."
        return desc
    
    def _deduplicate_events(
        self, 
        events: List[ExtractedTimelineEvent]
    ) -> List[ExtractedTimelineEvent]:
        """Remove duplicate events (same date and similar title)."""
        seen = set()
        unique = []
        
        for event in events:
            # Create a key from date and normalized title
            key = (
                event.event_date,
                event.title.lower().strip(),
            )
            
            if key not in seen:
                seen.add(key)
                unique.append(event)
            else:
                # Keep the one with higher confidence
                for i, existing in enumerate(unique):
                    existing_key = (existing.event_date, existing.title.lower().strip())
                    if existing_key == key and event.confidence > existing.confidence:
                        unique[i] = event
                        break
        
        return unique


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def extract_timeline_from_text(
    text: str,
    document_id: Optional[str] = None,
    filename: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function to extract timeline events from text.
    
    Returns list of event dictionaries ready for API response.
    """
    builder = TimelineBuilder()
    result = await builder.build_from_text(text, document_id, filename)
    return [event.to_dict() for event in result.events]


async def extract_timeline_from_documents(
    documents: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Convenience function to extract timeline from multiple documents.
    
    Returns full result dictionary with events and statistics.
    """
    builder = TimelineBuilder()
    result = await builder.build_from_documents(documents)
    return result.to_dict()
