"""
Semptify - Google Gemini AI Service
FREE tier: 1,500 requests/day
Fast, capable AI for document classification and extraction.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import get_settings


@dataclass
class GeminiAnalysisResult:
    """Result from Gemini document analysis."""
    doc_type: str
    confidence: float
    title: str
    summary: str
    key_dates: list[dict]
    key_parties: list[dict]
    key_amounts: list[dict]
    key_terms: list[str]
    issues_detected: list[dict]
    analyzed_at: datetime


class GeminiAIService:
    """
    Google Gemini AI client for document processing.
    FREE tier: 1,500 requests/day with Gemini 1.5 Flash
    """

    API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    
    # Model options
    MODELS = {
        "flash": "gemini-1.5-flash",      # Fast, free tier friendly
        "pro": "gemini-1.5-pro",          # More capable
        "flash-8b": "gemini-1.5-flash-8b", # Fastest, lowest cost
    }

    def __init__(self):
        settings = get_settings()
        self.api_key = getattr(settings, 'gemini_api_key', None) or getattr(settings, 'google_ai_api_key', None)
        self.model = getattr(settings, 'gemini_model', self.MODELS["flash"])
        
    @property
    def is_available(self) -> bool:
        """Check if Gemini is configured."""
        return bool(self.api_key)

    async def analyze_document(
        self,
        text: str,
        filename: str,
        doc_hint: Optional[str] = None,
    ) -> GeminiAnalysisResult:
        """
        Analyze a document using Gemini.
        
        Args:
            text: Document text content
            filename: Original filename
            doc_hint: Optional hint about document type
            
        Returns:
            GeminiAnalysisResult with extracted information
        """
        if not self.is_available:
            raise ValueError("Gemini API key not configured. Set GEMINI_API_KEY in .env")
        
        prompt = self._build_analysis_prompt(text, filename, doc_hint)
        
        url = f"{self.API_URL}/{self.model}:generateContent?key={self.api_key}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.1,
                        "topP": 0.95,
                        "maxOutputTokens": 4096,
                    }
                }
            )
            
            if response.status_code != 200:
                raise ValueError(f"Gemini API error: {response.status_code} - {response.text}")
            
            data = response.json()
            
            # Extract text from response
            result_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
            
            return self._parse_response(result_text)

    async def chat(
        self,
        message: str,
        context: str = "tenant_rights",
        history: Optional[list] = None,
    ) -> str:
        """
        Chat with Gemini about tenant rights.
        
        Args:
            message: User's question
            context: Context type (tenant_rights, eviction_defense, etc.)
            history: Previous conversation history
            
        Returns:
            AI response text
        """
        if not self.is_available:
            raise ValueError("Gemini API key not configured")
        
        system_prompt = self._get_system_prompt(context)
        
        # Build conversation
        contents = []
        
        # Add system context as first user message
        contents.append({
            "role": "user",
            "parts": [{"text": f"Context: {system_prompt}\n\nQuestion: {message}"}]
        })
        
        url = f"{self.API_URL}/{self.model}:generateContent?key={self.api_key}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                json={
                    "contents": contents,
                    "generationConfig": {
                        "temperature": 0.7,
                        "topP": 0.95,
                        "maxOutputTokens": 2048,
                    }
                }
            )
            
            if response.status_code != 200:
                raise ValueError(f"Gemini API error: {response.status_code}")
            
            data = response.json()
            return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "I couldn't process that request.")

    async def generate_document(
        self,
        doc_type: str,
        case_data: dict,
    ) -> str:
        """Generate a legal document draft."""
        if not self.is_available:
            raise ValueError("Gemini API key not configured")
        
        prompt = f"""Generate a {doc_type} document for a Minnesota eviction case.

Case Information:
{json.dumps(case_data, indent=2)}

Generate a professional, legally appropriate document following Minnesota court requirements.
Include proper formatting, case caption, and all required sections.
"""
        
        url = f"{self.API_URL}/{self.model}:generateContent?key={self.api_key}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 4096,
                    }
                }
            )
            
            if response.status_code != 200:
                raise ValueError(f"Gemini API error: {response.status_code}")
            
            data = response.json()
            return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

    def _build_analysis_prompt(self, text: str, filename: str, doc_hint: Optional[str]) -> str:
        """Build the document analysis prompt."""
        return f"""Analyze this legal document and extract key information.

Filename: {filename}
{f"Document type hint: {doc_hint}" if doc_hint else ""}

Document text:
---
{text[:8000]}
---

Respond with a JSON object containing:
{{
    "doc_type": "summons|complaint|lease|notice|payment_record|communication|court_filing|other",
    "confidence": 0.0-1.0,
    "title": "document title or description",
    "summary": "brief 2-3 sentence summary",
    "key_dates": [{{"date": "YYYY-MM-DD", "description": "what this date means", "is_deadline": true/false}}],
    "key_parties": [{{"name": "party name", "role": "landlord|tenant|attorney|court|other", "contact": "if available"}}],
    "key_amounts": [{{"amount": 0.00, "description": "what this amount is for", "period": "monthly|one-time|etc"}}],
    "key_terms": ["important term 1", "important term 2"],
    "issues_detected": [{{"type": "issue type", "severity": "critical|high|medium|low", "description": "issue details", "legal_basis": "relevant law if any"}}]
}}

Respond ONLY with valid JSON."""

    def _parse_response(self, response_text: str) -> GeminiAnalysisResult:
        """Parse the Gemini response into a result object."""
        try:
            # Try to extract JSON from response
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            data = json.loads(text)
            
            return GeminiAnalysisResult(
                doc_type=data.get("doc_type", "unknown"),
                confidence=float(data.get("confidence", 0.5)),
                title=data.get("title", ""),
                summary=data.get("summary", ""),
                key_dates=data.get("key_dates", []),
                key_parties=data.get("key_parties", []),
                key_amounts=data.get("key_amounts", []),
                key_terms=data.get("key_terms", []),
                issues_detected=data.get("issues_detected", []),
                analyzed_at=datetime.now(timezone.utc),
            )
        except json.JSONDecodeError:
            # Return minimal result on parse failure
            return GeminiAnalysisResult(
                doc_type="unknown",
                confidence=0.0,
                title="Parse error",
                summary=response_text[:200],
                key_dates=[],
                key_parties=[],
                key_amounts=[],
                key_terms=[],
                issues_detected=[],
                analyzed_at=datetime.now(timezone.utc),
            )

    def _get_system_prompt(self, context: str) -> str:
        """Get system prompt based on context."""
        prompts = {
            "tenant_rights": """You are a helpful legal assistant specializing in Minnesota tenant rights.
You provide accurate, practical advice about:
- Tenant rights under Minnesota law (Chapter 504B)
- Eviction procedures and defenses
- Lease agreements and violations
- Security deposits and rent issues
- Habitability and repairs
- Fair housing protections

Always recommend consulting with a licensed attorney for specific legal advice.
Provide citations to Minnesota statutes when relevant.""",
            
            "eviction_defense": """You are an expert in Minnesota eviction defense.
Help tenants understand:
- Eviction process timeline and deadlines
- Common defenses (improper notice, retaliation, habitability)
- Court procedures in Minnesota
- How to file an Answer
- Rent escrow procedures

Always emphasize the importance of meeting court deadlines.
Recommend HOME Line (612-728-5767) for free tenant assistance.""",
        }
        return prompts.get(context, prompts["tenant_rights"])


# Singleton instance
_gemini_service: Optional[GeminiAIService] = None


def get_gemini_service() -> GeminiAIService:
    """Get or create the Gemini service singleton."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiAIService()
    return _gemini_service
