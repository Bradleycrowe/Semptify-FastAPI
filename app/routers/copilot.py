"""
AI Copilot Router
AI assistance for tenant legal questions.
Supports multiple providers: OpenAI, Azure OpenAI, Ollama.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.security import require_user, rate_limit_dependency


router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

class CopilotRequest(BaseModel):
    """Request to the AI copilot."""
    message: str = Field(..., min_length=1, max_length=4000, description="Your question")
    context: Optional[str] = Field(None, description="Additional context (e.g., from documents)")
    conversation_id: Optional[str] = Field(None, description="Continue a conversation")


class CopilotResponse(BaseModel):
    """Response from the AI copilot."""
    response: str
    conversation_id: str
    provider: str
    disclaimer: str = (
        "This is general information, not legal advice. "
        "For specific legal situations, consult with a licensed attorney."
    )


class CopilotStatusResponse(BaseModel):
    """Status of the AI copilot service."""
    available: bool
    provider: str
    model: str


class CaseAnalysisRequest(BaseModel):
    """Request for full case analysis."""
    include_documents: bool = Field(True, description="Include documents in analysis")
    include_timeline: bool = Field(True, description="Include timeline events")
    focus_area: Optional[str] = Field(None, description="Specific area to focus on (e.g., 'notice_defects', 'habitability')")


class CaseAnalysisResponse(BaseModel):
    """Full case analysis response."""
    case_strength: float = Field(..., description="Case strength 0-100")
    key_issues: list[str] = Field(default_factory=list)
    critical_deadlines: list[dict] = Field(default_factory=list)
    defense_options: list[dict] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    provider: str
    disclaimer: str = (
        "This analysis is for informational purposes only, not legal advice. "
        "Consult a licensed attorney for your specific situation."
    )


class SuggestionRequest(BaseModel):
    """Request for suggestions."""
    category: Optional[str] = Field(None, description="Category: 'defense', 'documentation', 'response', 'preparation'")
    context: Optional[str] = Field(None, description="Additional context")


class SuggestionResponse(BaseModel):
    """Suggestions response."""
    suggestions: list[dict] = Field(default_factory=list)
    priority_action: Optional[str] = None
    provider: str


class GenerateRequest(BaseModel):
    """Request to generate a document."""
    template_type: str = Field(..., description="Type: 'response_letter', 'repair_request', 'motion', 'statement'")
    additional_context: Optional[str] = Field(None, description="Extra details to include")
    tone: str = Field("formal", description="Tone: 'formal', 'assertive', 'conciliatory'")


class GenerateResponse(BaseModel):
    """Generated document response."""
    content: str
    format: str
    template_type: str
    provider: str
    disclaimer: str = (
        "This generated document is a starting point and should be reviewed "
        "by a legal professional before use."
    )


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are Semptify Copilot, an AI assistant helping tenants understand their rights and navigate housing issues.

Your role:
- Explain tenant rights in clear, simple language
- Help users understand legal documents (leases, notices)
- Guide users through processes (filing complaints, documenting issues)
- Suggest next steps based on their situation

Important guidelines:
1. Always clarify you provide INFORMATION, not LEGAL ADVICE
2. Recommend consulting an attorney for specific legal situations
3. Be empathetic - users may be stressed about housing issues
4. Focus on practical, actionable guidance
5. When unsure, say so and suggest resources
6. Tailor responses to the user's situation when context is provided

You are knowledgeable about:
- Tenant rights (habitability, quiet enjoyment, security deposits)
- Eviction processes and defenses
- Fair housing laws and discrimination
- Lease terms and violations
- Repair requests and landlord obligations
- Small claims court procedures
"""


# =============================================================================
# AI Provider Clients (Async)
# =============================================================================

async def call_openai(message: str, context: Optional[str], settings: Settings) -> str:
    """Call OpenAI API."""
    try:
        import httpx
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if context:
            messages.append({"role": "user", "content": f"Context: {context}"})
        
        messages.append({"role": "user", "content": message})
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openai_model,
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OpenAI API error: {str(e)}",
        )


async def call_azure_openai(message: str, context: Optional[str], settings: Settings) -> str:
    """Call Azure OpenAI API."""
    try:
        import httpx
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if context:
            messages.append({"role": "user", "content": f"Context: {context}"})
        
        messages.append({"role": "user", "content": message})
        
        url = (
            f"{settings.azure_openai_endpoint}/openai/deployments/"
            f"{settings.azure_openai_deployment}/chat/completions"
            f"?api-version={settings.azure_openai_api_version}"
        )
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "api-key": settings.azure_openai_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Azure OpenAI API error: {str(e)}",
        )


async def call_ollama(message: str, context: Optional[str], settings: Settings) -> str:
    """Call local Ollama API."""
    try:
        import httpx
        
        prompt = SYSTEM_PROMPT + "\n\n"
        if context:
            prompt += f"Context: {context}\n\n"
        prompt += f"User: {message}\n\nAssistant:"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=60.0,  # Ollama can be slower
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "No response generated")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ollama API error: {str(e)}",
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/status", response_model=CopilotStatusResponse)
async def copilot_status(settings: Settings = Depends(get_settings)):
    """
    Check if AI copilot is available and which provider is configured.
    """
    provider = settings.ai_provider
    
    if provider == "none":
        return CopilotStatusResponse(
            available=False,
            provider="none",
            model="N/A",
        )
    
    model = {
        "openai": settings.openai_model,
        "azure": settings.azure_openai_deployment,
        "ollama": settings.ollama_model,
    }.get(provider, "unknown")
    
    # Check if API keys are configured
    available = False
    if provider == "openai" and settings.openai_api_key:
        available = True
    elif provider == "azure" and settings.azure_openai_api_key:
        available = True
    elif provider == "ollama":
        available = True  # Ollama doesn't need API key
    
    return CopilotStatusResponse(
        available=available,
        provider=provider,
        model=model,
    )


@router.post(
    "/",
    response_model=CopilotResponse,
    dependencies=[Depends(rate_limit_dependency("copilot", window=60, max_requests=10))],
)
async def ask_copilot(
    request: CopilotRequest,
    user: dict = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Ask the AI copilot a question about tenant rights.
    
    The copilot can help with:
    - Understanding your rights as a tenant
    - Explaining lease terms and notices
    - Guiding you through complaint processes
    - Suggesting documentation strategies
    
    **Note**: This provides information, not legal advice.
    """
    import uuid
    
    provider = settings.ai_provider
    
    if provider == "none":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI copilot is not configured. Set AI_PROVIDER environment variable.",
        )
    
    # Call the appropriate provider
    if provider == "openai":
        response_text = await call_openai(request.message, request.context, settings)
    elif provider == "azure":
        response_text = await call_azure_openai(request.message, request.context, settings)
    elif provider == "ollama":
        response_text = await call_ollama(request.message, request.context, settings)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown AI provider: {provider}",
        )
    
    # Generate or reuse conversation ID
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    return CopilotResponse(
        response=response_text,
        conversation_id=conversation_id,
        provider=provider,
    )


@router.post("/analyze-document")
async def analyze_document(
    document_id: str,
    question: Optional[str] = None,
    user: dict = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Analyze a document from the vault using AI.

    If a question is provided, answers it based on the document.
    Otherwise, provides a general summary and highlights important terms.
    """
    if settings.ai_provider == "none":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI copilot is not configured.",
        )

    # Get document from pipeline
    from app.services.document_pipeline import get_document_pipeline
    
    pipeline = get_document_pipeline()
    doc = pipeline.get_document(document_id)
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )
    
    # Build analysis prompt
    document_text = doc.full_text or doc.summary or ""
    if not document_text:
        return {
            "document_id": document_id,
            "status": "no_content",
            "message": "Document has no extracted text. Try reprocessing the document.",
        }
    
    # Create analysis prompt
    if question:
        analysis_prompt = f"""Analyze the following document and answer this question: {question}

Document Type: {doc.doc_type.value if doc.doc_type else 'unknown'}
Document Title: {doc.title or doc.filename}

Document Content:
{document_text[:8000]}  # Limit to ~8000 chars to fit in context

Please provide a clear, helpful answer based on the document content."""
    else:
        analysis_prompt = f"""Analyze the following tenant-related document and provide:
1. A brief summary (2-3 sentences)
2. Document type and purpose
3. Key dates mentioned
4. Important terms or clauses that affect tenant rights
5. Any deadlines or required actions
6. Potential concerns or red flags

Document Type: {doc.doc_type.value if doc.doc_type else 'unknown'}
Document Title: {doc.title or doc.filename}

Document Content:
{document_text[:8000]}"""

    # Call the appropriate AI provider
    provider = settings.ai_provider
    try:
        if provider == "openai":
            analysis = await call_openai(analysis_prompt, None, settings)
        elif provider == "azure":
            analysis = await call_azure_openai(analysis_prompt, None, settings)
        elif provider == "ollama":
            analysis = await call_ollama(analysis_prompt, None, settings)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unknown AI provider: {provider}",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI analysis failed: {str(e)}",
        )

    return {
        "document_id": document_id,
        "filename": doc.filename,
        "doc_type": doc.doc_type.value if doc.doc_type else None,
        "status": "analyzed",
        "analysis": analysis,
        "provider": provider,
        "disclaimer": (
            "This AI analysis is for informational purposes only and does not "
            "constitute legal advice. Consult with a licensed attorney for "
            "specific legal questions about this document."
        ),
    }


# =============================================================================
# New Endpoints: analyze, suggest, chat, generate
# =============================================================================

@router.post("/chat", response_model=CopilotResponse)
async def chat(
    request: CopilotRequest,
    user: dict = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Interactive chat with the AI copilot.
    Alias for the main '/' endpoint with clearer naming.
    """
    return await ask_copilot(request, user, settings)


@router.post("/analyze", response_model=CaseAnalysisResponse)
async def analyze_case(
    request: CaseAnalysisRequest = CaseAnalysisRequest(),
    user: dict = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Perform a comprehensive AI analysis of the entire case.
    
    Analyzes:
    - All uploaded documents
    - Timeline events
    - Current case data from FormDataHub
    - Relevant laws and defenses
    
    Returns case strength, issues, recommendations.
    """
    from app.services.form_data import get_form_data_service
    from app.services.law_engine import get_law_engine
    
    provider = settings.ai_provider
    user_id = getattr(user, 'user_id', 'open-mode-user')
    form_data_svc = get_form_data_service(user_id)
    law_engine = get_law_engine()
    
    # Gather case context using correct methods
    case_summary = form_data_svc.get_case_summary()
    case_info = {
        "case_number": case_summary.get("case_number"),
        "court": case_summary.get("court"),
        "stage": case_summary.get("stage"),
        "hearing_date": case_summary.get("hearing_date"),
        "defendant_name": case_summary.get("tenant_name"),
        "plaintiff_name": case_summary.get("landlord_name"),
        "property_address": case_summary.get("property_address"),
    }
    timeline = form_data_svc.form_data.timeline_events if form_data_svc.form_data else []
    
    # Get violations and defenses from law engine
    violations = await law_engine.find_violations(case_info, timeline)
    strategies = law_engine.get_defense_strategies(violations)
    
    # Build context for AI
    context_parts = []
    context_parts.append(f"Case Number: {case_info.get('case_number', 'Not assigned')}")
    context_parts.append(f"Court: {case_info.get('court', 'Not specified')}")
    context_parts.append(f"Stage: {case_info.get('stage', 'Unknown')}")
    
    if case_info.get('hearing_date'):
        context_parts.append(f"Hearing Date: {case_info['hearing_date']}")
        
    if violations:
        context_parts.append(f"Violations Found: {len(violations)}")
        for v in violations[:3]:
            context_parts.append(f"  - {v.get('title', 'Unknown')}: {v.get('description', '')}")
            
    if strategies:
        context_parts.append(f"Defense Strategies: {len(strategies)}")
        for s in strategies[:3]:
            context_parts.append(f"  - {s.get('title', 'Unknown')}: {s.get('strength', 'unknown')}")
    
    context = "\n".join(context_parts)
    
    # If AI is available, enhance with AI analysis
    if provider != "none":
        try:
            analysis_prompt = f"""As a legal assistant specializing in tenant rights and eviction defense, analyze this case:

{context}

Provide:
1. Overall case strength assessment (0-100 score)
2. Key legal issues that need to be addressed
3. Strengths in the tenant's position
4. Potential weaknesses or concerns
5. Recommended priority actions

Be specific and practical. Focus on Minnesota eviction law."""

            if provider == "openai":
                ai_analysis = await call_openai(analysis_prompt, None, settings)
            elif provider == "azure":
                ai_analysis = await call_azure_openai(analysis_prompt, None, settings)
            elif provider == "ollama":
                ai_analysis = await call_ollama(analysis_prompt, None, settings)
        except Exception:
            ai_analysis = None
    else:
        ai_analysis = None
    
    # Calculate case strength based on data
    strength = 30  # Base score
    if violations:
        strength += min(len(violations) * 10, 30)  # Up to 30 points for violations
    if strategies:
        strength += min(len(strategies) * 5, 20)  # Up to 20 points for strategies
    if case_info.get('case_number'):
        strength += 5
    if timeline:
        strength += min(len(timeline) * 2, 15)  # Up to 15 points for documentation
    strength = min(strength, 100)
    
    # Build response
    key_issues = []
    if not case_info.get('case_number'):
        key_issues.append("Case number not entered - check summons")
    if not timeline:
        key_issues.append("No timeline events - upload documents")
    if violations:
        key_issues.extend([v.get('title', 'Unknown violation') for v in violations])
    
    evidence_gaps = []
    if not timeline:
        evidence_gaps.append("Need to upload lease agreement")
        evidence_gaps.append("Need to upload eviction notice")
        evidence_gaps.append("Need summons and complaint")
    
    recommended = []
    if not case_info.get('case_number'):
        recommended.append("Enter case number from summons")
    recommended.append("Review detected violations")
    if strategies:
        recommended.append("Prepare Answer using recommended defense")
    recommended.append("Gather additional evidence")
    
    return CaseAnalysisResponse(
        case_strength=strength,
        key_issues=key_issues[:5],
        critical_deadlines=[{"deadline": case_info.get('hearing_date', 'Not set'), "action": "Court Hearing"}],
        defense_options=[{"code": s.get('code'), "title": s.get('title'), "strength": s.get('strength')} for s in strategies[:5]],
        evidence_gaps=evidence_gaps[:5],
        recommended_actions=recommended[:5],
        provider=provider,
    )


@router.post("/suggest", response_model=SuggestionResponse)
async def get_suggestions(
    request: SuggestionRequest = SuggestionRequest(),
    user: dict = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Get AI-powered suggestions for next steps.
    
    Categories:
    - defense: Defense strategy suggestions
    - documentation: What documents to gather
    - response: How to respond to landlord
    - preparation: Court preparation tips
    """
    from app.services.form_data import get_form_data_service
    from app.services.law_engine import get_law_engine
    
    provider = settings.ai_provider
    user_id = getattr(user, 'user_id', 'open-mode-user')
    form_data_svc = get_form_data_service(user_id)
    case_summary = form_data_svc.get_case_summary()
    case_info = {
        "case_number": case_summary.get("case_number"),
        "court": case_summary.get("court"),
        "stage": case_summary.get("stage"),
        "hearing_date": case_summary.get("hearing_date"),
    }
    category = request.category or "defense"
    
    suggestions = []
    law_engine = get_law_engine()
    
    if category == "defense":
        timeline = form_data_svc.form_data.timeline_events if form_data_svc.form_data else []
        violations = await law_engine.find_violations(case_info, timeline)
        strategies = law_engine.get_defense_strategies(violations)
        
        for s in strategies[:5]:
            suggestions.append({
                "title": s.get("title", "Defense Strategy"),
                "description": s.get("description", ""),
                "priority": "high" if s.get("strength") == "strong" else "medium",
                "action": f"File {s.get('forms_to_file', ['motion'])[0] if s.get('forms_to_file') else 'motion'}"
            })
            
    elif category == "documentation":
        suggestions = [
            {"title": "Upload Lease Agreement", "description": "Essential for identifying lease violations", "priority": "high", "action": "Upload document"},
            {"title": "Upload Eviction Notice", "description": "Review for proper notice requirements", "priority": "high", "action": "Upload document"},
            {"title": "Gather Rent Receipts", "description": "Prove payment history", "priority": "medium", "action": "Upload documents"},
            {"title": "Document Property Conditions", "description": "Photos/videos of any maintenance issues", "priority": "medium", "action": "Take photos"},
            {"title": "Save Communications", "description": "All emails/texts with landlord", "priority": "medium", "action": "Upload documents"},
        ]
        
    elif category == "response":
        suggestions = [
            {"title": "File Answer within Deadline", "description": "Respond to summons before hearing", "priority": "high", "action": "Generate Answer form"},
            {"title": "Request Time Extension", "description": "If you need more time to prepare", "priority": "medium", "action": "File Motion for Continuance"},
            {"title": "Propose Settlement", "description": "Consider negotiating with landlord", "priority": "low", "action": "Draft settlement letter"},
        ]
        
    elif category == "preparation":
        suggestions = [
            {"title": "Organize Evidence", "description": "Create a timeline and organize documents", "priority": "high", "action": "Review timeline"},
            {"title": "Test Zoom Setup", "description": "Ensure camera, mic, and internet work", "priority": "high", "action": "Run test"},
            {"title": "Prepare Opening Statement", "description": "Know what to say to the judge", "priority": "high", "action": "Practice"},
            {"title": "Review Courtroom Procedures", "description": "Understand how eviction hearings work", "priority": "medium", "action": "Read guide"},
        ]
    
    priority_action = suggestions[0]["title"] if suggestions else None
    
    return SuggestionResponse(
        suggestions=suggestions,
        priority_action=priority_action,
        provider=provider,
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate_document(
    request: GenerateRequest,
    user: dict = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Generate a document using AI.
    
    Template types:
    - response_letter: Response to landlord
    - repair_request: Formal repair demand
    - motion: Court motion
    - statement: Personal statement for court
    """
    from app.services.form_data import get_form_data_service
    
    provider = settings.ai_provider
    user_id = getattr(user, 'user_id', 'open-mode-user')
    form_data_svc = get_form_data_service(user_id)
    case_summary = form_data_svc.get_case_summary()
    case_info = {
        "case_number": case_summary.get("case_number"),
        "defendant_name": case_summary.get("tenant_name"),
        "plaintiff_name": case_summary.get("landlord_name"),
        "property_address": case_summary.get("property_address"),
    }
    
    # Build generation prompt based on template type
    template_prompts = {
        "response_letter": f"""Generate a {request.tone} letter from a tenant to their landlord responding to an eviction action.

Case: {case_info.get('case_number', '[Case Number]')}
Tenant: {case_info.get('defendant_name', '[Your Name]')}
Landlord: {case_info.get('plaintiff_name', '[Landlord Name]')}
Property: {case_info.get('property_address', '[Property Address]')}

{request.additional_context or ''}

Include:
1. Reference to the eviction notice/summons
2. State your position clearly
3. Request specific action (dismissal, negotiation, etc.)
4. Professional closing""",

        "repair_request": f"""Generate a formal repair request letter from a tenant to their landlord.

Tenant: {case_info.get('defendant_name', '[Your Name]')}
Property: {case_info.get('property_address', '[Property Address]')}

{request.additional_context or 'Issues: [List maintenance issues]'}

Include:
1. Clear description of repair issues
2. Reference to landlord's legal obligations (MN Stat. 504B.161)
3. Reasonable deadline for repairs
4. Notice of tenant's remedies if not addressed""",

        "motion": f"""Generate a court motion for an eviction case.

Case: {case_info.get('case_number', '[Case Number]')}
Court: Dakota County District Court
Defendant/Movant: {case_info.get('defendant_name', '[Your Name]')}
Plaintiff: {case_info.get('plaintiff_name', '[Landlord Name]')}

{request.additional_context or 'Motion type: Motion to Dismiss'}

Include:
1. Caption with case information
2. Clear statement of what is being requested
3. Legal grounds (cite Minnesota statutes)
4. Factual basis for the motion
5. Relief requested
6. Signature line""",

        "statement": f"""Generate a personal statement for court regarding an eviction case.

Case: {case_info.get('case_number', '[Case Number]')}
Name: {case_info.get('defendant_name', '[Your Name]')}
Property: {case_info.get('property_address', '[Property Address]')}

{request.additional_context or ''}

Include:
1. Introduction of yourself
2. Brief history of tenancy
3. Your perspective on the situation
4. Key facts supporting your position
5. What you are asking the court to do"""
    }
    
    prompt = template_prompts.get(request.template_type)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown template type: {request.template_type}. Valid types: response_letter, repair_request, motion, statement"
        )
    
    # Generate with AI or use template
    if provider != "none":
        try:
            if provider == "openai":
                content = await call_openai(prompt, None, settings)
            elif provider == "azure":
                content = await call_azure_openai(prompt, None, settings)
            elif provider == "ollama":
                content = await call_ollama(prompt, None, settings)
            else:
                content = f"[AI generation not available. Template type: {request.template_type}]"
        except Exception as e:
            content = f"[AI generation failed: {str(e)}. Please fill in manually.]"
    else:
        # Fallback template when no AI
        content = f"""[{request.template_type.upper().replace('_', ' ')} TEMPLATE]

Case: {case_info.get('case_number', '[Enter case number]')}
Date: [Today's date]

To Whom It May Concern:

[Your content here based on {request.template_type}]

{request.additional_context or '[Add your specific details]'}

Respectfully,

{case_info.get('defendant_name', '[Your Name]')}
{case_info.get('property_address', '[Your Address]')}
[Your Phone]
[Your Email]

---
Note: AI assistance is not configured. Please complete this template manually.
"""
    
    return GenerateResponse(
        content=content,
        format="markdown",
        template_type=request.template_type,
        provider=provider,
    )