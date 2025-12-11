"""
🔍 Document Recognition Engine - API Router
============================================
REST API endpoints for the world-class document recognition engine.
Integrates with Brain Mesh for real-time updates and cross-module communication.
Includes handwriting recognition and forgery detection.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query, UploadFile, File
from pydantic import BaseModel, Field
import io
import tempfile
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.services.recognition import (
    DocumentRecognitionEngine,
    RecognitionResult,
    DocumentType,
    DocumentCategory,
    ConfidenceLevel,
    EntityType,
    IssueSeverity,
    # Handwriting & Forgery
    HandwritingAnalyzer,
    HandwritingAnalysisResult,
    SignatureProfile,
    SignatureStatus,
    ForgeryType,
    RiskLevel,
    analyze_handwriting,
)
from app.services.positronic_brain import (
    get_brain,
    PositronicBrain,
    BrainEvent,
    EventType,
    ModuleType,
)
from app.core.security import require_user, StorageUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recognition", tags=["Document Recognition"])


# =============================================================================
# Request/Response Models
# =============================================================================

class AnalyzeTextRequest(BaseModel):
    """Request to analyze document text."""
    text: str = Field(..., min_length=10, description="Document text to analyze")
    filename: Optional[str] = Field(None, description="Original filename for context")
    include_handwriting: bool = Field(True, description="Include handwriting/forgery analysis")


class QuickClassifyRequest(BaseModel):
    """Request for quick document classification."""
    text: str = Field(..., min_length=10, description="Document text to classify")


class HandwritingAnalyzeRequest(BaseModel):
    """Request for handwriting/forgery analysis."""
    text: str = Field(..., min_length=10, description="Document text to analyze")
    document_type: Optional[str] = Field(None, description="Document type for context")


class SignatureCompareRequest(BaseModel):
    """Request to compare signatures."""
    text: str = Field(..., min_length=10, description="Document text with signature")
    reference_name: str = Field(..., description="Name of expected signer")
    reference_signatures: Optional[List[Dict[str, Any]]] = Field(
        None, description="Known signature profiles for comparison"
    )


class BatchAnalyzeRequest(BaseModel):
    """Request to analyze multiple documents."""
    documents: List[Dict[str, str]] = Field(
        ..., 
        description="List of documents with 'text' and optional 'filename' keys"
    )


# Response models
class EntityResponse(BaseModel):
    id: str
    type: str
    value: str
    confidence: float
    attributes: Dict[str, Any] = {}


class LegalIssueResponse(BaseModel):
    id: str
    type: str
    title: str
    description: str
    severity: str
    statute: Optional[str] = None
    defense_available: bool = False


class SignatureResponse(BaseModel):
    id: str
    signer_name: str
    location: str
    confidence: float
    characteristics: Dict[str, Any]


class ForgeryIndicatorResponse(BaseModel):
    id: str
    type: str
    description: str
    risk_level: str
    confidence: float
    evidence: List[str]
    legal_significance: str
    recommended_action: str


class HandwritingResponse(BaseModel):
    analysis_id: str
    signatures: List[SignatureResponse]
    forgery_indicators: List[ForgeryIndicatorResponse]
    risk_level: str
    risk_score: float
    total_signatures: int
    suspicious_elements: int
    recommendations: List[str]
    requires_expert_review: bool


class PartyResponse(BaseModel):
    """Party information (sender or recipient)."""
    name: str = ""
    role: str = ""  # landlord, tenant, court, attorney, etc.
    organization: str = ""
    confidence: float = 0.0


class ToneResponse(BaseModel):
    """Document tone and direction analysis."""
    # WHO sent it and WHO received it
    sender: PartyResponse
    recipient: PartyResponse
    communication_flow: str  # e.g., "landlord_to_tenant"
    from_to_summary: str  # e.g., "From Landlord → To Tenant"
    
    # Tone analysis
    primary_tone: str
    tone_confidence: float
    tone_description: str
    
    # Process direction
    primary_direction: str
    direction_confidence: float
    what_this_means: str
    likely_next_step: str
    recommended_response: str
    
    # Urgency
    urgency_score: float
    days_to_respond: Optional[int] = None
    tone_breakdown: Dict[str, float] = {}


class RecognitionResponse(BaseModel):
    """Full recognition analysis response."""
    analysis_id: str
    document_type: str
    document_category: str
    confidence_score: float
    confidence_level: str
    entities: List[EntityResponse]
    legal_issues: List[LegalIssueResponse]
    applicable_statutes: List[str]
    defense_options: List[str]
    urgency_level: str
    risk_score: float
    passes_completed: int
    processing_time_ms: float
    # Tone and direction analysis
    tone: Optional[ToneResponse] = None
    # Handwriting analysis (if included)
    handwriting: Optional[HandwritingResponse] = None


class QuickClassifyResponse(BaseModel):
    document_type: str
    document_category: str
    confidence: float
    confidence_level: str


class BatchAnalyzeResponse(BaseModel):
    results: List[RecognitionResponse]
    total_documents: int
    successful: int
    failed: int
    total_time_ms: float


# =============================================================================
# Module State
# =============================================================================

_engine: Optional[DocumentRecognitionEngine] = None
_handwriting_analyzer: Optional[HandwritingAnalyzer] = None


def get_engine() -> DocumentRecognitionEngine:
    """Get or create the recognition engine singleton."""
    global _engine
    if _engine is None:
        _engine = DocumentRecognitionEngine()
    return _engine


def get_handwriting_analyzer() -> HandwritingAnalyzer:
    """Get or create the handwriting analyzer singleton."""
    global _handwriting_analyzer
    if _handwriting_analyzer is None:
        _handwriting_analyzer = HandwritingAnalyzer()
    return _handwriting_analyzer


# =============================================================================
# Brain Mesh Integration
# =============================================================================

async def emit_analysis_event(
    brain: PositronicBrain,
    result: RecognitionResult,
    user_id: Optional[str] = None
):
    """Emit analysis complete event to Brain Mesh."""
    try:
        await brain.emit(BrainEvent(
            event_type=EventType.DOCUMENT_ANALYZED,
            source_module=ModuleType.DOCUMENTS,
            data={
                "analysis_id": result.analysis_id,
                "document_type": result.document_type.value,
                "confidence": result.confidence.overall_score,
                "entities_found": len(result.entities),
                "issues_found": len(result.legal_analysis.issues),
                "urgency": result.legal_analysis.urgency_level,
            },
            user_id=user_id
        ))
        
        # If critical issues, emit defense event
        critical_issues = result.get_critical_issues()
        if critical_issues:
            await brain.emit(BrainEvent(
                event_type=EventType.DEFENSE_IDENTIFIED,
                source_module=ModuleType.DOCUMENTS,
                data={
                    "analysis_id": result.analysis_id,
                    "critical_issues": len(critical_issues),
                    "defense_options": result.legal_analysis.defense_options,
                },
                user_id=user_id
            ))
    except Exception as e:
        logger.warning(f"Could not emit Brain event: {e}")


async def emit_forgery_event(
    brain: PositronicBrain,
    result: HandwritingAnalysisResult,
    user_id: Optional[str] = None
):
    """Emit forgery detection event to Brain Mesh."""
    try:
        if result.overall_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            await brain.emit(BrainEvent(
                event_type=EventType.ERROR_OCCURRED,  # Use error for critical alerts
                source_module=ModuleType.DOCUMENTS,
                data={
                    "alert_type": "forgery_detected",
                    "analysis_id": result.analysis_id,
                    "risk_level": result.overall_risk_level.value,
                    "risk_score": result.forgery_risk_score,
                    "indicators": len(result.forgery_indicators),
                    "requires_review": result.requires_expert_review,
                },
                user_id=user_id
            ))
    except Exception as e:
        logger.warning(f"Could not emit forgery event: {e}")


# =============================================================================
# Helper Functions
# =============================================================================

def result_to_response(
    result: RecognitionResult, 
    processing_time_ms: float,
    handwriting_result: Optional[HandwritingAnalysisResult] = None
) -> RecognitionResponse:
    """Convert RecognitionResult to API response."""
    
    # Build handwriting response if available
    handwriting_response = None
    if handwriting_result:
        handwriting_response = HandwritingResponse(
            analysis_id=handwriting_result.analysis_id,
            signatures=[
                SignatureResponse(
                    id=s.id,
                    signer_name=s.signer_name,
                    location=s.location_in_doc,
                    confidence=s.confidence,
                    characteristics={
                        "slant": s.estimated_slant,
                        "size": s.estimated_size,
                        "complexity": s.estimated_complexity,
                        "has_flourish": s.has_flourish,
                        "legible": s.is_legible,
                    }
                )
                for s in handwriting_result.signatures
            ],
            forgery_indicators=[
                ForgeryIndicatorResponse(
                    id=i.id,
                    type=i.forgery_type.value,
                    description=i.description,
                    risk_level=i.risk_level.value,
                    confidence=i.confidence,
                    evidence=i.evidence,
                    legal_significance=i.legal_significance,
                    recommended_action=i.recommended_action,
                )
                for i in handwriting_result.forgery_indicators
            ],
            risk_level=handwriting_result.overall_risk_level.value,
            risk_score=handwriting_result.forgery_risk_score,
            total_signatures=handwriting_result.total_signatures,
            suspicious_elements=handwriting_result.suspicious_elements,
            recommendations=handwriting_result.recommendations,
            requires_expert_review=handwriting_result.requires_expert_review,
        )
    
    # Build tone response if available
    tone_response = None
    if result.tone_analysis:
        tone = result.tone_analysis
        tone_response = ToneResponse(
            # WHO sent and received
            sender=PartyResponse(
                name=tone.sender.name,
                role=tone.sender.role,
                organization=tone.sender.organization,
                confidence=tone.sender.confidence,
            ),
            recipient=PartyResponse(
                name=tone.recipient.name,
                role=tone.recipient.role,
                organization=tone.recipient.organization,
                confidence=tone.recipient.confidence,
            ),
            communication_flow=tone.communication_flow.value,
            from_to_summary=f"From {tone.sender.role or 'Unknown'} → To {tone.recipient.role or 'Unknown'}",
            # Tone
            primary_tone=tone.primary_tone.value,
            tone_confidence=tone.tone_confidence,
            tone_description=tone.plain_english_tone,
            # Direction
            primary_direction=tone.primary_direction.value,
            direction_confidence=tone.direction_confidence,
            what_this_means=tone.what_this_means,
            likely_next_step=tone.likely_next_step,
            recommended_response=tone.recommended_response_tone,
            # Urgency
            urgency_score=tone.urgency_score,
            days_to_respond=tone.days_to_respond,
            tone_breakdown={k.value: v for k, v in tone.tone_breakdown.items()},
        )

    return RecognitionResponse(
        analysis_id=result.analysis_id,
        document_type=result.document_type.value,
        document_category=result.document_category.value,
        confidence_score=result.confidence.overall_score,
        confidence_level=result.confidence.level.value,
        entities=[
            EntityResponse(
                id=e.id,
                type=e.entity_type.value,
                value=e.value,
                confidence=e.confidence,
                attributes=e.attributes,
            )
            for e in result.entities
        ],
        legal_issues=[
            LegalIssueResponse(
                id=i.id,
                type=i.issue_type,
                title=i.title,
                description=i.description,
                severity=i.severity.value,
                statute=i.mn_statute,
                defense_available=i.defense_available,
            )
            for i in result.legal_analysis.issues
        ],
        applicable_statutes=result.legal_analysis.applicable_mn_statutes,
        defense_options=result.legal_analysis.defense_options,
        urgency_level=result.legal_analysis.urgency_level,
        risk_score=result.legal_analysis.risk_score,
        passes_completed=result.passes_completed,
        processing_time_ms=processing_time_ms,
        tone=tone_response,
        handwriting=handwriting_response,
    )


# =============================================================================
# API Endpoints - Document Recognition
# =============================================================================

@router.post("/analyze", response_model=RecognitionResponse)
async def analyze_text(
    request: AnalyzeTextRequest,
    background_tasks: BackgroundTasks,
    user: StorageUser = Depends(require_user),
):
    """
    🔍 Analyze document text with the recognition engine.
    
    Performs multi-pass analysis including:
    - Context-aware document structure analysis
    - Entity extraction (parties, dates, amounts, addresses)
    - Minnesota tenant law issue detection
    - Relationship mapping between entities
    - Confidence scoring with uncertainty identification
    - Handwriting/signature analysis and forgery detection
    
    Returns comprehensive analysis with legal insights.
    """
    engine = get_engine()
    brain = get_brain()
    
    start_time = datetime.now()
    
    try:
        # Run document analysis
        result = await engine.analyze(
            text=request.text,
            filename=request.filename,
        )
        
        # Run handwriting analysis if requested
        handwriting_result = None
        if request.include_handwriting:
            analyzer = get_handwriting_analyzer()
            handwriting_result = await analyzer.analyze(
                request.text,
                document_type=result.document_type.value,
            )
            
            # Emit forgery event if high risk
            background_tasks.add_task(
                emit_forgery_event,
                brain,
                handwriting_result,
                user.user_id,
            )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Emit analysis event
        background_tasks.add_task(
            emit_analysis_event,
            brain,
            result,
            user.user_id,
        )
        
        return result_to_response(result, processing_time, handwriting_result)
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze-file", response_model=RecognitionResponse)
async def analyze_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Document file to analyze"),
    user: StorageUser = Depends(require_user),
):
    """
    📁 Analyze an uploaded document file.
    
    Supports:
    - PDF files (text extraction)
    - Images (PNG, JPG, GIF) - OCR text extraction
    - Word documents (.doc, .docx)
    - Text files (.txt, .rtf)
    
    Returns comprehensive analysis with legal insights.
    """
    engine = get_engine()
    brain = get_brain()
    
    # Validate file type
    allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.txt', '.doc', '.docx', '.rtf'}
    file_ext = os.path.splitext(file.filename or '')[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Read file content
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 20MB.")
    
    start_time = datetime.now()
    
    try:
        # Extract text based on file type
        text = ""
        
        if file_ext == '.txt':
            # Plain text
            text = content.decode('utf-8', errors='ignore')
        
        elif file_ext == '.rtf':
            # RTF - basic text extraction
            text = content.decode('utf-8', errors='ignore')
            # Strip RTF formatting (basic)
            import re
            text = re.sub(r'\\[a-z]+\d*\s?', '', text)
            text = re.sub(r'[{}]', '', text)
        
        elif file_ext == '.pdf':
            # PDF text extraction
            try:
                import fitz  # PyMuPDF
                with fitz.open(stream=content, filetype="pdf") as doc:
                    text = "\n".join(page.get_text() for page in doc)
            except ImportError:
                # Fallback: try pdfplumber
                try:
                    import pdfplumber
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name
                    try:
                        with pdfplumber.open(tmp_path) as pdf:
                            text = "\n".join(page.extract_text() or '' for page in pdf.pages)
                    finally:
                        os.unlink(tmp_path)
                except ImportError:
                    raise HTTPException(
                        status_code=500, 
                        detail="PDF processing not available. Install PyMuPDF or pdfplumber."
                    )
        
        elif file_ext in {'.png', '.jpg', '.jpeg', '.gif'}:
            # Image OCR
            try:
                import pytesseract
                from PIL import Image
                img = Image.open(io.BytesIO(content))
                text = pytesseract.image_to_string(img)
            except ImportError:
                raise HTTPException(
                    status_code=500, 
                    detail="Image OCR not available. Install pytesseract and Pillow."
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}")
        
        elif file_ext in {'.doc', '.docx'}:
            # Word document
            try:
                import docx
                with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    doc = docx.Document(tmp_path)
                    text = "\n".join(para.text for para in doc.paragraphs)
                finally:
                    os.unlink(tmp_path)
            except ImportError:
                raise HTTPException(
                    status_code=500, 
                    detail="Word document processing not available. Install python-docx."
                )
        
        if not text or len(text.strip()) < 10:
            raise HTTPException(
                status_code=400, 
                detail="Could not extract enough text from document. Try a different file or paste text directly."
            )
        
        # Run document analysis
        result = await engine.analyze(
            text=text,
            filename=file.filename,
        )
        
        # Run handwriting analysis
        analyzer = get_handwriting_analyzer()
        handwriting_result = await analyzer.analyze(
            text,
            document_type=result.document_type.value,
        )
        
        # Emit forgery event if high risk
        background_tasks.add_task(
            emit_forgery_event,
            brain,
            handwriting_result,
            user.user_id,
        )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Emit analysis event
        background_tasks.add_task(
            emit_analysis_event,
            brain,
            result,
            user.user_id,
        )
        
        return result_to_response(result, processing_time, handwriting_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/quick-classify", response_model=QuickClassifyResponse)
async def quick_classify(
    request: QuickClassifyRequest,
    user: StorageUser = Depends(require_user),
):
    """
    ⚡ Quick document classification without full analysis.
    
    Fast classification for upload sorting and initial triage.
    """
    engine = get_engine()
    
    try:
        result = await engine.analyze(request.text)
        
        return QuickClassifyResponse(
            document_type=result.document_type.value,
            document_category=result.document_category.value,
            confidence=result.confidence.overall_score,
            confidence_level=result.confidence.level.value,
        )
        
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


# =============================================================================
# API Endpoints - Handwriting & Forgery Detection
# =============================================================================

@router.post("/handwriting/analyze", response_model=HandwritingResponse)
async def analyze_handwriting_endpoint(
    request: HandwritingAnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: StorageUser = Depends(require_user),
):
    """
    ✍️ Analyze document for handwriting and detect forgery.
    
    Performs comprehensive handwriting analysis including:
    - Signature extraction and profiling
    - Handwritten dates, amounts, initials detection
    - Forgery indicator detection
    - Date manipulation detection
    - Amount alteration detection
    - Minnesota-specific notice backdating detection
    
    Returns risk assessment and recommendations.
    """
    analyzer = get_handwriting_analyzer()
    brain = get_brain()
    
    try:
        result = await analyzer.analyze(
            request.text,
            document_type=request.document_type,
        )
        
        # Emit forgery event if high risk
        background_tasks.add_task(
            emit_forgery_event,
            brain,
            result,
            user.user_id,
        )
        
        return HandwritingResponse(
            analysis_id=result.analysis_id,
            signatures=[
                SignatureResponse(
                    id=s.id,
                    signer_name=s.signer_name,
                    location=s.location_in_doc,
                    confidence=s.confidence,
                    characteristics={
                        "slant": s.estimated_slant,
                        "size": s.estimated_size,
                        "complexity": s.estimated_complexity,
                        "has_flourish": s.has_flourish,
                        "legible": s.is_legible,
                    }
                )
                for s in result.signatures
            ],
            forgery_indicators=[
                ForgeryIndicatorResponse(
                    id=i.id,
                    type=i.forgery_type.value,
                    description=i.description,
                    risk_level=i.risk_level.value,
                    confidence=i.confidence,
                    evidence=i.evidence,
                    legal_significance=i.legal_significance,
                    recommended_action=i.recommended_action,
                )
                for i in result.forgery_indicators
            ],
            risk_level=result.overall_risk_level.value,
            risk_score=result.forgery_risk_score,
            total_signatures=result.total_signatures,
            suspicious_elements=result.suspicious_elements,
            recommendations=result.recommendations,
            requires_expert_review=result.requires_expert_review,
        )
        
    except Exception as e:
        logger.error(f"Handwriting analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/signature/verify")
async def verify_signature(
    request: SignatureCompareRequest,
    user: StorageUser = Depends(require_user),
):
    """
    ✅ Verify signature against known reference.
    
    Compares signatures found in document against expected signer.
    Returns verification status and discrepancy details.
    """
    analyzer = get_handwriting_analyzer()
    
    try:
        # Analyze document
        result = await analyzer.analyze(request.text)
        
        # Check signatures against reference name
        verified = False
        matches = []
        mismatches = []
        
        for sig in result.signatures:
            name_match = request.reference_name.lower() in sig.signer_name.lower() or \
                        sig.signer_name.lower() in request.reference_name.lower()
            
            if name_match and sig.confidence >= 0.6:
                verified = True
                matches.append({
                    "signature_id": sig.id,
                    "signer_name": sig.signer_name,
                    "location": sig.location_in_doc,
                    "confidence": sig.confidence,
                    "status": "verified" if sig.confidence >= 0.8 else "probable_match",
                })
            elif sig.signer_name != "Unknown Signer":
                mismatches.append({
                    "signature_id": sig.id,
                    "found_name": sig.signer_name,
                    "expected_name": request.reference_name,
                    "location": sig.location_in_doc,
                })
        
        return {
            "verified": verified,
            "reference_name": request.reference_name,
            "signatures_found": len(result.signatures),
            "matches": matches,
            "mismatches": mismatches,
            "forgery_risk": result.overall_risk_level.value,
            "recommendations": result.recommendations[:5],
        }
        
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.get("/forgery/types")
async def get_forgery_types():
    """
    📋 Get all detectable forgery types.
    """
    return {
        "forgery_types": [
            {
                "value": ft.value,
                "name": ft.name,
                "description": _get_forgery_description(ft),
            }
            for ft in ForgeryType
        ],
        "risk_levels": [
            {"value": rl.value, "name": rl.name}
            for rl in RiskLevel
        ],
        "signature_statuses": [
            {"value": ss.value, "name": ss.name}
            for ss in SignatureStatus
        ],
    }


def _get_forgery_description(ft: ForgeryType) -> str:
    """Get description for forgery type."""
    descriptions = {
        ForgeryType.SIGNATURE_MISMATCH: "Signature doesn't match expected signer",
        ForgeryType.DATE_ALTERATION: "Date appears to have been changed or backdated",
        ForgeryType.AMOUNT_MODIFICATION: "Financial amounts appear altered",
        ForgeryType.TEXT_INSERTION: "Text appears inserted after document was signed",
        ForgeryType.WHITEOUT_DETECTED: "Evidence of correction fluid or whiteout",
        ForgeryType.INK_INCONSISTENCY: "Multiple ink types or colors detected",
        ForgeryType.PRESSURE_ANOMALY: "Unusual writing pressure patterns",
        ForgeryType.TRACING_DETECTED: "Signature appears traced",
        ForgeryType.DIGITAL_MANIPULATION: "Digital editing detected",
        ForgeryType.COPY_PASTE_SIGNATURE: "Signature appears copied from another document",
        ForgeryType.TIMESTAMP_MISMATCH: "Timestamps don't align with claimed dates",
    }
    return descriptions.get(ft, "Unknown forgery indicator")


# =============================================================================
# API Endpoints - Batch & Reference
# =============================================================================

@router.post("/batch", response_model=BatchAnalyzeResponse)
async def batch_analyze(
    request: BatchAnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: StorageUser = Depends(require_user),
):
    """
    📚 Batch analyze multiple documents.
    """
    engine = get_engine()
    analyzer = get_handwriting_analyzer()
    brain = get_brain()
    
    start_time = datetime.now()
    results = []
    successful = 0
    failed = 0
    
    for doc in request.documents:
        try:
            text = doc.get("text", "")
            filename = doc.get("filename")
            
            if len(text) < 10:
                failed += 1
                continue
            
            doc_start = datetime.now()
            result = await engine.analyze(text, filename=filename)
            handwriting_result = await analyzer.analyze(text)
            doc_time = (datetime.now() - doc_start).total_seconds() * 1000
            
            results.append(result_to_response(result, doc_time, handwriting_result))
            successful += 1
            
            background_tasks.add_task(emit_analysis_event, brain, result, user.user_id)
            
        except Exception as e:
            logger.error(f"Batch item failed: {e}")
            failed += 1
    
    total_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return BatchAnalyzeResponse(
        results=results,
        total_documents=len(request.documents),
        successful=successful,
        failed=failed,
        total_time_ms=total_time,
    )


@router.get("/document-types")
async def get_document_types():
    """📋 Get all supported document types."""
    return {
        "types": [{"value": dt.value, "name": dt.name} for dt in DocumentType],
        "categories": [{"value": dc.value, "name": dc.name} for dc in DocumentCategory],
    }


@router.get("/entity-types")
async def get_entity_types():
    """🏷️ Get all entity types the engine can extract."""
    return {
        "entity_types": [{"value": et.value, "name": et.name} for et in EntityType],
    }


@router.get("/health")
async def recognition_health():
    """💚 Health check for the recognition engine."""
    return {
        "status": "healthy",
        "engine": "DocumentRecognitionEngine",
        "version": "2.0.0",
        "capabilities": [
            "multi_pass_analysis",
            "legal_issue_detection",
            "entity_extraction",
            "relationship_mapping",
            "confidence_scoring",
            "minnesota_law_expertise",
            "handwriting_recognition",
            "signature_verification",
            "forgery_detection",
        ],
        "ready": True,
    }
