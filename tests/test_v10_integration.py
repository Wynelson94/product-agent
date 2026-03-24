"""Integration tests for Product Agent v10.0 features.

Tests the end-to-end flow of v10.0 post-mortem fixes:
  - State serialization roundtrip for new fields (critical_count, build_mode, plugin_packaged)
  - Orchestrator CRITICAL count propagation through to quality scoring
  - Resume path safety (no unbound variables when phases are skipped)
  - Dependency audit surfacing in build validation
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.state import AgentState, Phase, ReviewStatus, create_initial_state
from agent.orchestrator import (
    BuildConfig,
    BuildResult,
    build_product,
    _should_skip_phase,
)
from agent.validators import ValidationResult, validate_phase_output
from agent.cli_runner import PhaseCallResult
from agent.quality import compute_quality_score


# ---------------------------------------------------------------------------
# Helpers (mirrors patterns from test_orchestrator_v8.py and test_quality.py)
# ---------------------------------------------------------------------------

def _make_call_result(
    success: bool = True,
    result_text: str = "ok",
    error: str = "",
    duration_s: float = 1.0,
    num_turns: int = 5,
    cost_usd: float = 0.02,
    session_id: str = "sess-v10",
) -> PhaseCallResult:
    return PhaseCallResult(
        success=success,
        result_text=result_text,
        error=error,
        duration_s=duration_s,
        num_turns=num_turns,
        cost_usd=cost_usd,
        session_id=session_id,
    )


def _make_validation(
    passed: bool = True,
    phase: Phase = Phase.ANALYSIS,
    messages: list[str] | None = None,
    extracted: dict | None = None,
) -> ValidationResult:
    return ValidationResult(
        passed=passed,
        phase=phase,
        messages=messages or [],
        extracted=extracted or {},
    )


def _make_state(**overrides) -> AgentState:
    state = AgentState()
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


# ---------------------------------------------------------------------------
# 1. State Serialization Roundtrip
# ---------------------------------------------------------------------------

class TestV10StateRoundtrip:
    """Verify v10.0 fields survive to_dict → from_dict serialization."""

    def test_critical_count_survives_serialization(self):
        state = _make_state(spec_audit_critical_count=3)
        restored = AgentState.from_dict(state.to_dict())
        assert restored.spec_audit_critical_count == 3

    def test_build_mode_survives_serialization(self):
        state = _make_state(build_mode="plugin")
        restored = AgentState.from_dict(state.to_dict())
        assert restored.build_mode == "plugin"

    def test_plugin_packaged_survives_serialization(self):
        state = _make_state(plugin_packaged=True)
        restored = AgentState.from_dict(state.to_dict())
        assert restored.plugin_packaged is True

    def test_full_v10_state_roundtrip(self):
        """All v10.0-relevant fields survive a JSON roundtrip."""
        state = _make_state(
            spec_audit_critical_count=5,
            build_mode="host",
            plugin_packaged=True,
            spec_audit_completed=True,
            spec_audit_discrepancies=2,
        )
        json_str = state.to_json()
        restored = AgentState.from_json(json_str)
        assert restored.spec_audit_critical_count == 5
        assert restored.build_mode == "host"
        assert restored.plugin_packaged is True
        assert restored.spec_audit_completed is True
        assert restored.spec_audit_discrepancies == 2

    def test_defaults_when_fields_absent(self):
        """from_dict with missing v10.0 keys should use safe defaults."""
        data = {"phase": "init", "idea": "test"}
        restored = AgentState.from_dict(data)
        assert restored.spec_audit_critical_count == 0
        assert restored.build_mode == "standard"
        assert restored.plugin_packaged is False


# ---------------------------------------------------------------------------
# 2. Orchestrator CRITICAL Count Flow
# ---------------------------------------------------------------------------

def _mock_run_phase_factory(
    audit_extracted: dict | None = None,
    test_extracted: dict | None = None,
    critical_count: int = 0,
):
    """Create a run_phase mock that returns phase-appropriate results.

    Returns different (PhaseCallResult, ValidationResult) based on which
    phase is being run, simulating a full pipeline.
    """
    async def mock_run_phase(phase, state, project_dir, progress, retry_context=None, timeout_override=None):
        call = _make_call_result()

        if phase == Phase.ANALYSIS:
            val = _make_validation(phase=Phase.ANALYSIS, extracted={"stack_id": "nextjs-supabase"})
        elif phase == Phase.DESIGN:
            val = _make_validation(phase=Phase.DESIGN)
        elif phase == Phase.REVIEW:
            val = _make_validation(phase=Phase.REVIEW, extracted={"approved": True})
        elif phase == Phase.BUILD:
            val = _make_validation(phase=Phase.BUILD)
        elif phase == Phase.AUDIT:
            extracted = audit_extracted or {"requirements_met": 10, "requirements_total": 10}
            if critical_count:
                extracted["critical_count"] = critical_count
            val = _make_validation(phase=Phase.AUDIT, extracted=extracted)
        elif phase == Phase.TEST:
            extracted = test_extracted or {"tests_passed": 10, "tests_total": 10, "all_passed": True}
            val = _make_validation(phase=Phase.TEST, extracted=extracted)
        elif phase == Phase.DEPLOY:
            val = _make_validation(phase=Phase.DEPLOY, extracted={"url": "https://test.vercel.app"})
        elif phase == Phase.VERIFY:
            val = _make_validation(phase=Phase.VERIFY, extracted={"verified": True})
        else:
            val = _make_validation(phase=phase)

        return call, val

    return mock_run_phase


class TestOrchestratorCriticalFlow:
    """Verify CRITICAL count flows from audit → state → quality scoring."""

    @patch("agent.orchestrator.run_phase")
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.validate_build_routes")
    async def test_orchestrator_propagates_critical_count(
        self, mock_routes, mock_validate, mock_run, tmp_path
    ):
        """Audit with critical_count=2 should cap quality at grade B."""
        mock_run.side_effect = _mock_run_phase_factory(critical_count=2)
        mock_validate.return_value = _make_validation(phase=Phase.BUILD)
        mock_routes.return_value = _make_validation(phase=Phase.BUILD, extracted={})

        result = await build_product("Build a test app", tmp_path)

        assert result.success is True
        # With 2 CRITICAL findings, quality should be capped at B (84)
        assert "B" in result.quality
        assert "B+" not in result.quality
        assert "A" not in result.quality

    @patch("agent.orchestrator.run_phase")
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.validate_build_routes")
    async def test_orchestrator_zero_critical_no_cap(
        self, mock_routes, mock_validate, mock_run, tmp_path
    ):
        """No CRITICAL findings should allow full quality score."""
        mock_run.side_effect = _mock_run_phase_factory(critical_count=0)
        mock_validate.return_value = _make_validation(phase=Phase.BUILD)
        mock_routes.return_value = _make_validation(phase=Phase.BUILD, extracted={})

        result = await build_product("Build a test app", tmp_path)

        assert result.success is True
        assert "A" in result.quality

    @patch("agent.orchestrator.run_phase")
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.validate_build_routes")
    async def test_critical_count_affects_quality_score_directly(
        self, mock_routes, mock_validate, mock_run, tmp_path
    ):
        """Verify critical_count is set on state and affects compute_quality_score."""
        mock_run.side_effect = _mock_run_phase_factory(critical_count=3)
        mock_validate.return_value = _make_validation(phase=Phase.BUILD)
        mock_routes.return_value = _make_validation(phase=Phase.BUILD, extracted={})

        result = await build_product("Build a test app", tmp_path)

        assert result.success is True
        # 3 CRITICAL = 15 pt penalty on spec_coverage, capped at 84
        assert "B" in result.quality


# ---------------------------------------------------------------------------
# 3. Resume Path — No Unbound Variables
# ---------------------------------------------------------------------------

class TestResumeSkipSafety:
    """Verify no NameError when audit+test phases are both skipped on resume."""

    @patch("agent.orchestrator.run_phase")
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.validate_build_routes")
    @patch("agent.orchestrator.config")
    async def test_resume_skipping_audit_and_test_no_crash(
        self, mock_config, mock_routes, mock_validate, mock_run, tmp_path
    ):
        """Resume past audit+test should not raise NameError."""
        mock_config.MAX_DESIGN_REVISIONS = 3
        mock_config.MAX_BUILD_ATTEMPTS = 5
        mock_config.PHASE_TIMEOUT_S = 600
        mock_config.MAX_TOTAL_TURNS = 300
        mock_config.ENABLE_ARTIFACT_VERIFICATION = False

        # Set up state that's past the test phase
        state = _make_state(
            phase=Phase.DEPLOY,
            idea="test app",
            project_dir=str(tmp_path),
            stack_id="nextjs-supabase",
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            spec_audit_critical_count=0,
            tests_generated=True,
            tests_passed=True,
        )

        # Create artifacts so _should_skip_phase returns True
        (tmp_path / "STACK_DECISION.md").write_text("stack_id: nextjs-supabase")
        (tmp_path / "DESIGN.md").write_text("# Design\ndata model\nroute\nauth")
        (tmp_path / "SPEC_AUDIT.md").write_text("---\nstatus: PASS\n---\n# Audit")
        (tmp_path / "TEST_RESULTS.md").write_text("---\ntests_passed: 10\ntests_total: 10\n---")
        src = tmp_path / "src" / "app"
        src.mkdir(parents=True)
        (src / "page.tsx").write_text("export default function() {}")

        # Deploy and verify phases run normally
        async def mock_phase(phase, st, pdir, prog, retry_context=None):
            call = _make_call_result()
            if phase == Phase.DEPLOY:
                val = _make_validation(phase=Phase.DEPLOY, extracted={"url": "https://test.vercel.app"})
            elif phase == Phase.VERIFY:
                val = _make_validation(phase=Phase.VERIFY, extracted={"verified": True})
            else:
                val = _make_validation(phase=phase, extracted={"stack_id": "nextjs-supabase"})
            return call, val

        mock_run.side_effect = mock_phase
        mock_validate.return_value = _make_validation(phase=Phase.BUILD)
        mock_routes.return_value = _make_validation(phase=Phase.BUILD, extracted={})

        # Patch checkpoint manager to return our pre-built state
        with patch("agent.orchestrator.CheckpointManager") as mock_cp:
            mock_cp_inst = MagicMock()
            mock_cp.return_value = mock_cp_inst
            mock_cp_inst.load_latest.return_value = ("cp-123", state)

            cfg = BuildConfig(resume=True)
            result = await build_product("test app", tmp_path, cfg)

        # The key assertion: no NameError, build completes
        assert result.success is True
        assert result.quality is not None

    @patch("agent.orchestrator.run_phase")
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.validate_build_routes")
    @patch("agent.orchestrator.config")
    async def test_resume_skip_test_detail_empty(
        self, mock_config, mock_routes, mock_validate, mock_run, tmp_path
    ):
        """When test phase is skipped, test_detail should be empty string."""
        mock_config.MAX_DESIGN_REVISIONS = 3
        mock_config.MAX_BUILD_ATTEMPTS = 5
        mock_config.PHASE_TIMEOUT_S = 600
        mock_config.MAX_TOTAL_TURNS = 300
        mock_config.ENABLE_ARTIFACT_VERIFICATION = False

        state = _make_state(
            phase=Phase.DEPLOY,
            idea="test app",
            project_dir=str(tmp_path),
            stack_id="nextjs-supabase",
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            tests_generated=True,
            tests_passed=True,
        )

        (tmp_path / "STACK_DECISION.md").write_text("stack_id: nextjs-supabase")
        (tmp_path / "DESIGN.md").write_text("# Design\ndata model\nroute\nauth")
        (tmp_path / "SPEC_AUDIT.md").write_text("---\nstatus: PASS\n---")
        (tmp_path / "TEST_RESULTS.md").write_text("---\ntests_passed: 5\ntests_total: 5\n---")
        src = tmp_path / "src" / "app"
        src.mkdir(parents=True)
        (src / "page.tsx").write_text("export default function() {}")

        async def mock_phase(phase, st, pdir, prog, retry_context=None):
            call = _make_call_result()
            if phase == Phase.DEPLOY:
                val = _make_validation(phase=Phase.DEPLOY, extracted={"url": "https://test.vercel.app"})
            elif phase == Phase.VERIFY:
                val = _make_validation(phase=Phase.VERIFY, extracted={"verified": True})
            else:
                val = _make_validation(phase=phase, extracted={"stack_id": "nextjs-supabase"})
            return call, val

        mock_run.side_effect = mock_phase
        mock_validate.return_value = _make_validation(phase=Phase.BUILD)
        mock_routes.return_value = _make_validation(phase=Phase.BUILD, extracted={})

        with patch("agent.orchestrator.CheckpointManager") as mock_cp:
            mock_cp_inst = MagicMock()
            mock_cp.return_value = mock_cp_inst
            mock_cp_inst.load_latest.return_value = ("cp-456", state)

            cfg = BuildConfig(resume=True)
            result = await build_product("test app", tmp_path, cfg)

        assert result.success is True
        # test_count should be empty when test phase was skipped
        assert result.test_count == ""


# ---------------------------------------------------------------------------
# 4. Dependency Audit through Build Validation
# ---------------------------------------------------------------------------

class TestDependencyAuditIntegration:
    """Verify missing deps from DESIGN.md surface in build validation."""

    def test_missing_deps_in_build_validation_messages(self, tmp_path):
        """DESIGN.md references @missing/pkg not in package.json → info message."""
        (tmp_path / "DESIGN.md").write_text(
            "Use `@missing/some-lib` for rendering and `@present/other-lib` for data."
        )
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"@present/other-lib": "1.0.0"}}'
        )
        src = tmp_path / "src" / "app"
        src.mkdir(parents=True)
        (src / "page.tsx").write_text("export default function() { return <div/> }")

        result = validate_phase_output(Phase.BUILD, tmp_path)

        assert "@missing/some-lib" in result.extracted.get("missing_deps", [])
        assert "@present/other-lib" not in result.extracted.get("missing_deps", [])
        assert any("@missing/some-lib" in m for m in result.messages)

    def test_missing_deps_do_not_block_build(self, tmp_path):
        """Missing deps are warnings, not errors — build should still pass."""
        (tmp_path / "DESIGN.md").write_text("Use `@fancy/charts` for visualization.")
        (tmp_path / "package.json").write_text('{"dependencies": {"next": "14.0.0"}}')
        src = tmp_path / "src" / "app"
        src.mkdir(parents=True)
        (src / "page.tsx").write_text("export default function() { return <div/> }")

        result = validate_phase_output(Phase.BUILD, tmp_path)

        # Build passes even with missing deps (they're info, not errors)
        assert result.passed is True
        assert "@fancy/charts" in result.extracted.get("missing_deps", [])
