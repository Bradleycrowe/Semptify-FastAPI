"""
Semptify 5.0 - Azure AI Service
Document Intelligence + OpenAI integration for document analysis.
"""

import asyncio
import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import httpx

from app.core.config import get_settings


class DocumentType(str, Enum):
    """Types of documents in a tenancy."""
    LEASE = "lease"
    NOTICE = "notice"
    RECEIPT = "receipt"
    LETTER = "letter"
    PHOTO = "photo"
    COURT_FILING = "court_filing"
    INSPECTION = "inspection"
    REPAIR_REQUEST = "repair_request"
    PAYMENT_RECORD = "payment_record"
    COMMUNICATION = "communication"
    UNKNOWN = "unknown"


@dataclass
class ExtractedDocument:
    """Result of document analysis."""
    doc_type: DocumentType
    confidence: float
    title: str
    summary: str
    key_dates: list[dict]  # [{date, description}]
    key_parties: list[dict]  # [{name, role}]
    key_amounts: list[dict]  # [{amount, description}]
    key_terms: list[str]
    full_text: str
    raw_response: dict
    analyzed_at: datetime


class AzureAIService:
    """
    Azure AI client for document processing.
    Uses Document Intelligence for OCR and structure extraction.
    Uses OpenAI for classification and understanding.
    """

    def __init__(self):
        settings = get_settings()
        self.endpoint = settings.azure_ai_endpoint.rstrip('/')
        self.api_key = settings.azure_ai_key1
        self.region = settings.azure_ai_region
        
        # Document Intelligence API
        self.doc_intel_url = f"{self.endpoint}/documentintelligence"
        
    async def analyze_document(
        self,
        content: bytes,
        filename: str,
        mime_type: str = "application/pdf"
    ) -> ExtractedDocument:
        """
        Full document analysis pipeline:
        1. Text extraction (local PDF extraction or Azure OCR)
        2. Classification with AI (Groq/Ollama/Azure)
        3. Extract key information
        """
        full_text = ""
        raw_result = {}
        
        # For text files, use content directly
        if mime_type in ("text/plain", "text/csv", "text/markdown") or filename.endswith(('.txt', '.csv', '.md')):
            try:
                full_text = content.decode('utf-8')
            except UnicodeDecodeError:
                full_text = content.decode('latin-1', errors='replace')
            raw_result = {"content": full_text, "source": "direct_text"}
        
        # For PDFs, use local extraction first
        elif mime_type == "application/pdf" or filename.lower().endswith('.pdf'):
            try:
                from app.services.pdf_extractor import get_pdf_extractor
                extractor = get_pdf_extractor()
                
                # Try local extraction first (fast, no API calls)
                result = extractor.extract(content)
                full_text = result.text
                raw_result = {
                    "content": full_text,
                    "source": result.method_used,
                    "page_count": result.page_count,
                    "has_images": result.has_images,
                    "confidence": result.confidence
                }
                
                # If extraction failed or got very little text, try Azure OCR
                if len(full_text.strip()) < 50 and self.api_key:
                    print(f"Local extraction got {len(full_text)} chars, trying Azure OCR...")
                    ocr_result = extractor.extract_with_ocr(
                        content,
                        azure_endpoint=self.endpoint,
                        azure_key=self.api_key
                    )
                    if ocr_result.text.strip():
                        full_text = ocr_result.text
                        raw_result = {
                            "content": full_text,
                            "source": ocr_result.method_used,
                            "page_count": ocr_result.page_count,
                            "confidence": ocr_result.confidence
                        }
            except Exception as e:
                print(f"PDF extraction error: {e}, falling back to Azure")
                # Fallback to Azure Document Intelligence
                raw_result = await self._extract_with_doc_intelligence(content, mime_type)
                full_text = self._get_text_from_result(raw_result)
        
        # For images, use Azure Document Intelligence (OCR)
        elif mime_type.startswith("image/") or filename.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.bmp')):
            raw_result = await self._extract_with_doc_intelligence(content, mime_type)
            full_text = self._get_text_from_result(raw_result)
        
        # Other file types - try to decode as text
        else:
            try:
                full_text = content.decode('utf-8')
            except:
                full_text = content.decode('latin-1', errors='replace')
            raw_result = {"content": full_text, "source": "text_decode"}

        # Step 2: Classify and extract with AI
        analysis = await self._classify_and_extract(full_text, filename)

        return ExtractedDocument(
            doc_type=DocumentType(analysis.get("doc_type", "unknown")),
            confidence=analysis.get("confidence", 0.0),
            title=analysis.get("title", filename),
            summary=analysis.get("summary", ""),
            key_dates=analysis.get("key_dates", []),
            key_parties=analysis.get("key_parties", []),
            key_amounts=analysis.get("key_amounts", []),
            key_terms=analysis.get("key_terms", []),
            full_text=full_text,
            raw_response=raw_result,
            analyzed_at=datetime.now(timezone.utc)
        )

    async def _extract_with_doc_intelligence(
        self,
        content: bytes,
        mime_type: str
    ) -> dict:
        """Use Azure Document Intelligence to extract text and structure."""
        
        # Use prebuilt-read model for general document OCR
        url = f"{self.doc_intel_url}/documentModels/prebuilt-read:analyze?api-version=2024-02-29-preview"
        
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": mime_type,
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Submit for analysis
            response = await client.post(url, headers=headers, content=content)
            
            if response.status_code == 202:
                # Async operation - poll for result
                operation_url = response.headers.get("Operation-Location")
                return await self._poll_operation(client, operation_url)
            elif response.status_code == 200:
                return response.json()
            else:
                # Return error info for debugging
                return {
                    "error": True,
                    "status": response.status_code,
                    "message": response.text
                }

    async def _poll_operation(
        self,
        client: httpx.AsyncClient,
        operation_url: str,
        max_attempts: int = 30
    ) -> dict:
        """Poll async operation until complete."""
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        
        for _ in range(max_attempts):
            response = await client.get(operation_url, headers=headers)
            result = response.json()
            
            status = result.get("status", "")
            if status == "succeeded":
                return result.get("analyzeResult", result)
            elif status == "failed":
                return {"error": True, "message": result.get("error", "Analysis failed")}
            
            await asyncio.sleep(1)
        
        return {"error": True, "message": "Operation timed out"}

    def _get_text_from_result(self, result: dict) -> str:
        """Extract plain text from Document Intelligence result."""
        if result.get("error"):
            return ""
        
        # Try different result structures
        if "content" in result:
            return result["content"]
        
        if "pages" in result:
            texts = []
            for page in result["pages"]:
                for line in page.get("lines", []):
                    texts.append(line.get("content", ""))
            return "\n".join(texts)
        
        return ""

    async def _classify_and_extract(
        self,
        text: str,
        filename: str
    ) -> dict:
        """Use AI to classify document and extract key information."""
        
        if not text.strip():
            return {
                "doc_type": "unknown",
                "confidence": 0.0,
                "title": filename,
                "summary": "Could not extract text from document",
                "key_dates": [],
                "key_parties": [],
                "key_amounts": [],
                "key_terms": []
            }

        # Build classification prompt
        prompt = f"""Analyze this document from a tenant's records. Extract key information.

Document filename: {filename}
Document text:
{text[:4000]}  # Limit to avoid token limits

Respond in JSON format:
{{
    "doc_type": "lease|notice|receipt|letter|photo|court_filing|inspection|repair_request|payment_record|communication|unknown",
    "confidence": 0.0-1.0,
    "title": "descriptive title",
    "summary": "2-3 sentence summary",
    "key_dates": [{{"date": "YYYY-MM-DD", "description": "what this date means"}}],
    "key_parties": [{{"name": "person/company name", "role": "landlord|tenant|court|other"}}],
    "key_amounts": [{{"amount": "dollar amount", "description": "what it's for"}}],
    "key_terms": ["important terms or clauses"]
}}"""

        # Call Azure OpenAI
        return await self._call_openai(prompt)

    async def _call_openai(self, prompt: str) -> dict:
        """
        Call AI for text analysis.
        
        Priority order (free/local first):
        1. Ollama - FREE, private, local (no API costs)
        2. Rule-based - FREE, instant, no API needed
        3. Groq - FREE tier: 14,400 req/day, then ~$0.59/M tokens
        4. Azure OpenAI - Pay per use (~$1-3/1K docs)
        """
        settings = get_settings()

        # 1. Try Ollama FIRST (completely free, local, private)
        try:
            result = await self._call_ollama(prompt, settings)
            if result:
                print("✓ Using Ollama (free, local)")
                return result
        except Exception as e:
            pass  # Silent fail, try next

        # 2. Try Groq (free tier: 14,400 requests/day)
        if settings.groq_api_key:
            try:
                result = await self._call_groq(prompt, settings)
                print("✓ Using Groq (free tier)")
                return result
            except Exception as e:
                print(f"Groq failed: {e}")

        # 3. Try Azure OpenAI (paid, but you may have free credits)
        if settings.azure_openai_endpoint and settings.azure_openai_api_key:
            try:
                result = await self._call_azure_openai(prompt, settings)
                if result:
                    print("✓ Using Azure OpenAI")
                    return result
            except Exception as e:
                print(f"Azure OpenAI failed: {e}")

        # 4. Fall back to rule-based (always free, always works)
        print("✓ Using rule-based classification (free)")
        return self._rule_based_classify(prompt)

    async def _call_azure_openai(self, prompt: str, settings) -> Optional[dict]:
        """Call Azure OpenAI for text analysis."""
        url = f"{settings.azure_openai_endpoint}/openai/deployments/{settings.azure_openai_deployment}/chat/completions?api-version=2024-02-15-preview"

        headers = {
            "api-key": settings.azure_openai_api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "messages": [
                {"role": "system", "content": "You are a document analysis assistant for tenant rights. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 1000
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return json.loads(content)
            else:
                return None

    async def _call_groq(self, prompt: str, settings) -> dict:
        """Call Groq API for fast, affordable text analysis."""
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": settings.groq_model or "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are a document analysis assistant for tenant rights. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return json.loads(content)
            else:
                raise Exception(f"Groq API error: {response.status_code}")

    async def _call_ollama(self, prompt: str, settings) -> Optional[dict]:
        """Call local Ollama for free, private text analysis."""
        base_url = settings.ollama_base_url or "http://localhost:11434"
        model = settings.ollama_model or "llama3.2"
        
        # Quick check if Ollama is running
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{base_url}/api/tags")
                if r.status_code != 200:
                    return None
        except Exception:
            return None

        url = f"{base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": f"You are a document analysis assistant. Respond with valid JSON only.\n\n{prompt}",
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": 1000,
            }
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                result = response.json()
                content = result.get("response", "{}")
                # Clean up
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                return json.loads(content.strip())
            else:
                raise Exception(f"Ollama error: {response.status_code}")

    def _rule_based_classify(self, text: str) -> dict:
        """Fallback rule-based document classification."""
        text_lower = text.lower()
        
        # Determine document type by keywords
        doc_type = "unknown"
        confidence = 0.5
        
        if any(w in text_lower for w in ["lease agreement", "rental agreement", "tenancy agreement"]):
            doc_type = "lease"
            confidence = 0.9
        elif any(w in text_lower for w in ["notice to quit", "eviction notice", "notice to vacate", "pay or quit"]):
            doc_type = "notice"
            confidence = 0.85
        elif any(w in text_lower for w in ["receipt", "payment received", "amount paid"]):
            doc_type = "receipt"
            confidence = 0.8
        elif any(w in text_lower for w in ["repair", "maintenance request", "work order"]):
            doc_type = "repair_request"
            confidence = 0.8
        elif any(w in text_lower for w in ["court", "summons", "complaint", "filing"]):
            doc_type = "court_filing"
            confidence = 0.85
        elif any(w in text_lower for w in ["inspection", "walkthrough", "condition report"]):
            doc_type = "inspection"
            confidence = 0.8
        
        return {
            "doc_type": doc_type,
            "confidence": confidence,
            "title": "Document",
            "summary": "Rule-based classification (AI not available)",
            "key_dates": [],
            "key_parties": [],
            "key_amounts": [],
            "key_terms": []
        }

    async def quick_classify(self, text: str) -> tuple[DocumentType, float]:
        """Quick classification without full extraction."""
        result = self._rule_based_classify(text)
        return DocumentType(result["doc_type"]), result["confidence"]


# Singleton instance
_azure_ai: Optional[AzureAIService] = None


def get_azure_ai() -> AzureAIService:
    """Get or create Azure AI service instance."""
    global _azure_ai
    if _azure_ai is None:
        _azure_ai = AzureAIService()
    return _azure_ai
