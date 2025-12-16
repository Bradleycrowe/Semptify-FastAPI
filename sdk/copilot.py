"""
Semptify SDK - Copilot Client

Handles AI assistant interactions, case analysis, and recommendations.
"""

from typing import Optional, Dict, Any, List, AsyncIterator
from dataclasses import dataclass
from enum import Enum

from .base import BaseClient


class ConversationType(str, Enum):
    """Types of copilot conversations."""
    GENERAL = "general"
    DOCUMENT_ANALYSIS = "document_analysis"
    CASE_STRATEGY = "case_strategy"
    LEGAL_RESEARCH = "legal_research"
    COMPLAINT_DRAFT = "complaint_draft"
    LETTER_DRAFT = "letter_draft"


@dataclass
class Message:
    """Conversation message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Conversation:
    """Copilot conversation."""
    id: str
    conversation_type: str
    title: Optional[str] = None
    messages: List[Message] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = []


@dataclass
class CaseAnalysis:
    """AI-generated case analysis."""
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    legal_theories: List[str]
    evidence_gaps: List[str]
    estimated_strength: float  # 0.0 to 1.0
    next_steps: List[Dict[str, Any]]


@dataclass
class DraftResponse:
    """AI-generated draft document."""
    draft_type: str
    content: str
    sections: List[Dict[str, str]]
    citations: List[str]
    warnings: List[str]


class CopilotClient(BaseClient):
    """Client for AI copilot interactions."""
    
    def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        conversation_type: ConversationType = ConversationType.GENERAL,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a message to the copilot and get a response.
        
        Args:
            message: User message
            conversation_id: Existing conversation ID to continue
            conversation_type: Type of conversation
            context: Additional context (documents, case info, etc.)
            
        Returns:
            Response with assistant message and conversation details
        """
        data = {
            "message": message,
            "conversation_type": conversation_type.value if isinstance(conversation_type, ConversationType) else conversation_type,
        }
        
        if conversation_id:
            data["conversation_id"] = conversation_id
        if context:
            data["context"] = context
        
        return self.post("/api/copilot/chat", json=data)
    
    def analyze_case(
        self,
        include_documents: bool = True,
        include_timeline: bool = True,
        focus_areas: Optional[List[str]] = None,
    ) -> CaseAnalysis:
        """
        Get a comprehensive AI analysis of the current case.
        
        Args:
            include_documents: Include document analysis
            include_timeline: Include timeline analysis
            focus_areas: Specific areas to focus on
            
        Returns:
            Case analysis with strengths, weaknesses, and recommendations
        """
        data = {
            "include_documents": include_documents,
            "include_timeline": include_timeline,
        }
        if focus_areas:
            data["focus_areas"] = focus_areas
        
        response = self.post("/api/copilot/analyze/case", json=data)
        
        return CaseAnalysis(
            summary=response.get("summary", ""),
            strengths=response.get("strengths", []),
            weaknesses=response.get("weaknesses", []),
            recommendations=response.get("recommendations", []),
            legal_theories=response.get("legal_theories", []),
            evidence_gaps=response.get("evidence_gaps", []),
            estimated_strength=response.get("estimated_strength", 0.5),
            next_steps=response.get("next_steps", []),
        )
    
    def analyze_document(
        self,
        document_id: str,
        analysis_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """
        Analyze a specific document with AI.
        
        Args:
            document_id: The document ID to analyze
            analysis_type: Type of analysis (comprehensive, summary, key_dates, violations)
            
        Returns:
            Document analysis results
        """
        return self.post(
            "/api/copilot/analyze/document",
            json={"document_id": document_id, "analysis_type": analysis_type},
        )
    
    def draft_letter(
        self,
        letter_type: str,
        recipient: str,
        key_points: List[str],
        tone: str = "professional",
        include_citations: bool = True,
    ) -> DraftResponse:
        """
        Draft a letter using AI assistance.
        
        Args:
            letter_type: Type of letter (demand, complaint_to_landlord, repair_request, etc.)
            recipient: Letter recipient description
            key_points: Key points to include
            tone: Letter tone (professional, firm, urgent)
            include_citations: Include legal citations
            
        Returns:
            Drafted letter content
        """
        data = {
            "letter_type": letter_type,
            "recipient": recipient,
            "key_points": key_points,
            "tone": tone,
            "include_citations": include_citations,
        }
        
        response = self.post("/api/copilot/draft/letter", json=data)
        
        return DraftResponse(
            draft_type="letter",
            content=response.get("content", ""),
            sections=response.get("sections", []),
            citations=response.get("citations", []),
            warnings=response.get("warnings", []),
        )
    
    def draft_complaint_section(
        self,
        section_type: str,
        facts: List[str],
        legal_basis: Optional[str] = None,
    ) -> DraftResponse:
        """
        Draft a section of a legal complaint.
        
        Args:
            section_type: Section type (allegations, prayer_for_relief, causes_of_action)
            facts: Relevant facts to include
            legal_basis: Legal basis for the section
            
        Returns:
            Drafted complaint section
        """
        data = {
            "section_type": section_type,
            "facts": facts,
        }
        if legal_basis:
            data["legal_basis"] = legal_basis
        
        response = self.post("/api/copilot/draft/complaint-section", json=data)
        
        return DraftResponse(
            draft_type="complaint_section",
            content=response.get("content", ""),
            sections=response.get("sections", []),
            citations=response.get("citations", []),
            warnings=response.get("warnings", []),
        )
    
    def get_recommendations(
        self,
        context: str = "general",
        urgency: str = "normal",
    ) -> List[Dict[str, Any]]:
        """
        Get AI-powered recommendations for next steps.
        
        Args:
            context: Context for recommendations
            urgency: Urgency level (low, normal, high, critical)
            
        Returns:
            List of recommended actions
        """
        response = self.get(
            "/api/copilot/recommendations",
            params={"context": context, "urgency": urgency},
        )
        return response if isinstance(response, list) else response.get("recommendations", [])
    
    def get_conversation(self, conversation_id: str) -> Conversation:
        """
        Get a specific conversation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            Conversation with messages
        """
        response = self.get(f"/api/copilot/conversations/{conversation_id}")
        
        messages = [
            Message(
                role=msg.get("role", ""),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp"),
                metadata=msg.get("metadata"),
            )
            for msg in response.get("messages", [])
        ]
        
        return Conversation(
            id=response.get("id", conversation_id),
            conversation_type=response.get("conversation_type", "general"),
            title=response.get("title"),
            messages=messages,
            created_at=response.get("created_at"),
            updated_at=response.get("updated_at"),
        )
    
    def list_conversations(
        self,
        conversation_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Conversation]:
        """
        List copilot conversations.
        
        Args:
            conversation_type: Filter by type
            limit: Maximum conversations to return
            
        Returns:
            List of conversations
        """
        params = {"limit": limit}
        if conversation_type:
            params["conversation_type"] = conversation_type
        
        response = self.get("/api/copilot/conversations", params=params)
        conversations = response if isinstance(response, list) else response.get("conversations", [])
        
        return [
            Conversation(
                id=conv.get("id", ""),
                conversation_type=conv.get("conversation_type", "general"),
                title=conv.get("title"),
                created_at=conv.get("created_at"),
                updated_at=conv.get("updated_at"),
            )
            for conv in conversations
        ]
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            True if deleted successfully
        """
        self.delete(f"/api/copilot/conversations/{conversation_id}")
        return True
    
    def search_legal(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        document_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search legal resources and precedents.
        
        Args:
            query: Search query
            jurisdiction: Filter by jurisdiction
            document_types: Filter by document types
            
        Returns:
            Search results with relevant legal resources
        """
        data = {"query": query}
        if jurisdiction:
            data["jurisdiction"] = jurisdiction
        if document_types:
            data["document_types"] = document_types
        
        response = self.post("/api/copilot/search/legal", json=data)
        return response if isinstance(response, list) else response.get("results", [])
