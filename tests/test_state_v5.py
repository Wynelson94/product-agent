"""Tests for v5.0 state management features."""

import pytest

from agent.state import (
    Phase,
    ReviewStatus,
    AgentState,
    create_initial_state,
    get_next_phase,
)


class TestPhaseVerify:
    """Tests for the new VERIFY phase."""

    def test_verify_phase_exists(self):
        """Test that VERIFY phase is defined."""
        assert Phase.VERIFY.value == "verify"

    def test_deploy_transitions_to_verify(self):
        """Test that DEPLOY transitions to VERIFY."""
        next_phase = get_next_phase(Phase.DEPLOY)
        assert next_phase == Phase.VERIFY

    def test_verify_transitions_to_complete(self):
        """Test that VERIFY transitions to COMPLETE."""
        next_phase = get_next_phase(Phase.VERIFY)
        assert next_phase == Phase.COMPLETE

    def test_phase_order(self):
        """Test the full phase order."""
        phases = [
            Phase.INIT,
            Phase.ANALYSIS,
            Phase.DESIGN,
            Phase.BUILD,
            Phase.DEPLOY,
            Phase.VERIFY,
            Phase.COMPLETE,
        ]
        for i, phase in enumerate(phases[:-1]):
            if phase == Phase.DESIGN:
                # Design can go to either REVIEW or DESIGN
                continue
            next_phase = get_next_phase(phase)
            if phase == Phase.INIT:
                assert next_phase == Phase.ANALYSIS
            elif phase == Phase.ANALYSIS:
                assert next_phase == Phase.DESIGN


class TestAgentStateV5Fields:
    """Tests for new v5.0 state fields."""

    def test_has_deployment_target_field(self):
        """Test that deployment_target field exists."""
        state = AgentState()
        assert hasattr(state, 'deployment_target')
        assert state.deployment_target is None

    def test_has_database_type_field(self):
        """Test that database_type field exists."""
        state = AgentState()
        assert hasattr(state, 'database_type')
        assert state.database_type is None

    def test_has_verification_results_field(self):
        """Test that verification_results field exists."""
        state = AgentState()
        assert hasattr(state, 'verification_results')
        assert state.verification_results == {}

    def test_has_verification_attempts_field(self):
        """Test that verification_attempts field exists."""
        state = AgentState()
        assert hasattr(state, 'verification_attempts')
        assert state.verification_attempts == 0

    def test_set_deployment_fields(self):
        """Test setting deployment fields."""
        state = AgentState()
        state.deployment_target = "vercel"
        state.database_type = "postgresql"
        assert state.deployment_target == "vercel"
        assert state.database_type == "postgresql"


class TestMarkVerified:
    """Tests for the mark_verified method."""

    def test_mark_verified_sets_flag(self):
        """Test that mark_verified sets deployment_verified."""
        state = AgentState()
        state.phase = Phase.DEPLOY
        state.mark_verified({"status": "PASSED"})
        assert state.deployment_verified is True

    def test_mark_verified_stores_results(self):
        """Test that mark_verified stores results."""
        state = AgentState()
        state.phase = Phase.DEPLOY
        results = {"status": "PASSED", "tests": 5}
        state.mark_verified(results)
        assert state.verification_results["status"] == "PASSED"
        assert state.verification_results["tests"] == 5

    def test_mark_verified_transitions_phase(self):
        """Test that mark_verified transitions to VERIFY phase."""
        state = AgentState()
        state.phase = Phase.DEPLOY
        state.mark_verified({"status": "PASSED"})
        assert state.phase == Phase.VERIFY


class TestMarkVerificationFailed:
    """Tests for the mark_verification_failed method."""

    def test_mark_failed_clears_verified(self):
        """Test that mark_verification_failed clears flag."""
        state = AgentState()
        state.deployment_verified = True
        state.mark_verification_failed({"status": "FAILED"})
        assert state.deployment_verified is False

    def test_mark_failed_increments_attempts(self):
        """Test that mark_verification_failed increments attempts."""
        state = AgentState()
        state.mark_verification_failed({"status": "FAILED"})
        assert state.verification_attempts == 1
        state.mark_verification_failed({"status": "FAILED"})
        assert state.verification_attempts == 2

    def test_mark_failed_stores_results(self):
        """Test that mark_verification_failed stores results."""
        state = AgentState()
        results = {"status": "FAILED", "error": "Auth broken"}
        state.mark_verification_failed(results)
        assert state.verification_results["status"] == "FAILED"


class TestCanRetryVerification:
    """Tests for the can_retry_verification method."""

    def test_can_retry_when_zero_attempts(self):
        """Test that retry is allowed with zero attempts."""
        state = AgentState()
        assert state.can_retry_verification() is True

    def test_can_retry_when_one_attempt(self):
        """Test that retry is allowed with one attempt."""
        state = AgentState()
        state.verification_attempts = 1
        assert state.can_retry_verification() is True

    def test_cannot_retry_when_max_attempts(self):
        """Test that retry is blocked at max attempts."""
        state = AgentState()
        state.verification_attempts = 2
        assert state.can_retry_verification(max_attempts=2) is False

    def test_custom_max_attempts(self):
        """Test custom max attempts."""
        state = AgentState()
        state.verification_attempts = 3
        assert state.can_retry_verification(max_attempts=5) is True
        assert state.can_retry_verification(max_attempts=3) is False


class TestStateSerialization:
    """Tests for serializing v5.0 state fields."""

    def test_to_dict_includes_v5_fields(self):
        """Test that to_dict includes v5.0 fields."""
        state = AgentState()
        state.deployment_target = "vercel"
        state.database_type = "postgresql"
        state.verification_results = {"status": "PASSED"}
        state.verification_attempts = 1

        data = state.to_dict()
        assert data["deployment_target"] == "vercel"
        assert data["database_type"] == "postgresql"
        assert data["verification_results"]["status"] == "PASSED"
        assert data["verification_attempts"] == 1

    def test_from_dict_loads_v5_fields(self):
        """Test that from_dict loads v5.0 fields."""
        data = {
            "phase": "deploy",
            "deployment_target": "railway",
            "database_type": "sqlite",
            "verification_results": {"status": "PARTIAL"},
            "verification_attempts": 2,
        }
        state = AgentState.from_dict(data)
        assert state.deployment_target == "railway"
        assert state.database_type == "sqlite"
        assert state.verification_results["status"] == "PARTIAL"
        assert state.verification_attempts == 2

    def test_from_dict_handles_missing_v5_fields(self):
        """Test that from_dict handles missing v5.0 fields (backwards compat)."""
        data = {
            "phase": "build",
            "idea": "test app",
        }
        state = AgentState.from_dict(data)
        assert state.deployment_target is None
        assert state.database_type is None
        assert state.verification_results == {}
        assert state.verification_attempts == 0


class TestStackCriteriaIntegration:
    """Tests for stack criteria v5.0 fields."""

    def test_stack_has_deployment_type(self):
        """Test that stacks have deployment_type field."""
        from agent.stacks.criteria import STACKS
        for stack in STACKS.values():
            assert hasattr(stack, 'deployment_type')
            assert stack.deployment_type in ["serverless", "traditional", "mobile"]

    def test_stack_has_incompatible_databases(self):
        """Test that stacks have incompatible_databases field."""
        from agent.stacks.criteria import STACKS
        for stack in STACKS.values():
            assert hasattr(stack, 'incompatible_databases')
            assert isinstance(stack.incompatible_databases, list)

    def test_vercel_stacks_block_sqlite(self):
        """Test that Vercel stacks block SQLite."""
        from agent.stacks.criteria import STACKS
        vercel_stacks = [s for s in STACKS.values() if s.deployment == "vercel"]
        for stack in vercel_stacks:
            assert "sqlite" in stack.incompatible_databases

    def test_check_compatibility_function(self):
        """Test the check_stack_deployment_compatibility function."""
        from agent.stacks.criteria import check_stack_deployment_compatibility

        # SQLite + Vercel should fail
        compatible, error = check_stack_deployment_compatibility(
            "nextjs-prisma", "vercel", "sqlite"
        )
        assert compatible is False
        assert error is not None

        # PostgreSQL + Vercel should pass
        compatible, error = check_stack_deployment_compatibility(
            "nextjs-supabase", "vercel", "postgresql"
        )
        assert compatible is True
        assert error is None
