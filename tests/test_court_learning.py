"""
Tests for the Court Learning Engine.

The learning engine enables bidirectional information flow:
- FROM court: Record case outcomes, defense effectiveness, motion results
- TO court: Data-driven strategy recommendations
"""

import pytest
from httpx import AsyncClient


class TestLearningEndpoints:
    """Test the learning API endpoints."""
    
    @pytest.mark.anyio
    async def test_defense_rates_public(self, client: AsyncClient):
        """Defense success rates should be publicly accessible."""
        response = await client.get("/eviction/learn/learn/defense-rates")
        assert response.status_code == 200
        data = response.json()
        assert "county" in data
        assert "defense_rates" in data
        assert data["county"] == "Dakota"
    
    @pytest.mark.anyio
    async def test_judge_patterns_public(self, client: AsyncClient):
        """Judge patterns should be publicly accessible."""
        response = await client.get("/eviction/learn/learn/judge-patterns")
        assert response.status_code == 200
        data = response.json()
        assert "county" in data
        assert "judges" in data
    
    @pytest.mark.anyio
    async def test_landlord_patterns_public(self, client: AsyncClient):
        """Landlord patterns should be publicly accessible."""
        response = await client.get("/eviction/learn/learn/landlord-patterns")
        assert response.status_code == 200
        data = response.json()
        assert "landlords" in data
    
    @pytest.mark.anyio
    async def test_learning_stats_public(self, client: AsyncClient):
        """Learning stats should be publicly accessible."""
        response = await client.get("/eviction/learn/learn/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_cases" in data
        assert "total_defense_outcomes" in data
    
    @pytest.mark.anyio
    async def test_strategy_recommendation(self, client: AsyncClient):
        """Strategy recommendation endpoint should work."""
        response = await client.post(
            "/eviction/learn/strategy/recommend",
            json={
                "notice_type": "14-day",
                "amount_claimed_cents": 250000,
                "available_defenses": ["improper_notice", "habitability", "payment"],
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "recommendation" in data
        assert "disclaimer" in data


class TestLearningEngine:
    """Test the CourtLearningEngine directly."""
    
    def test_case_outcome_enum(self):
        """CaseOutcome enum should have expected values."""
        from app.services.eviction.court_learning import CaseOutcome
        
        values = [e.value for e in CaseOutcome]
        assert "won" in values
        assert "lost" in values
        assert "settled" in values
        assert "dismissed" in values
        assert "pending" in values
    
    def test_defense_effectiveness_enum(self):
        """DefenseEffectiveness enum should have expected values."""
        from app.services.eviction.court_learning import DefenseEffectiveness
        
        values = [e.value for e in DefenseEffectiveness]
        assert "highly_effective" in values
        assert "effective" in values
        assert "ineffective" in values
    
    def test_motion_outcome_enum(self):
        """MotionOutcome enum should have expected values."""
        from app.services.eviction.court_learning import MotionOutcome
        
        values = [e.value for e in MotionOutcome]
        assert "granted" in values
        assert "denied" in values
        assert "partially_granted" in values
    
    @pytest.mark.anyio
    async def test_record_case_outcome(self):
        """Should be able to record a case outcome."""
        from app.services.eviction.court_learning import (
            CourtLearningEngine,
            CaseOutcome,
        )
        
        engine = CourtLearningEngine()
        
        record = await engine.record_case_outcome(
            user_id="test_user_123",
            case_number="19-CV-25-1234",
            outcome=CaseOutcome.WON,
            defenses_used=["improper_notice", "habitability"],
            primary_defense="improper_notice",
            notice_type="14-day",
            amount_claimed_cents=250000,
            judge_name="Judge Smith",
        )
        
        assert record.id is not None
        assert record.user_id == "test_user_123"
        assert record.case_number == "19-CV-25-1234"
        assert record.outcome == CaseOutcome.WON
        assert "improper_notice" in record.defenses_used
    
    @pytest.mark.anyio
    async def test_get_defense_success_rates(self):
        """Should calculate defense success rates."""
        from app.services.eviction.court_learning import (
            CourtLearningEngine,
            CaseOutcome,
        )
        
        # Create fresh engine instance for isolation
        engine = CourtLearningEngine()
        engine._case_outcomes = []  # Clear any shared state
        
        # Record some test outcomes
        for i in range(5):
            await engine.record_case_outcome(
                user_id="test",
                case_number=f"case-win-{i}",
                outcome=CaseOutcome.WON,
                defenses_used=["test_habitability"],
                county="Dakota",
            )
        
        for i in range(3):
            await engine.record_case_outcome(
                user_id="test",
                case_number=f"case-loss-{i}",
                outcome=CaseOutcome.LOST,
                defenses_used=["test_habitability"],
                county="Dakota",
            )
        
        rates = await engine.get_defense_success_rates("Dakota", min_cases=3)
        
        # Should have at least one defense with rates
        assert len(rates) > 0
        
        # Find our test defense
        hab_rate = next((r for r in rates if r.defense_code == "test_habitability"), None)
        assert hab_rate is not None
        assert hab_rate.total_uses == 8
        assert hab_rate.wins == 5
        assert hab_rate.losses == 3
    
    @pytest.mark.anyio
    async def test_get_recommended_strategy(self):
        """Should generate strategy recommendations."""
        from app.services.eviction.court_learning import CourtLearningEngine
        
        engine = CourtLearningEngine()
        
        recommendation = await engine.get_recommended_strategy(
            notice_type="14-day",
            amount_claimed_cents=200000,
            available_defenses=["improper_notice", "habitability", "payment"],
        )
        
        assert "primary_defense" in recommendation
        assert "secondary_defenses" in recommendation
        assert "motions_to_consider" in recommendation
        assert "notes" in recommendation


class TestBidirectionalFlow:
    """Test the full bidirectional learning flow."""
    
    @pytest.mark.anyio
    async def test_learn_and_recommend_cycle(self):
        """
        Full cycle test:
        1. Record multiple case outcomes
        2. Query success rates
        3. Get recommendations based on learned data
        """
        from app.services.eviction.court_learning import (
            CourtLearningEngine,
            CaseOutcome,
        )
        
        engine = CourtLearningEngine()
        
        # Simulate historical data: habitability works well, payment doesn't
        for i in range(10):
            await engine.record_case_outcome(
                user_id=f"tenant_{i}",
                case_number=f"19-CV-25-{1000+i}",
                outcome=CaseOutcome.WON if i < 7 else CaseOutcome.LOST,
                defenses_used=["habitability"],
                primary_defense="habitability",
                county="Dakota",
            )
        
        for i in range(10):
            await engine.record_case_outcome(
                user_id=f"tenant_{10+i}",
                case_number=f"19-CV-25-{2000+i}",
                outcome=CaseOutcome.WON if i < 2 else CaseOutcome.LOST,
                defenses_used=["payment"],
                primary_defense="payment",
                county="Dakota",
            )
        
        # Get success rates
        rates = await engine.get_defense_success_rates("Dakota", min_cases=5)
        
        hab = next((r for r in rates if r.defense_code == "habitability"), None)
        pay = next((r for r in rates if r.defense_code == "payment"), None)
        
        assert hab is not None
        assert pay is not None
        assert hab.win_rate > pay.win_rate  # Habitability should rank higher
        
        # Get recommendation for new case
        rec = await engine.get_recommended_strategy(
            notice_type="14-day",
            amount_claimed_cents=150000,
            available_defenses=["habitability", "payment"],
        )
        
        # Should recommend habitability over payment based on learned rates
        assert rec["primary_defense"] == "habitability"
