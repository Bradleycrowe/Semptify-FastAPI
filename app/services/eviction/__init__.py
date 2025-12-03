"""
Eviction Defense Services

This module provides:
- i18n: Multi-language support (English, Spanish, Somali, Arabic)
- pdf: Court form PDF generation
- case_builder: Unified case builder that pulls from all Semptify data
- court_learning: Bidirectional learning engine - outcomes improve future strategies
- court_procedures: Rules, motions, objections, and procedure guides
"""

from .i18n import get_string, get_all_strings, get_supported_languages, is_rtl
from .pdf import (
    generate_answer_pdf,
    generate_counterclaim_pdf,
    generate_motion_pdf,
    generate_hearing_prep_pdf
)
from .case_builder import (
    EvictionCaseBuilder,
    EvictionCase,
    ComplianceReport,
    ComplianceStatus,
    MNCourtRules,
    get_case_builder,
)
from .court_learning import (
    CourtLearningEngine,
    CaseOutcome,
    DefenseEffectiveness,
    MotionOutcome,
    get_learning_engine,
)
from .court_procedures import (
    CourtProceduresEngine,
    MotionType,
    ObjectionType,
    ProcedurePhase,
    DefenseCategory,
    get_procedures_engine,
)

__all__ = [
    # i18n
    "get_string",
    "get_all_strings",
    "get_supported_languages",
    "is_rtl",
    # pdf
    "generate_answer_pdf",
    "generate_counterclaim_pdf",
    "generate_motion_pdf",
    "generate_hearing_prep_pdf",
    # case_builder
    "EvictionCaseBuilder",
    "EvictionCase",
    "ComplianceReport",
    "ComplianceStatus",
    "MNCourtRules",
    "get_case_builder",
    # court_learning
    "CourtLearningEngine",
    "CaseOutcome",
    "DefenseEffectiveness",
    "MotionOutcome",
    "get_learning_engine",
    # court_procedures
    "CourtProceduresEngine",
    "MotionType",
    "ObjectionType",
    "ProcedurePhase",
    "DefenseCategory",
    "get_procedures_engine",
]