"""
Document Recognition Training Service

Allows the system to learn from user corrections and improve over time.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4


@dataclass
class TrainingExample:
    """A single training example from user feedback."""
    id: str = field(default_factory=lambda: str(uuid4()))
    
    # Document info
    document_text: str = ""
    document_filename: str = ""
    document_hash: str = ""  # To prevent duplicates
    
    # System's prediction
    predicted_type: str = ""
    predicted_confidence: float = 0.0
    
    # User's correction
    correct_type: str = ""
    user_notes: str = ""
    
    # Extracted patterns (for learning)
    key_phrases_found: list[str] = field(default_factory=list)
    
    # Metadata
    user_id: str = ""
    county: str = "Dakota"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentTrainingService:
    """
    Service for collecting training data and improving recognition.
    
    Training Loop:
    1. User uploads document
    2. System classifies it (with confidence)
    3. If wrong, user corrects it
    4. Correction saved as training example
    5. Periodically: analyze patterns from corrections
    6. Update keyword weights based on what works
    """
    
    def __init__(self, storage_path: str = "data/training"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.examples_file = self.storage_path / "training_examples.json"
        self.learned_patterns_file = self.storage_path / "learned_patterns.json"
        
        # Load existing data
        self.examples: list[TrainingExample] = self._load_examples()
        self.learned_patterns: dict = self._load_learned_patterns()
    
    def _load_examples(self) -> list[TrainingExample]:
        """Load existing training examples."""
        if self.examples_file.exists():
            try:
                with open(self.examples_file, "r") as f:
                    data = json.load(f)
                    return [TrainingExample(**ex) for ex in data]
            except:
                pass
        return []
    
    def _load_learned_patterns(self) -> dict:
        """Load learned patterns."""
        if self.learned_patterns_file.exists():
            try:
                with open(self.learned_patterns_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {
            "boosted_keywords": {},  # keyword -> doc_type -> weight_boost
            "new_patterns": {},  # doc_type -> [new patterns]
            "suppressed_patterns": {},  # patterns that cause false positives
        }
    
    def _save_examples(self):
        """Save training examples."""
        data = []
        for ex in self.examples:
            d = asdict(ex)
            d["created_at"] = ex.created_at.isoformat()
            data.append(d)
        with open(self.examples_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def _save_learned_patterns(self):
        """Save learned patterns."""
        with open(self.learned_patterns_file, "w") as f:
            json.dump(self.learned_patterns, f, indent=2)
    
    # =========================================================================
    # Training API
    # =========================================================================
    
    def record_correction(
        self,
        document_text: str,
        document_filename: str,
        predicted_type: str,
        predicted_confidence: float,
        correct_type: str,
        user_notes: str = "",
        user_id: str = "",
        county: str = "Dakota"
    ) -> TrainingExample:
        """
        Record when a user corrects the system's prediction.
        
        This is the primary training signal - when we get it wrong,
        we learn from the correction.
        """
        import hashlib
        doc_hash = hashlib.md5(document_text.encode()).hexdigest()
        
        # Check for duplicates
        for ex in self.examples:
            if ex.document_hash == doc_hash:
                # Update existing instead of duplicate
                ex.correct_type = correct_type
                ex.user_notes = user_notes
                self._save_examples()
                return ex
        
        # Extract key phrases for learning
        key_phrases = self._extract_key_phrases(document_text)
        
        example = TrainingExample(
            document_text=document_text[:5000],  # Limit size
            document_filename=document_filename,
            document_hash=doc_hash,
            predicted_type=predicted_type,
            predicted_confidence=predicted_confidence,
            correct_type=correct_type,
            user_notes=user_notes,
            key_phrases_found=key_phrases,
            user_id=user_id,
            county=county,
        )
        
        self.examples.append(example)
        self._save_examples()
        
        # Immediately learn from this correction
        self._learn_from_correction(example)
        
        return example
    
    def record_confirmation(
        self,
        document_text: str,
        document_filename: str,
        predicted_type: str,
        predicted_confidence: float,
        user_id: str = ""
    ) -> None:
        """
        Record when user confirms the prediction was correct.
        
        This helps reinforce correct patterns.
        """
        key_phrases = self._extract_key_phrases(document_text)
        
        # Boost the patterns that led to correct prediction
        for phrase in key_phrases:
            phrase_lower = phrase.lower()
            if phrase_lower not in self.learned_patterns["boosted_keywords"]:
                self.learned_patterns["boosted_keywords"][phrase_lower] = {}
            
            current = self.learned_patterns["boosted_keywords"][phrase_lower].get(predicted_type, 0)
            self.learned_patterns["boosted_keywords"][phrase_lower][predicted_type] = current + 0.1
        
        self._save_learned_patterns()
    
    def _extract_key_phrases(self, text: str, max_phrases: int = 20) -> list[str]:
        """Extract potential key phrases from document text."""
        import re
        
        phrases = []
        
        # Legal document patterns
        patterns = [
            r"(?:notice\s+(?:to|of)\s+\w+)",
            r"(?:you\s+are\s+hereby\s+\w+)",
            r"(?:motion\s+(?:to|for)\s+\w+)",
            r"(?:writ\s+of\s+\w+)",
            r"(?:order\s+(?:to|of|for)\s+\w+)",
            r"(?:\d+\s*-?\s*day\s+notice)",
            r"(?:HOU\d{3})",
            r"(?:CIV\d{3})",
            r"(?:unlawful\s+detainer)",
            r"(?:eviction\s+\w+)",
            r"(?:security\s+deposit)",
            r"(?:lease\s+(?:agreement|violation|termination))",
        ]
        
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            phrases.extend(matches[:3])  # Limit per pattern
        
        return list(set(phrases))[:max_phrases]
    
    def _learn_from_correction(self, example: TrainingExample):
        """
        Immediately learn from a correction.
        
        When the system gets it wrong:
        1. Suppress patterns that led to wrong prediction
        2. Boost patterns that should lead to correct type
        """
        # Suppress patterns associated with wrong prediction
        for phrase in example.key_phrases_found:
            phrase_lower = phrase.lower()
            if phrase_lower not in self.learned_patterns["suppressed_patterns"]:
                self.learned_patterns["suppressed_patterns"][phrase_lower] = {}
            
            # Reduce weight for the wrong type
            current = self.learned_patterns["suppressed_patterns"][phrase_lower].get(
                example.predicted_type, 0
            )
            self.learned_patterns["suppressed_patterns"][phrase_lower][example.predicted_type] = current + 0.2
        
        # Boost patterns for correct type
        for phrase in example.key_phrases_found:
            phrase_lower = phrase.lower()
            if phrase_lower not in self.learned_patterns["boosted_keywords"]:
                self.learned_patterns["boosted_keywords"][phrase_lower] = {}
            
            current = self.learned_patterns["boosted_keywords"][phrase_lower].get(
                example.correct_type, 0
            )
            self.learned_patterns["boosted_keywords"][phrase_lower][example.correct_type] = current + 0.3
        
        self._save_learned_patterns()
    
    # =========================================================================
    # Analysis & Reporting
    # =========================================================================
    
    def get_training_stats(self) -> dict:
        """Get statistics about training data."""
        if not self.examples:
            return {
                "total_examples": 0,
                "accuracy_rate": 0,
                "common_mistakes": [],
            }
        
        total = len(self.examples)
        correct = sum(1 for ex in self.examples if ex.predicted_type == ex.correct_type)
        
        # Find common mistakes
        mistakes = {}
        for ex in self.examples:
            if ex.predicted_type != ex.correct_type:
                key = f"{ex.predicted_type} → {ex.correct_type}"
                mistakes[key] = mistakes.get(key, 0) + 1
        
        common_mistakes = sorted(mistakes.items(), key=lambda x: -x[1])[:10]
        
        return {
            "total_examples": total,
            "accuracy_rate": correct / total if total > 0 else 0,
            "correct_predictions": correct,
            "corrections_needed": total - correct,
            "common_mistakes": [{"error": k, "count": v} for k, v in common_mistakes],
            "learned_patterns_count": len(self.learned_patterns.get("boosted_keywords", {})),
            "suppressed_patterns_count": len(self.learned_patterns.get("suppressed_patterns", {})),
        }
    
    def get_weight_adjustments(self) -> dict:
        """
        Get keyword weight adjustments from learning.
        
        This can be applied to the recognition engine to improve accuracy.
        """
        adjustments = {}
        
        # Combine boosted and suppressed
        for keyword, type_boosts in self.learned_patterns.get("boosted_keywords", {}).items():
            if keyword not in adjustments:
                adjustments[keyword] = {}
            for doc_type, boost in type_boosts.items():
                adjustments[keyword][doc_type] = adjustments[keyword].get(doc_type, 0) + boost
        
        for keyword, type_suppresses in self.learned_patterns.get("suppressed_patterns", {}).items():
            if keyword not in adjustments:
                adjustments[keyword] = {}
            for doc_type, suppress in type_suppresses.items():
                adjustments[keyword][doc_type] = adjustments[keyword].get(doc_type, 0) - suppress
        
        return adjustments


# Singleton instance
_training_service: Optional[DocumentTrainingService] = None


def get_training_service() -> DocumentTrainingService:
    """Get the document training service singleton."""
    global _training_service
    if _training_service is None:
        _training_service = DocumentTrainingService()
    return _training_service
