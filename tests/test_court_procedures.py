"""
Tests for Court Procedures, Rules, Motions & Objections API.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.eviction.court_procedures import (
    CourtProceduresEngine,
    get_procedures_engine,
    MotionType,
    ObjectionType,
    ProcedurePhase,
    DefenseCategory,
)


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def engine():
    """Get procedures engine."""
    return get_procedures_engine()


# =============================================================================
# ENGINE TESTS
# =============================================================================

class TestProceduresEngine:
    """Test the CourtProceduresEngine directly."""

    def test_engine_singleton(self, engine):
        """Engine is a singleton."""
        engine2 = get_procedures_engine()
        assert engine is engine2

    def test_rules_loaded(self, engine):
        """Rules are loaded."""
        rules = engine.get_all_rules()
        assert len(rules) > 0
        assert any(r.rule_id == "notice_14_day" for r in rules)

    def test_get_specific_rule(self, engine):
        """Can get a specific rule."""
        rule = engine.get_rule("notice_14_day")
        assert rule is not None
        assert rule.deadline_days == 14
        assert "504B.135" in rule.statute

    def test_motions_loaded(self, engine):
        """Motion templates are loaded."""
        motions = engine.get_all_motions()
        assert len(motions) > 0
        assert any(m.motion_type == MotionType.DISMISS_IMPROPER_SERVICE for m in motions)

    def test_objections_loaded(self, engine):
        """Objection responses are loaded."""
        objections = engine.get_all_objection_responses()
        assert len(objections) > 0
        assert any(o.objection_type == ObjectionType.HEARSAY for o in objections)

    def test_procedures_loaded(self, engine):
        """Procedure steps are loaded."""
        steps = engine.get_procedure_steps()
        assert len(steps) > 0
        # Steps should be in order
        for i, step in enumerate(steps):
            assert step.step_number == i + 1

    def test_counterclaims_loaded(self, engine):
        """Counterclaim types are loaded."""
        counterclaims = engine.get_counterclaim_types()
        assert len(counterclaims) > 0
        assert any(c.code == "breach_habitability" for c in counterclaims)

    def test_defenses_loaded(self, engine):
        """Defense strategies are loaded."""
        defenses = engine.get_defense_strategies()
        assert DefenseCategory.PROCEDURAL in defenses
        assert DefenseCategory.HABITABILITY in defenses

    def test_generate_motion(self, engine):
        """Can generate a motion document."""
        motion = engine.generate_motion(
            motion_type=MotionType.DISMISS_IMPROPER_SERVICE,
            tenant_name="John Doe",
            case_number="27-CV-24-12345",
            facts={"landlord_name": "ABC Properties"}
        )
        assert "John Doe" in motion
        assert "27-CV-24-12345" in motion
        assert "MOTION TO DISMISS" in motion

    def test_hearing_checklist(self, engine):
        """Can get hearing checklist."""
        checklist = engine.get_hearing_checklist()
        assert "before_hearing" in checklist
        assert "bring_to_court" in checklist
        assert "during_hearing" in checklist

    def test_rules_by_phase(self, engine):
        """Can filter rules by phase."""
        pre_filing_rules = engine.get_rules_by_phase(ProcedurePhase.PRE_FILING)
        assert len(pre_filing_rules) > 0
        assert all(ProcedurePhase.PRE_FILING in r.applies_to for r in pre_filing_rules)


# =============================================================================
# API ENDPOINT TESTS
# =============================================================================

class TestRulesEndpoints:
    """Test rules API endpoints."""

    def test_get_all_rules(self, client):
        """GET /dakota/procedures/rules returns rules."""
        response = client.get("/dakota/procedures/rules")
        assert response.status_code == 200
        rules = response.json()
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_get_specific_rule(self, client):
        """GET /dakota/procedures/rules/{rule_id} returns specific rule."""
        response = client.get("/dakota/procedures/rules/notice_14_day")
        assert response.status_code == 200
        rule = response.json()
        assert rule["rule_id"] == "notice_14_day"
        assert rule["deadline_days"] == 14

    def test_get_invalid_rule(self, client):
        """GET invalid rule returns 404."""
        response = client.get("/dakota/procedures/rules/nonexistent")
        assert response.status_code == 404

    def test_get_rules_by_phase(self, client):
        """GET /dakota/procedures/rules/phase/{phase} filters by phase."""
        response = client.get("/dakota/procedures/rules/phase/pre_filing")
        assert response.status_code == 200
        rules = response.json()
        assert all("pre_filing" in r["applies_to"] for r in rules)


class TestMotionsEndpoints:
    """Test motions API endpoints."""

    def test_get_all_motions(self, client):
        """GET /dakota/procedures/motions returns motions."""
        response = client.get("/dakota/procedures/motions")
        assert response.status_code == 200
        motions = response.json()
        assert isinstance(motions, list)
        assert len(motions) > 0

    def test_get_specific_motion(self, client):
        """GET /dakota/procedures/motions/{type} returns specific motion."""
        response = client.get("/dakota/procedures/motions/dismiss_improper_service")
        assert response.status_code == 200
        motion = response.json()
        assert motion["motion_type"] == "dismiss_improper_service"
        assert "legal_basis" in motion

    def test_generate_motion(self, client):
        """POST /dakota/procedures/motions/generate creates motion."""
        response = client.post(
            "/dakota/procedures/motions/generate",
            json={
                "motion_type": "dismiss_improper_service",
                "tenant_name": "Jane Smith",
                "case_number": "27-CV-24-99999",
                "landlord_name": "Bad Landlord LLC"
            }
        )
        assert response.status_code == 200
        result = response.json()
        assert "Jane Smith" in result["generated_motion"]
        assert "27-CV-24-99999" in result["generated_motion"]


class TestObjectionsEndpoints:
    """Test objections API endpoints."""

    def test_get_all_objections(self, client):
        """GET /dakota/procedures/objections returns objections."""
        response = client.get("/dakota/procedures/objections")
        assert response.status_code == 200
        objections = response.json()
        assert isinstance(objections, list)
        assert len(objections) > 0

    def test_get_specific_objection(self, client):
        """GET /dakota/procedures/objections/{type} returns specific objection."""
        response = client.get("/dakota/procedures/objections/hearsay")
        assert response.status_code == 200
        obj = response.json()
        assert obj["objection_type"] == "hearsay"
        assert "how_to_overcome" in obj

    def test_hearsay_response_complete(self, client):
        """Hearsay response has complete guidance."""
        response = client.get("/dakota/procedures/objections/hearsay")
        assert response.status_code == 200
        obj = response.json()
        assert len(obj["how_to_overcome"]) > 0
        assert obj["example_response"]
        assert "801" in obj["supporting_rule"]  # Evidence Rule 801


class TestProceduresEndpoints:
    """Test procedures/steps API endpoints."""

    def test_get_all_steps(self, client):
        """GET /dakota/procedures/steps returns all steps."""
        response = client.get("/dakota/procedures/steps")
        assert response.status_code == 200
        steps = response.json()
        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_get_steps_by_phase(self, client):
        """GET /dakota/procedures/steps?phase=hearing filters by phase."""
        response = client.get("/dakota/procedures/steps?phase=hearing")
        assert response.status_code == 200
        steps = response.json()
        assert all(s["phase"] == "hearing" for s in steps)


class TestCounterclaimsEndpoints:
    """Test counterclaims API endpoints."""

    def test_get_all_counterclaims(self, client):
        """GET /dakota/procedures/counterclaims returns counterclaims."""
        response = client.get("/dakota/procedures/counterclaims")
        assert response.status_code == 200
        claims = response.json()
        assert isinstance(claims, list)
        assert len(claims) > 0

    def test_get_specific_counterclaim(self, client):
        """GET /dakota/procedures/counterclaims/{code} returns specific counterclaim."""
        response = client.get("/dakota/procedures/counterclaims/breach_habitability")
        assert response.status_code == 200
        claim = response.json()
        assert claim["code"] == "breach_habitability"
        assert "504B.161" in claim["legal_basis"]

    def test_counterclaim_has_elements(self, client):
        """Counterclaim includes elements to prove."""
        response = client.get("/dakota/procedures/counterclaims/retaliation")
        assert response.status_code == 200
        claim = response.json()
        assert len(claim["elements_to_prove"]) > 0
        assert len(claim["damages_available"]) > 0
        assert len(claim["evidence_needed"]) > 0


class TestDefensesEndpoints:
    """Test defenses API endpoints."""

    def test_get_all_defenses(self, client):
        """GET /dakota/procedures/defenses returns all defense categories."""
        response = client.get("/dakota/procedures/defenses")
        assert response.status_code == 200
        defenses = response.json()
        assert "procedural" in defenses
        assert "habitability" in defenses

    def test_get_defense_category(self, client):
        """GET /dakota/procedures/defenses/{category} returns specific category."""
        response = client.get("/dakota/procedures/defenses/procedural")
        assert response.status_code == 200
        defense = response.json()
        assert defense["name"] == "Procedural Defenses"
        assert len(defense["defenses"]) > 0


class TestHearingChecklist:
    """Test hearing checklist endpoint."""

    def test_get_hearing_checklist(self, client):
        """GET /dakota/procedures/hearing-checklist returns checklist."""
        response = client.get("/dakota/procedures/hearing-checklist")
        assert response.status_code == 200
        checklist = response.json()
        assert "before_hearing" in checklist
        assert "bring_to_court" in checklist
        assert "during_hearing" in checklist
        assert "what_to_say" in checklist
        assert "after_hearing" in checklist


class TestQuickReference:
    """Test quick reference endpoint."""

    def test_get_quick_reference(self, client):
        """GET /dakota/procedures/quick-reference returns reference guide."""
        response = client.get("/dakota/procedures/quick-reference")
        assert response.status_code == 200
        ref = response.json()
        assert "critical_deadlines" in ref
        assert "common_dismissal_grounds" in ref
        assert "key_statutes" in ref
        assert "emergency_contacts" in ref


class TestEnumsEndpoints:
    """Test enum value endpoints (for frontend)."""

    def test_get_motion_types(self, client):
        """GET /dakota/procedures/enums/motion-types returns all motion types."""
        response = client.get("/dakota/procedures/enums/motion-types")
        assert response.status_code == 200
        types = response.json()
        assert len(types) > 0
        assert any(t["value"] == "dismiss_improper_service" for t in types)

    def test_get_objection_types(self, client):
        """GET /dakota/procedures/enums/objection-types returns all objection types."""
        response = client.get("/dakota/procedures/enums/objection-types")
        assert response.status_code == 200
        types = response.json()
        assert len(types) > 0
        assert any(t["value"] == "hearsay" for t in types)

    def test_get_procedure_phases(self, client):
        """GET /dakota/procedures/enums/procedure-phases returns all phases."""
        response = client.get("/dakota/procedures/enums/procedure-phases")
        assert response.status_code == 200
        phases = response.json()
        assert len(phases) > 0
        assert any(p["value"] == "hearing" for p in phases)

    def test_get_defense_categories(self, client):
        """GET /dakota/procedures/enums/defense-categories returns all categories."""
        response = client.get("/dakota/procedures/enums/defense-categories")
        assert response.status_code == 200
        cats = response.json()
        assert len(cats) > 0
        assert any(c["value"] == "procedural" for c in cats)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestProceduresIntegration:
    """Integration tests for procedures system."""

    def test_full_defense_preparation_flow(self, client):
        """Test complete flow: rules → defenses → counterclaims → motion."""
        # 1. Check what rules apply
        rules_resp = client.get("/dakota/procedures/rules")
        assert rules_resp.status_code == 200
        rules = rules_resp.json()
        
        # 2. Get available defenses
        defenses_resp = client.get("/dakota/procedures/defenses/procedural")
        assert defenses_resp.status_code == 200
        defenses = defenses_resp.json()
        
        # 3. Identify applicable counterclaim
        counterclaim_resp = client.get("/dakota/procedures/counterclaims/breach_habitability")
        assert counterclaim_resp.status_code == 200
        counterclaim = counterclaim_resp.json()
        
        # 4. Generate motion
        motion_resp = client.post(
            "/dakota/procedures/motions/generate",
            json={
                "motion_type": "dismiss_defective_notice",
                "tenant_name": "Test Tenant",
                "case_number": "27-CV-24-00001"
            }
        )
        assert motion_resp.status_code == 200
        motion = motion_resp.json()
        
        # 5. Get hearing checklist
        checklist_resp = client.get("/dakota/procedures/hearing-checklist")
        assert checklist_resp.status_code == 200
        
        # All steps completed successfully
        assert len(rules) > 0
        assert len(defenses["defenses"]) > 0
        assert counterclaim["code"] == "breach_habitability"
        assert "Test Tenant" in motion["generated_motion"]

    def test_objection_handling_knowledge(self, client):
        """Test that all objections have complete handling guidance."""
        response = client.get("/dakota/procedures/objections")
        assert response.status_code == 200
        objections = response.json()
        
        for obj in objections:
            # Each objection should have complete guidance
            assert obj["definition"], f"{obj['objection_type']} missing definition"
            assert obj["when_valid"], f"{obj['objection_type']} missing when_valid"
            assert len(obj["how_to_overcome"]) > 0, f"{obj['objection_type']} missing how_to_overcome"
            assert obj["example_response"], f"{obj['objection_type']} missing example_response"
            assert obj["supporting_rule"], f"{obj['objection_type']} missing supporting_rule"
