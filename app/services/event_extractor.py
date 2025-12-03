"""
Semptify 5.0 - Event Extractor Service
Automatically extracts dated events from document text for timeline generation.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum

from app.core.event_bus import event_bus, EventType


class EventCategory(str, Enum):
    """Categories of timeline events extracted from documents."""
    NOTICE_SERVED = "notice"          # Notice to quit, eviction notice
    NOTICE_DEADLINE = "notice"        # When notice period ends
    LEASE_START = "other"             # Lease commencement
    LEASE_END = "other"               # Lease termination
    RENT_DUE = "payment"              # Rent payment deadline
    PAYMENT_MADE = "payment"          # Actual payment date
    COURT_FILING = "court"            # When document was filed
    COURT_HEARING = "court"           # Scheduled hearing date
    MOVE_IN = "other"                 # Move-in date
    MOVE_OUT = "other"                # Move-out/vacate date
    INSPECTION = "maintenance"        # Inspection date
    REPAIR_REQUEST = "maintenance"    # When repair was requested
    COMMUNICATION = "communication"   # Letter sent/received date
    OTHER = "other"


@dataclass
class ExtractedEvent:
    """A single event extracted from document text."""
    date: datetime
    event_type: str            # Maps to timeline event_type
    title: str                 # Short title
    description: str           # Full context
    confidence: float          # 0.0 - 1.0
    source_text: str           # Original text snippet
    is_deadline: bool = False  # True if this is a deadline/due date
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "date": self.date.isoformat() if self.date else None,
            "event_type": self.event_type,
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "source_text": self.source_text,
            "is_deadline": self.is_deadline,
        }


class EventExtractor:
    """
    Extracts dated events from document text using pattern matching
    and contextual analysis.
    """

    # Date patterns - various formats
    DATE_PATTERNS = [
        # MM/DD/YYYY, MM-DD-YYYY
        (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', 'MDY'),
        # Month DD, YYYY
        (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', 'TEXT'),
        # YYYY-MM-DD (ISO)
        (r'(\d{4})-(\d{2})-(\d{2})', 'ISO'),
        # DD Month YYYY
        (r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', 'DMY_TEXT'),
    ]

    MONTH_MAP = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }

    # Context patterns - keywords that give meaning to dates
    EVENT_CONTEXTS = [
        # Notice events
        (r'(?:notice|served|delivered|given)\s*(?:on|dated?)?\s*', 'Notice Served', 'notice', 0.9),
        (r'(?:must\s+vacate|vacate\s+by|quit\s+by|leave\s+by)\s*', 'Vacate Deadline', 'notice', 0.95),
        (r'(?:effective|expires?|terminat\w*)\s*(?:on|date)?\s*', 'Notice Effective Date', 'notice', 0.85),
        
        # Court events
        (r'(?:filed|filing\s+date)\s*(?:on|in)?\s*', 'Court Filing', 'court', 0.95),
        (r'(?:hearing|trial|appear\w*)\s*(?:on|at|scheduled\s+for)?\s*', 'Court Hearing', 'court', 0.95),
        (r'(?:summons|complaint)\s*(?:dated?|filed)?\s*', 'Summons/Complaint Filed', 'court', 0.9),
        
        # Lease events
        (r'(?:lease\s+)?(?:commence|start|begin)\w*\s*(?:on|date)?\s*', 'Lease Start Date', 'other', 0.9),
        (r'(?:lease\s+)?(?:end|expir\w*|terminat\w*)\s*(?:on|date)?\s*', 'Lease End Date', 'other', 0.9),
        (r'(?:move[\s\-]?in)\s*(?:on|date)?\s*', 'Move-In Date', 'other', 0.85),
        (r'(?:move[\s\-]?out)\s*(?:on|date)?\s*', 'Move-Out Date', 'other', 0.85),
        
        # Payment events
        (r'(?:rent\s+)?(?:due|payable)\s*(?:on|by)?\s*', 'Rent Due', 'payment', 0.85),
        (r'(?:paid|payment\s+(?:of|made|received))\s*(?:on)?\s*', 'Payment Made', 'payment', 0.85),
        (r'(?:last\s+payment)\s*(?:on|dated?)?\s*', 'Last Payment Date', 'payment', 0.8),
        
        # Communication
        (r'(?:dated?|written|sent|mailed)\s*(?:on)?\s*', 'Document Date', 'communication', 0.7),
        (r'(?:received)\s*(?:on)?\s*', 'Document Received', 'communication', 0.75),
        
        # Inspection/Maintenance
        (r'(?:inspection|walkthrough)\s*(?:on|dated?)?\s*', 'Inspection Date', 'maintenance', 0.85),
        (r'(?:repair\w*|maintenanc\w*)\s*(?:request\w*|schedul\w*)?\s*(?:on|for)?\s*', 'Repair/Maintenance', 'maintenance', 0.8),
    ]

    # Deadline indicators
    DEADLINE_WORDS = ['by', 'before', 'deadline', 'due', 'must', 'no later than', 'expire', 'within']
    
    # Patterns to exclude (not real events)
    EXCLUDE_PATTERNS = [
        r'(?:dob|d\.o\.b\.?|date\s+of\s+birth|born|birthday)\s*[:)]?\s*',
        r'(?:ssn|social\s+security)',
        r'(?:case\s+(?:no|number|#))',
    ]

    def __init__(self):
        # Compile patterns for efficiency
        self._date_patterns = [(re.compile(p, re.IGNORECASE), fmt) for p, fmt in self.DATE_PATTERNS]
        self._context_patterns = [
            (re.compile(p, re.IGNORECASE), title, etype, conf)
            for p, title, etype, conf in self.EVENT_CONTEXTS
        ]
        self._exclude_patterns = [re.compile(p, re.IGNORECASE) for p in self.EXCLUDE_PATTERNS]

    def extract_events(self, text: str, doc_type: str = "unknown") -> list[ExtractedEvent]:
        """
        Extract all dated events from document text.
        
        Args:
            text: Full document text
            doc_type: Document type hint (lease, notice, court_filing, etc.)
            
        Returns:
            List of extracted events sorted by date
        """
        events = []
        
        # Split into sentences/chunks for context
        chunks = self._split_into_chunks(text)
        
        for chunk in chunks:
            # Find all dates in this chunk
            dates_found = self._find_dates(chunk)
            
            for date, date_str, position in dates_found:
                # Get context around the date
                context_before = chunk[max(0, position-100):position].lower()
                context_after = chunk[position:position+50].lower()
                
                # Skip dates that are clearly not events (DOB, SSN, case numbers)
                if self._should_exclude(context_before):
                    continue
                
                # Skip dates too far in the past (likely DOBs or historical refs)
                if date.year < 2000:
                    continue
                
                # Determine event type from context
                event_type, title, confidence = self._classify_event(
                    context_before, context_after, doc_type
                )
                
                # Check if it's a deadline
                is_deadline = any(word in context_before for word in self.DEADLINE_WORDS)
                
                # Build description from surrounding text
                desc_start = max(0, position - 60)
                desc_end = min(len(chunk), position + len(date_str) + 60)
                description = chunk[desc_start:desc_end].strip()
                
                events.append(ExtractedEvent(
                    date=date,
                    event_type=event_type,
                    title=title,
                    description=description,
                    confidence=confidence,
                    source_text=date_str,
                    is_deadline=is_deadline
                ))
        
        # Deduplicate similar events
        events = self._deduplicate_events(events)

        # Sort by date
        events.sort(key=lambda e: e.date)

        # Publish events extracted event
        if events:
            try:
                event_bus.publish_sync(
                    EventType.EVENTS_EXTRACTED,
                    {
                        "count": len(events),
                        "doc_type": doc_type,
                        "event_types": list(set(e.event_type for e in events)),
                        "date_range": {
                            "earliest": events[0].date.isoformat() if events else None,
                            "latest": events[-1].date.isoformat() if events else None,
                        }
                    },
                    source="event_extractor",
                )
            except Exception:
                pass  # Don't fail extraction on event publish errors

        return events

    def _split_into_chunks(self, text: str) -> list[str]:
        """Split text into processable chunks (sentences/paragraphs)."""
        # Split on sentence endings and paragraph breaks
        chunks = re.split(r'(?<=[.!?])\s+|\n\n+', text)
        return [c.strip() for c in chunks if c.strip()]

    def _should_exclude(self, context: str) -> bool:
        """Check if this date should be excluded (DOB, case number, etc.)."""
        for pattern in self._exclude_patterns:
            if pattern.search(context):
                return True
        return False

    def _find_dates(self, text: str) -> list[tuple[datetime, str, int]]:
        """Find all dates in text with their positions."""
        dates = []
        
        for pattern, fmt in self._date_patterns:
            for match in pattern.finditer(text):
                try:
                    date = self._parse_match(match, fmt)
                    if date:
                        dates.append((date, match.group(0), match.start()))
                except (ValueError, IndexError):
                    continue
        
        return dates

    def _parse_match(self, match: re.Match, fmt: str) -> Optional[datetime]:
        """Parse a regex match into a datetime."""
        groups = match.groups()
        
        try:
            if fmt == 'MDY':
                month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
            elif fmt == 'ISO':
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            elif fmt == 'TEXT':
                month = self.MONTH_MAP[groups[0].lower()]
                day = int(groups[1])
                year = int(groups[2])
            elif fmt == 'DMY_TEXT':
                day = int(groups[0])
                month = self.MONTH_MAP[groups[1].lower()]
                year = int(groups[2])
            else:
                return None
            
            # Validate ranges
            if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
                return None
            
            return datetime(year, month, day, tzinfo=timezone.utc)
        
        except (ValueError, KeyError):
            return None

    def _classify_event(
        self, 
        context_before: str, 
        context_after: str,
        doc_type: str
    ) -> tuple[str, str, float]:
        """Classify event type based on surrounding context."""
        
        full_context = context_before + " " + context_after
        
        # Check each context pattern
        best_match = None
        best_confidence = 0.0
        
        for pattern, title, event_type, confidence in self._context_patterns:
            if pattern.search(full_context):
                if confidence > best_confidence:
                    best_match = (event_type, title, confidence)
                    best_confidence = confidence
        
        if best_match:
            return best_match
        
        # Fall back to doc_type hints
        type_defaults = {
            'notice': ('notice', 'Notice Date', 0.6),
            'lease': ('other', 'Lease Date', 0.6),
            'court_filing': ('court', 'Court Date', 0.7),
            'receipt': ('payment', 'Payment Date', 0.6),
            'payment_record': ('payment', 'Payment Date', 0.6),
        }
        
        return type_defaults.get(doc_type, ('other', 'Document Date', 0.5))

    def _deduplicate_events(self, events: list[ExtractedEvent]) -> list[ExtractedEvent]:
        """Remove duplicate events (same date + type)."""
        seen = set()
        unique = []
        
        for event in events:
            key = (event.date.date(), event.event_type, event.title)
            if key not in seen:
                seen.add(key)
                unique.append(event)
        
        return unique


# Singleton
_extractor: Optional[EventExtractor] = None


def get_event_extractor() -> EventExtractor:
    """Get or create the event extractor singleton."""
    global _extractor
    if _extractor is None:
        _extractor = EventExtractor()
    return _extractor
