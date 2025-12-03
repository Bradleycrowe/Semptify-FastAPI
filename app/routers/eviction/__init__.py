"""
Dakota County Eviction Defense Module
Integrated into Semptify FastAPI

This module provides court-ready eviction defense tools:
- flows_router: Multi-step guided flows for Answer, Counterclaims, Motions
- forms_router: Individual form generation
- case_router: Unified case builder that pulls from all Semptify data
- learning_router: Bidirectional court learning - outcomes flow back to improve strategies
- procedures_router: Court rules, motions, objections, and step-by-step procedures
"""

from app.routers.eviction.flows import router as flows_router
from app.routers.eviction.forms import router as forms_router
from app.routers.eviction.case import router as case_router
from app.routers.eviction.learning import router as learning_router
from app.routers.eviction.procedures import router as procedures_router

__all__ = [
    "flows_router",
    "forms_router",
    "case_router",
    "learning_router",
    "procedures_router",
]
