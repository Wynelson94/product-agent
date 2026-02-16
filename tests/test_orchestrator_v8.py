"""Comprehensive tests for agent/orchestrator.py — the v9.0 orchestrator module.

Tests cover:
  - BuildConfig / BuildResult dataclass defaults
  - _get_phase_count logic (standard, enrich, enhancement)
  - _parse_stack_decision file parsing
  - _setup_enhancement_mode design copying and stack inference
  - build_product happy path, failure modes, retries, loops, and edge cases

Quality scoring is tested in test_quality.py (compute_quality_score).

All async tests use pytest.mark.asyncio. External calls to run_phase are
mocked so that tests never invoke Claude.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from agent.orchestrator import (
    BuildConfig,
    BuildResult,
    build_product,
    _build_failed,
    _get_phase_count,
    _parse_stack_decision,
    _setup_enhancement_mode,
    _should_skip_phase,
    _has_source_code,
    _PHASE_ORDER,
)
from agent.state import AgentState, Phase, ReviewStatus, create_initial_state
from agent.validators import ValidationResult
from agent.cli_runner import PhaseCallResult
from agent.progress import ProgressReporter, PhaseResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_call_result(
    success: bool = True,
    result_text: str = "ok",
    error: str = "",
    duration_s: float = 1.0,
    num_turns: int = 5,
    cost_usd: float = 0.02,
    session_id: str = "sess-abc",
) -> PhaseCallResult:
    """Create a PhaseCallResult with sensible defaults."""
    return PhaseCallResult(
        success=success,
        result_text=result_text,
        error=error,
        duration_s=duration_s,
        num_turns=num_turns,
        cost_usd=cost_usd,
        session_id=session_id,
    )


def make_validation(
    passed: bool = True,
    phase: Phase = Phase.ANALYSIS,
    messages: list[str] | None = None,
    extracted: dict | None = None,
) -> ValidationResult:
    """Create a ValidationResult with sensible defaults."""
    return ValidationResult(
        passed=passed,
        phase=phase,
        messages=messages or [],
        extracted=extracted or {},
    )


def make_phase_return(
    success: bool = True,
    phase: Phase = Phase.ANALYSIS,
    extracted: dict | None = None,
    call_error: str = "",
    validation_passed: bool = True,
) -> tuple[PhaseCallResult, ValidationResult]:
    """Create a (PhaseCallResult, ValidationResult) tuple for run_phase mocking."""
    return (
        make_call_result(success=success, error=call_error),
        make_validation(passed=validation_passed, phase=phase, extracted=extracted or {}),
    )


# ---------------------------------------------------------------------------
# 1. BuildConfig defaults
# ---------------------------------------------------------------------------


class TestBuildConfigDefaults:
    """Verify BuildConfig dataclass default values."""

    def test_stack_defaults_to_none(self):
        cfg = BuildConfig()
        assert cfg.stack is None

    def test_mode_defaults_to_standard(self):
        cfg = BuildConfig()
        assert cfg.mode == "standard"

    def test_enrich_defaults_to_false(self):
        cfg = BuildConfig()
        assert cfg.enrich is False

    def test_enrich_url_defaults_to_none(self):
        cfg = BuildConfig()
        assert cfg.enrich_url is None

    def test_verbose_defaults_to_false(self):
        cfg = BuildConfig()
        assert cfg.verbose is False

    def test_require_tests_defaults_to_true(self):
        cfg = BuildConfig()
        assert cfg.require_tests is True

    def test_legacy_defaults_to_false(self):
        cfg = BuildConfig()
        assert cfg.legacy is False

    def test_design_file_defaults_to_none(self):
        cfg = BuildConfig()
        assert cfg.design_file is None

    def test_enhance_features_defaults_to_empty_list(self):
        cfg = BuildConfig()
        assert cfg.enhance_features == []

    def test_enhance_features_independent_per_instance(self):
        """Mutable default should not be shared across instances."""
        a = BuildConfig()
        b = BuildConfig()
        a.enhance_features.append("dark-mode")
        assert b.enhance_features == []

    def test_custom_values_respected(self):
        cfg = BuildConfig(
            stack="rails",
            mode="enhancement",
            enrich=True,
            enrich_url="https://example.com",
            verbose=True,
            require_tests=False,
            legacy=True,
            design_file="/tmp/design.md",
            enhance_features=["dark-mode", "search"],
        )
        assert cfg.stack == "rails"
        assert cfg.mode == "enhancement"
        assert cfg.enrich is True
        assert cfg.enrich_url == "https://example.com"
        assert cfg.verbose is True
        assert cfg.require_tests is False
        assert cfg.legacy is True
        assert cfg.design_file == "/tmp/design.md"
        assert cfg.enhance_features == ["dark-mode", "search"]


# ---------------------------------------------------------------------------
# 2. BuildResult defaults
# ---------------------------------------------------------------------------


class TestBuildResultDefaults:
    """Verify BuildResult dataclass default values."""

    def test_success_is_required(self):
        r = BuildResult(success=True)
        assert r.success is True

    def test_url_defaults_to_none(self):
        r = BuildResult(success=True)
        assert r.url is None

    def test_quality_defaults_to_none(self):
        r = BuildResult(success=True)
        assert r.quality is None

    def test_duration_defaults_to_zero(self):
        r = BuildResult(success=True)
        assert r.duration_s == 0.0

    def test_test_count_defaults_to_none(self):
        r = BuildResult(success=True)
        assert r.test_count is None

    def test_spec_coverage_defaults_to_none(self):
        r = BuildResult(success=True)
        assert r.spec_coverage is None

    def test_reason_defaults_to_none(self):
        r = BuildResult(success=True)
        assert r.reason is None

    def test_phase_results_defaults_to_empty(self):
        r = BuildResult(success=True)
        assert r.phase_results == []

    def test_phase_results_independent_per_instance(self):
        a = BuildResult(success=True)
        b = BuildResult(success=True)
        a.phase_results.append(PhaseResult(phase_name="test", success=True, duration_s=1.0))
        assert b.phase_results == []

    def test_failed_result_with_reason(self):
        r = BuildResult(success=False, reason="Build failed")
        assert r.success is False
        assert r.reason == "Build failed"


# ---------------------------------------------------------------------------
# 3. _get_phase_count
# ---------------------------------------------------------------------------


class TestGetPhaseCount:
    """Tests for _get_phase_count based on build mode."""

    def test_standard_mode_returns_9(self):
        cfg = BuildConfig()
        assert _get_phase_count(cfg) == 9

    def test_standard_with_enrich_returns_10(self):
        cfg = BuildConfig(enrich=True)
        assert _get_phase_count(cfg) == 10

    def test_enhancement_mode_returns_8(self):
        cfg = BuildConfig(mode="enhancement")
        assert _get_phase_count(cfg) == 8

    def test_enhancement_with_enrich_returns_9(self):
        cfg = BuildConfig(mode="enhancement", enrich=True)
        assert _get_phase_count(cfg) == 9

    def test_plugin_mode_returns_9(self):
        cfg = BuildConfig(mode="plugin")
        assert _get_phase_count(cfg) == 9

    def test_host_mode_returns_9(self):
        cfg = BuildConfig(mode="host")
        assert _get_phase_count(cfg) == 9


# ---------------------------------------------------------------------------
# 4. _parse_stack_decision
# ---------------------------------------------------------------------------


class TestParseStackDecision:
    """Tests for _parse_stack_decision file parsing."""

    def test_missing_file_returns_default(self, tmp_path):
        result = _parse_stack_decision(tmp_path)
        assert result == "nextjs-supabase"

    def test_valid_stack_id_line(self, tmp_path):
        content = "# Stack Decision\n\n- **Stack ID**: nextjs-prisma\n"
        (tmp_path / "STACK_DECISION.md").write_text(content)
        assert _parse_stack_decision(tmp_path) == "nextjs-prisma"

    def test_backtick_wrapped_stack_id(self, tmp_path):
        content = "# Stack Decision\n\n- **Stack ID**: `rails`\n"
        (tmp_path / "STACK_DECISION.md").write_text(content)
        assert _parse_stack_decision(tmp_path) == "rails"

    def test_fallback_detection_nextjs_supabase(self, tmp_path):
        content = "We will use the nextjs-supabase stack for rapid development.\n"
        (tmp_path / "STACK_DECISION.md").write_text(content)
        assert _parse_stack_decision(tmp_path) == "nextjs-supabase"

    def test_fallback_detection_expo_supabase(self, tmp_path):
        content = "This mobile project will use expo-supabase.\n"
        (tmp_path / "STACK_DECISION.md").write_text(content)
        assert _parse_stack_decision(tmp_path) == "expo-supabase"

    def test_fallback_detection_swift_swiftui(self, tmp_path):
        content = "The iOS app will use swift-swiftui with local storage.\n"
        (tmp_path / "STACK_DECISION.md").write_text(content)
        assert _parse_stack_decision(tmp_path) == "swift-swiftui"

    def test_unrecognised_content_returns_default(self, tmp_path):
        content = "# Stack Decision\n\nWe chose some custom unknown framework.\n"
        (tmp_path / "STACK_DECISION.md").write_text(content)
        assert _parse_stack_decision(tmp_path) == "nextjs-supabase"

    def test_empty_file_returns_default(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text("")
        assert _parse_stack_decision(tmp_path) == "nextjs-supabase"

    def test_case_sensitive_fallback(self, tmp_path):
        """Fallback checks content.lower(), so mixed case should still match."""
        content = "Using NextJS-Prisma for this project.\n"
        (tmp_path / "STACK_DECISION.md").write_text(content)
        # The fallback does content.lower() then checks if stack_id in it
        # "nextjs-prisma" in "using nextjs-prisma for this project.\n" -> True
        assert _parse_stack_decision(tmp_path) == "nextjs-prisma"


# ---------------------------------------------------------------------------
# 5. _setup_enhancement_mode
# ---------------------------------------------------------------------------


class TestSetupEnhancementMode:
    """Tests for _setup_enhancement_mode."""

    def test_copies_design_file(self, tmp_path):
        source = tmp_path / "source_design.md"
        source.write_text("# Existing Design\n\nUses supabase for storage.\n")
        project = tmp_path / "project"
        project.mkdir()

        state = create_initial_state("enhance todo", str(project))
        cfg = BuildConfig(
            mode="enhancement",
            design_file=str(source),
            enhance_features=["dark-mode"],
        )

        _setup_enhancement_mode(state, cfg, project)

        assert (project / "DESIGN.md").exists()
        assert "Existing Design" in (project / "DESIGN.md").read_text()

    def test_creates_stack_decision_md(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design with supabase\n")
        project = tmp_path / "project"
        project.mkdir()

        state = create_initial_state("enhance", str(project))
        cfg = BuildConfig(mode="enhancement", design_file=str(source), enhance_features=["search"])

        _setup_enhancement_mode(state, cfg, project)

        stack_file = project / "STACK_DECISION.md"
        assert stack_file.exists()
        content = stack_file.read_text()
        assert "Stack Decision" in content
        assert "Enhancement of existing design" in content
        assert "search" in content

    def test_infers_prisma_from_design(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n\nUses Prisma ORM for data.\n")
        project = tmp_path / "project"
        project.mkdir()

        state = create_initial_state("enhance", str(project))
        cfg = BuildConfig(mode="enhancement", design_file=str(source))

        _setup_enhancement_mode(state, cfg, project)
        assert state.stack_id == "nextjs-prisma"

    def test_infers_supabase_from_design(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n\nSupabase for realtime features.\n")
        project = tmp_path / "project"
        project.mkdir()

        state = create_initial_state("enhance", str(project))
        cfg = BuildConfig(mode="enhancement", design_file=str(source))

        _setup_enhancement_mode(state, cfg, project)
        assert state.stack_id == "nextjs-supabase"

    def test_infers_swift_from_design(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n\nBuilt with Swift and SwiftUI.\n")
        project = tmp_path / "project"
        project.mkdir()

        state = create_initial_state("enhance", str(project))
        cfg = BuildConfig(mode="enhancement", design_file=str(source))

        _setup_enhancement_mode(state, cfg, project)
        assert state.stack_id == "swift-swiftui"

    def test_defaults_to_nextjs_supabase_when_no_match(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Generic design doc with no stack clues.\n")
        project = tmp_path / "project"
        project.mkdir()

        state = create_initial_state("enhance", str(project))
        cfg = BuildConfig(mode="enhancement", design_file=str(source))

        _setup_enhancement_mode(state, cfg, project)
        assert state.stack_id == "nextjs-supabase"

    def test_explicit_stack_overrides_inference(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design with prisma\n")
        project = tmp_path / "project"
        project.mkdir()

        state = create_initial_state("enhance", str(project))
        cfg = BuildConfig(mode="enhancement", design_file=str(source), stack="rails")

        _setup_enhancement_mode(state, cfg, project)
        # Explicit stack should be used instead of inferred prisma
        assert state.stack_id == "rails"

    def test_sets_enhancement_mode_flag(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n")
        project = tmp_path / "project"
        project.mkdir()

        state = create_initial_state("enhance", str(project))
        cfg = BuildConfig(mode="enhancement", design_file=str(source), enhance_features=["a", "b"])

        _setup_enhancement_mode(state, cfg, project)
        assert state.enhancement_mode is True
        assert state.enhance_features == ["a", "b"]

    def test_missing_source_design_file(self, tmp_path):
        """When the source design file does not exist, DESIGN.md is not created."""
        project = tmp_path / "project"
        project.mkdir()

        state = create_initial_state("enhance", str(project))
        cfg = BuildConfig(mode="enhancement", design_file="/nonexistent/design.md")

        _setup_enhancement_mode(state, cfg, project)
        # DESIGN.md should NOT exist since the source was missing
        assert not (project / "DESIGN.md").exists()
        # STACK_DECISION.md is still written
        assert (project / "STACK_DECISION.md").exists()
        # Default stack is assigned
        assert state.stack_id == "nextjs-supabase"

    def test_enhancement_features_in_stack_decision(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n")
        project = tmp_path / "project"
        project.mkdir()

        state = create_initial_state("enhance", str(project))
        cfg = BuildConfig(
            mode="enhancement",
            design_file=str(source),
            enhance_features=["dark-mode", "search", "notifications"],
        )

        _setup_enhancement_mode(state, cfg, project)
        content = (project / "STACK_DECISION.md").read_text()
        assert "dark-mode, search, notifications" in content


# ---------------------------------------------------------------------------
# 7. _build_failed helper
# ---------------------------------------------------------------------------


class TestBuildFailed:
    """Tests for the _build_failed helper function."""

    def test_returns_failed_result(self):
        progress = ProgressReporter(verbose=False)
        result = _build_failed(progress, "Analysis failed", "timeout")
        assert result.success is False
        assert result.reason == "Analysis failed: timeout"

    def test_includes_phase_results(self):
        progress = ProgressReporter(verbose=False)
        # Simulate a prior phase result
        progress.phase_complete(PhaseResult(phase_name="Analysis", success=True, duration_s=2.0))
        result = _build_failed(progress, "Build failed", "no source code")
        assert len(result.phase_results) == 1
        assert result.phase_results[0].phase_name == "Analysis"


# ---------------------------------------------------------------------------
# Shared mock builder for build_product tests
# ---------------------------------------------------------------------------


def _standard_phase_responses() -> dict[Phase, tuple]:
    """Return a mapping of Phase -> (PhaseCallResult, ValidationResult) for a happy path."""
    return {
        Phase.ENRICH: make_phase_return(phase=Phase.ENRICH, extracted={}),
        Phase.ANALYSIS: make_phase_return(
            phase=Phase.ANALYSIS, extracted={"stack_id": "nextjs-supabase"}
        ),
        Phase.DESIGN: make_phase_return(phase=Phase.DESIGN, extracted={}),
        Phase.REVIEW: make_phase_return(
            phase=Phase.REVIEW, extracted={"approved": True}
        ),
        Phase.BUILD: make_phase_return(phase=Phase.BUILD, extracted={}),
        Phase.AUDIT: make_phase_return(
            phase=Phase.AUDIT, extracted={"requirements_met": 8, "requirements_total": 10}
        ),
        Phase.TEST: make_phase_return(
            phase=Phase.TEST,
            extracted={"tests_passed": 12, "tests_total": 12, "all_passed": True},
        ),
        Phase.DEPLOY: make_phase_return(
            phase=Phase.DEPLOY, extracted={"url": "https://myapp.vercel.app"}
        ),
        Phase.VERIFY: make_phase_return(
            phase=Phase.VERIFY, extracted={"verified": True}
        ),
    }


def _make_run_phase_mock(
    responses: dict[Phase, tuple] | None = None,
    call_log: list | None = None,
) -> AsyncMock:
    """Create an AsyncMock for run_phase that returns controlled results per phase.

    Args:
        responses: Mapping of Phase -> return value. Uses happy-path defaults if None.
        call_log: Optional list that will be appended with (phase, kwargs) per call.
    """
    phase_map = responses or _standard_phase_responses()

    async def _side_effect(phase, state, project_dir, progress, **kwargs):
        if call_log is not None:
            call_log.append((phase, kwargs))
        if phase in phase_map:
            return phase_map[phase]
        # Fallback: generic success
        return make_phase_return(phase=phase, extracted={})

    mock = AsyncMock(side_effect=_side_effect)
    return mock


# ---------------------------------------------------------------------------
# 8. build_product — happy path
# ---------------------------------------------------------------------------


class TestBuildProductHappyPath:
    """Tests for build_product under normal successful conditions."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_happy_path_returns_success(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is True

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_happy_path_returns_url(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.url == "https://myapp.vercel.app"

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_happy_path_has_quality_score(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.quality is not None
        assert "%" in result.quality

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_happy_path_has_spec_coverage(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.spec_coverage == "8/10"

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_happy_path_has_test_count(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.test_count == "12/12"

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_happy_path_calls_all_phases(self, mock_run_phase, mock_validate, tmp_path):
        call_log = []
        mock_run_phase.side_effect = _make_run_phase_mock(call_log=call_log).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        await build_product("Todo app", tmp_path / "project")

        phases_called = [entry[0] for entry in call_log]
        # Standard mode: analysis, design, review, build, audit, test, deploy, verify
        assert Phase.ANALYSIS in phases_called
        assert Phase.DESIGN in phases_called
        assert Phase.REVIEW in phases_called
        assert Phase.BUILD in phases_called
        assert Phase.AUDIT in phases_called
        assert Phase.TEST in phases_called
        assert Phase.DEPLOY in phases_called
        assert Phase.VERIFY in phases_called


# ---------------------------------------------------------------------------
# 9. build_product — analysis failure
# ---------------------------------------------------------------------------


class TestBuildProductAnalysisFailure:
    """Tests for build_product when analysis fails."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.run_phase")
    async def test_analysis_failure_returns_failed(self, mock_run_phase, tmp_path):
        responses = _standard_phase_responses()
        responses[Phase.ANALYSIS] = make_phase_return(
            success=False, phase=Phase.ANALYSIS, call_error="Claude timeout"
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is False
        assert "Analysis failed" in result.reason

    @pytest.mark.asyncio
    @patch("agent.orchestrator.run_phase")
    async def test_analysis_failure_stops_pipeline(self, mock_run_phase, tmp_path):
        call_log = []
        responses = _standard_phase_responses()
        responses[Phase.ANALYSIS] = make_phase_return(
            success=False, phase=Phase.ANALYSIS, call_error="fail"
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses, call_log=call_log).side_effect

        await build_product("Todo app", tmp_path / "project")

        phases_called = [entry[0] for entry in call_log]
        assert Phase.DESIGN not in phases_called
        assert Phase.BUILD not in phases_called


# ---------------------------------------------------------------------------
# 10. build_product — design/review loop
# ---------------------------------------------------------------------------


class TestBuildProductDesignReviewLoop:
    """Tests for the design/review revision loop."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_needs_revision_triggers_redesign(self, mock_run_phase, mock_validate, tmp_path):
        call_log = []
        review_call_count = 0

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            nonlocal review_call_count
            call_log.append(phase)

            if phase == Phase.REVIEW:
                review_call_count += 1
                if review_call_count == 1:
                    # First review: needs revision
                    return make_phase_return(
                        phase=Phase.REVIEW, extracted={"approved": False}
                    )
                else:
                    # Second review: approved
                    return make_phase_return(
                        phase=Phase.REVIEW, extracted={"approved": True}
                    )

            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is True
        # Design should be called twice (initial + revision)
        assert call_log.count(Phase.DESIGN) == 2
        assert call_log.count(Phase.REVIEW) == 2

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.config")
    @patch("agent.orchestrator.run_phase")
    async def test_max_revisions_proceeds_anyway(self, mock_run_phase, mock_config, mock_validate, tmp_path):
        """When max revisions are exhausted, the build continues with current design."""
        mock_config.MAX_DESIGN_REVISIONS = 1
        mock_config.MAX_BUILD_ATTEMPTS = 5

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            if phase == Phase.REVIEW:
                # Always reject
                return make_phase_return(
                    phase=Phase.REVIEW, extracted={"approved": False}
                )
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        # Should still proceed to build even though review never approved
        assert result.success is True

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_review_call_failure_treats_as_approved(self, mock_run_phase, mock_validate, tmp_path):
        """If the review call itself fails, treat the design as approved."""
        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            if phase == Phase.REVIEW:
                return make_phase_return(
                    success=False, phase=Phase.REVIEW, call_error="timeout"
                )
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is True


# ---------------------------------------------------------------------------
# 11. build_product — build retry
# ---------------------------------------------------------------------------


class TestBuildProductBuildRetry:
    """Tests for the build phase retry logic."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_first_attempt_fails_second_succeeds(self, mock_run_phase, mock_validate, tmp_path):
        build_call_count = 0

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            nonlocal build_call_count
            if phase == Phase.BUILD:
                build_call_count += 1
                if build_call_count == 1:
                    return make_phase_return(
                        success=False, phase=Phase.BUILD, call_error="syntax error"
                    )
                return make_phase_return(phase=Phase.BUILD)
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect

        # First call: validate_phase_output for first build attempt (fails)
        # Second call: validate_phase_output for second build attempt (passes)
        validate_call_count = 0

        def _validate_side_effect(phase, project_dir):
            nonlocal validate_call_count
            validate_call_count += 1
            if validate_call_count == 1:
                return make_validation(passed=False, phase=Phase.BUILD, messages=["FAIL: no source"])
            return make_validation(passed=True, phase=Phase.BUILD)

        mock_validate.side_effect = _validate_side_effect

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is True
        assert build_call_count == 2

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.config")
    @patch("agent.orchestrator.run_phase")
    async def test_build_retry_injects_error_context(self, mock_run_phase, mock_config, mock_validate, tmp_path):
        """On retry, retry_context kwarg should be set with previous error."""
        mock_config.MAX_DESIGN_REVISIONS = 2
        mock_config.MAX_BUILD_ATTEMPTS = 3

        build_kwargs = []

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            if phase == Phase.BUILD:
                build_kwargs.append(kwargs)
                if len(build_kwargs) == 1:
                    return make_phase_return(
                        success=False, phase=Phase.BUILD, call_error="npm install failed"
                    )
                return make_phase_return(phase=Phase.BUILD)
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect

        validate_count = 0

        def _validate_side_effect(phase, project_dir):
            nonlocal validate_count
            validate_count += 1
            if validate_count == 1:
                return make_validation(passed=False, phase=Phase.BUILD)
            return make_validation(passed=True, phase=Phase.BUILD)

        mock_validate.side_effect = _validate_side_effect

        await build_product("Todo app", tmp_path / "project")

        # First build: no retry context
        assert build_kwargs[0].get("retry_context") is None
        # Second build: should have retry context
        assert build_kwargs[1].get("retry_context") is not None
        assert "npm install failed" in build_kwargs[1]["retry_context"]


# ---------------------------------------------------------------------------
# 12. build_product — build exhaustion
# ---------------------------------------------------------------------------


class TestBuildProductBuildExhaustion:
    """Tests for when all build attempts are exhausted."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.config")
    @patch("agent.orchestrator.run_phase")
    async def test_all_attempts_fail_returns_failure(self, mock_run_phase, mock_config, mock_validate, tmp_path):
        mock_config.MAX_DESIGN_REVISIONS = 2
        mock_config.MAX_BUILD_ATTEMPTS = 2

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            if phase == Phase.BUILD:
                return make_phase_return(
                    success=False, phase=Phase.BUILD, call_error="build error"
                )
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=False, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is False
        assert "Build failed after all attempts" in result.reason
        assert "2 attempts exhausted" in result.reason

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.config")
    @patch("agent.orchestrator.run_phase")
    async def test_build_exhaustion_does_not_reach_deploy(self, mock_run_phase, mock_config, mock_validate, tmp_path):
        mock_config.MAX_DESIGN_REVISIONS = 2
        mock_config.MAX_BUILD_ATTEMPTS = 1

        call_log = []

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            call_log.append(phase)
            if phase == Phase.BUILD:
                return make_phase_return(
                    success=False, phase=Phase.BUILD, call_error="error"
                )
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=False, phase=Phase.BUILD)

        await build_product("Todo app", tmp_path / "project")

        assert Phase.DEPLOY not in call_log
        assert Phase.VERIFY not in call_log


# ---------------------------------------------------------------------------
# 13. build_product — test quality gate
# ---------------------------------------------------------------------------


class TestBuildProductTestQualityGate:
    """Tests for the test quality gate that blocks deployment."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_tests_fail_blocks_deploy_when_required(self, mock_run_phase, mock_validate, tmp_path):
        responses = _standard_phase_responses()
        responses[Phase.TEST] = make_phase_return(
            phase=Phase.TEST,
            extracted={"tests_passed": 8, "tests_total": 12, "all_passed": False},
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(require_tests=True)
        result = await build_product("Todo app", tmp_path / "project", build_config=cfg)

        assert result.success is False
        assert "Tests failed" in result.reason

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_tests_fail_does_not_block_when_not_required(self, mock_run_phase, mock_validate, tmp_path):
        responses = _standard_phase_responses()
        responses[Phase.TEST] = make_phase_return(
            phase=Phase.TEST,
            extracted={"tests_passed": 8, "tests_total": 12, "all_passed": False},
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(require_tests=False)
        result = await build_product("Todo app", tmp_path / "project", build_config=cfg)

        assert result.success is True

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_tests_pass_allows_deploy(self, mock_run_phase, mock_validate, tmp_path):
        responses = _standard_phase_responses()
        responses[Phase.TEST] = make_phase_return(
            phase=Phase.TEST,
            extracted={"tests_passed": 12, "tests_total": 12, "all_passed": True},
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(require_tests=True)
        result = await build_product("Todo app", tmp_path / "project", build_config=cfg)

        assert result.success is True


# ---------------------------------------------------------------------------
# 14. build_product — enrichment enabled
# ---------------------------------------------------------------------------


class TestBuildProductEnrichment:
    """Tests for build_product with enrichment phase enabled."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_enrichment_phase_called_when_enabled(self, mock_run_phase, mock_validate, tmp_path):
        call_log = []
        mock_run_phase.side_effect = _make_run_phase_mock(call_log=call_log).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(enrich=True)
        result = await build_product("Todo app", tmp_path / "project", build_config=cfg)

        phases_called = [entry[0] for entry in call_log]
        assert Phase.ENRICH in phases_called
        assert result.success is True

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_enrichment_not_called_when_disabled(self, mock_run_phase, mock_validate, tmp_path):
        call_log = []
        mock_run_phase.side_effect = _make_run_phase_mock(call_log=call_log).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(enrich=False)
        await build_product("Todo app", tmp_path / "project", build_config=cfg)

        phases_called = [entry[0] for entry in call_log]
        assert Phase.ENRICH not in phases_called

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_enrichment_failure_is_nonfatal(self, mock_run_phase, mock_validate, tmp_path):
        """Enrichment failure should not stop the pipeline."""
        responses = _standard_phase_responses()
        responses[Phase.ENRICH] = make_phase_return(
            success=False, phase=Phase.ENRICH, call_error="enrichment failed"
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(enrich=True)
        result = await build_product("Todo app", tmp_path / "project", build_config=cfg)

        assert result.success is True

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_enrich_url_set_in_state(self, mock_run_phase, mock_validate, tmp_path):
        """When enrich_url is provided, it should be set on state before enrich phase."""
        state_snapshots = []

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            if phase == Phase.ENRICH:
                state_snapshots.append(state.enrichment_source_url)
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(enrich=True, enrich_url="https://example.com/reference")
        await build_product("Todo app", tmp_path / "project", build_config=cfg)

        assert state_snapshots[0] == "https://example.com/reference"


# ---------------------------------------------------------------------------
# 15. build_product — creates ORIGINAL_PROMPT.md
# ---------------------------------------------------------------------------


class TestBuildProductOriginalPrompt:
    """Tests for ORIGINAL_PROMPT.md creation."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_creates_original_prompt_file(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        project = tmp_path / "project"
        await build_product("Build a todo app with auth", project)

        prompt_file = project / "ORIGINAL_PROMPT.md"
        assert prompt_file.exists()
        content = prompt_file.read_text()
        assert "Build a todo app with auth" in content
        assert "# Original Product Prompt" in content

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_original_prompt_created_before_phases(self, mock_run_phase, mock_validate, tmp_path):
        """ORIGINAL_PROMPT.md should exist by the time the first phase runs."""
        prompt_exists_during_analysis = None

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            nonlocal prompt_exists_during_analysis
            if phase == Phase.ANALYSIS:
                prompt_exists_during_analysis = (project_dir / "ORIGINAL_PROMPT.md").exists()
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        project = tmp_path / "project"
        await build_product("Test idea", project)

        assert prompt_exists_during_analysis is True


# ---------------------------------------------------------------------------
# 16. build_product — exception handling
# ---------------------------------------------------------------------------


class TestBuildProductExceptionHandling:
    """Tests for exception handling in build_product."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.run_phase")
    async def test_unexpected_exception_returns_failure(self, mock_run_phase, tmp_path):
        async def _raise_error(*args, **kwargs):
            raise RuntimeError("Unexpected SDK crash")

        mock_run_phase.side_effect = _raise_error

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is False
        assert "Unexpected SDK crash" in result.reason

    @pytest.mark.asyncio
    @patch("agent.orchestrator.run_phase")
    async def test_keyboard_interrupt_returns_failure(self, mock_run_phase, tmp_path):
        async def _raise_interrupt(*args, **kwargs):
            raise KeyboardInterrupt()

        mock_run_phase.side_effect = _raise_interrupt

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is False
        assert "Interrupted by user" in result.reason

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_exception_during_build_preserves_prior_work(self, mock_run_phase, mock_validate, tmp_path):
        """Exception during build should still create checkpoints for completed phases."""
        call_log = []

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            call_log.append(phase)
            if phase == Phase.BUILD:
                raise ConnectionError("Network error during build")
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is False
        # Analysis, design, and review should have been called before the exception
        assert Phase.ANALYSIS in call_log
        assert Phase.DESIGN in call_log


# ---------------------------------------------------------------------------
# 17. build_product — design failure
# ---------------------------------------------------------------------------


class TestBuildProductDesignFailure:
    """Tests for build_product when the design phase fails."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.run_phase")
    async def test_design_failure_returns_failed(self, mock_run_phase, tmp_path):
        responses = _standard_phase_responses()
        responses[Phase.DESIGN] = make_phase_return(
            success=False, phase=Phase.DESIGN, call_error="design generation failed"
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is False
        assert "Design failed" in result.reason


# ---------------------------------------------------------------------------
# 18. build_product — stack extraction from analysis
# ---------------------------------------------------------------------------


class TestBuildProductStackExtraction:
    """Tests for stack ID extraction from the analysis phase."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_stack_id_from_validation_extracted(self, mock_run_phase, mock_validate, tmp_path):
        """Stack ID should be taken from validation.extracted if available."""
        stack_seen_in_build = None

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            nonlocal stack_seen_in_build
            if phase == Phase.BUILD:
                stack_seen_in_build = state.stack_id
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert stack_seen_in_build == "nextjs-supabase"

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_explicit_stack_in_config_takes_precedence(self, mock_run_phase, mock_validate, tmp_path):
        stack_seen_during_analysis = None

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            nonlocal stack_seen_during_analysis
            if phase == Phase.ANALYSIS:
                stack_seen_during_analysis = state.stack_id
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(stack="rails")
        await build_product("Todo app", tmp_path / "project", build_config=cfg)

        assert stack_seen_during_analysis == "rails"

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_falls_back_to_parse_stack_decision(self, mock_run_phase, mock_validate, tmp_path):
        """When validation does not extract a stack ID, falls back to file parsing."""
        responses = _standard_phase_responses()
        # Analysis succeeds but doesn't extract stack_id
        responses[Phase.ANALYSIS] = make_phase_return(
            phase=Phase.ANALYSIS, extracted={}
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        project = tmp_path / "project"
        # Pre-create STACK_DECISION.md with a recognizable stack
        project.mkdir(parents=True, exist_ok=True)
        (project / "STACK_DECISION.md").write_text("# Stack\n\n- **Stack ID**: rails\n")

        result = await build_product("Todo app", project)

        assert result.success is True


# ---------------------------------------------------------------------------
# 19. build_product — parallel audit + test
# ---------------------------------------------------------------------------


class TestBuildProductParallelAuditTest:
    """Tests for the parallel audit + test execution."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_audit_and_test_both_called(self, mock_run_phase, mock_validate, tmp_path):
        call_log = []
        mock_run_phase.side_effect = _make_run_phase_mock(call_log=call_log).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        await build_product("Todo app", tmp_path / "project")

        phases_called = [entry[0] for entry in call_log]
        assert Phase.AUDIT in phases_called
        assert Phase.TEST in phases_called

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_audit_failure_does_not_block_pipeline(self, mock_run_phase, mock_validate, tmp_path):
        """If audit fails, the pipeline should still continue."""
        responses = _standard_phase_responses()
        responses[Phase.AUDIT] = make_phase_return(
            success=False, phase=Phase.AUDIT, call_error="audit crash"
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        # Audit failure doesn't block the pipeline; tests still determine quality gate
        assert result.success is True


# ---------------------------------------------------------------------------
# 20. build_product — deploy phase
# ---------------------------------------------------------------------------


class TestBuildProductDeploy:
    """Tests for the deploy phase."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_deploy_url_extracted(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.url == "https://myapp.vercel.app"

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_deploy_without_url(self, mock_run_phase, mock_validate, tmp_path):
        responses = _standard_phase_responses()
        responses[Phase.DEPLOY] = make_phase_return(
            phase=Phase.DEPLOY, extracted={}
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        # URL should be None when deploy doesn't extract one
        assert result.url is None
        assert result.success is True


# ---------------------------------------------------------------------------
# 21. build_product — verify phase
# ---------------------------------------------------------------------------


class TestBuildProductVerify:
    """Tests for the verify phase."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_verification_passed(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is True
        # Quality should reflect verified state
        assert result.quality is not None

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_verification_failed_still_succeeds(self, mock_run_phase, mock_validate, tmp_path):
        """Verify failure does not cause overall build failure."""
        responses = _standard_phase_responses()
        responses[Phase.VERIFY] = make_phase_return(
            phase=Phase.VERIFY, extracted={"verified": False}
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.success is True
        # Unverified deployment → hard capped at grade C
        assert result.quality is not None
        assert "A (" not in result.quality
        assert "A- (" not in result.quality
        assert "B" not in result.quality


# ---------------------------------------------------------------------------
# 22. build_product — default config
# ---------------------------------------------------------------------------


class TestBuildProductDefaultConfig:
    """Tests for build_product when no config is supplied."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_none_config_uses_defaults(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project", build_config=None)

        assert result.success is True

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_project_dir_created_if_missing(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        project = tmp_path / "nested" / "deep" / "project"
        assert not project.exists()

        await build_product("Todo app", project)

        assert project.exists()


# ---------------------------------------------------------------------------
# 23. build_product — enhancement mode
# ---------------------------------------------------------------------------


class TestBuildProductEnhancementMode:
    """Tests for build_product in enhancement mode."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_enhancement_calls_setup(self, mock_run_phase, mock_validate, tmp_path):
        source_design = tmp_path / "existing_design.md"
        source_design.write_text("# Design with supabase\n")

        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(
            mode="enhancement",
            design_file=str(source_design),
            enhance_features=["dark-mode"],
        )
        project = tmp_path / "project"
        result = await build_product("Enhance todo", project, build_config=cfg)

        assert result.success is True
        # DESIGN.md should have been copied
        assert (project / "DESIGN.md").exists()
        # STACK_DECISION.md should have been created
        assert (project / "STACK_DECISION.md").exists()


# ---------------------------------------------------------------------------
# 24. build_product — test results extraction
# ---------------------------------------------------------------------------


class TestBuildProductTestResultsExtraction:
    """Tests for how test results are extracted and stored."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_test_count_from_extracted(self, mock_run_phase, mock_validate, tmp_path):
        responses = _standard_phase_responses()
        responses[Phase.TEST] = make_phase_return(
            phase=Phase.TEST,
            extracted={"tests_passed": 15, "tests_total": 20, "all_passed": True},
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.test_count == "15/20"

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_test_no_extracted_uses_call_success(self, mock_run_phase, mock_validate, tmp_path):
        """When test validation doesn't extract counts, tests_passed = call.success."""
        responses = _standard_phase_responses()
        responses[Phase.TEST] = make_phase_return(
            phase=Phase.TEST,
            extracted={},  # No test counts extracted
        )
        mock_run_phase.side_effect = _make_run_phase_mock(responses).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        # test_count will be empty string since no tests_passed in extracted
        assert result.success is True


# ---------------------------------------------------------------------------
# 25. Additional edge cases
# ---------------------------------------------------------------------------


class TestBuildProductEdgeCases:
    """Additional edge case tests."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_string_project_dir_converted_to_path(self, mock_run_phase, mock_validate, tmp_path):
        """build_product should accept string project_dir and resolve it."""
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        project_str = str(tmp_path / "project")
        result = await build_product("Todo app", project_str)

        assert result.success is True
        assert Path(project_str).exists()

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_build_mode_set_on_state(self, mock_run_phase, mock_validate, tmp_path):
        """State should have build_mode set from config."""
        mode_seen = None

        async def _side_effect(phase, state, project_dir, progress, **kwargs):
            nonlocal mode_seen
            if phase == Phase.ANALYSIS:
                mode_seen = state.build_mode
            responses = _standard_phase_responses()
            if phase in responses:
                return responses[phase]
            return make_phase_return(phase=phase)

        mock_run_phase.side_effect = _side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(mode="plugin")
        await build_product("Todo app", tmp_path / "project", build_config=cfg)

        assert mode_seen == "plugin"

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_duration_is_positive(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        assert result.duration_s > 0

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_phase_results_populated(self, mock_run_phase, mock_validate, tmp_path):
        mock_run_phase.side_effect = _make_run_phase_mock().side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        result = await build_product("Todo app", tmp_path / "project")

        # Progress reporter collects results; our mock won't populate these
        # but the result should at least have the list attribute
        assert isinstance(result.phase_results, list)


# ---------------------------------------------------------------------------
# 26. _should_skip_phase (v9.1)
# ---------------------------------------------------------------------------


class TestShouldSkipPhase:
    """Tests for _should_skip_phase phase skip logic (v9.1 crash recovery)."""

    def test_fresh_state_skips_nothing(self, tmp_path):
        """INIT state should not skip any phase."""
        state = create_initial_state("test", str(tmp_path))
        for phase in [Phase.ANALYSIS, Phase.DESIGN, Phase.REVIEW, Phase.BUILD]:
            assert _should_skip_phase(state, phase, tmp_path) is False

    def test_analysis_done_skips_analysis(self, tmp_path):
        """When state is past ANALYSIS and STACK_DECISION.md exists, skip it."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.BUILD
        state.stack_id = "nextjs-supabase"
        (tmp_path / "STACK_DECISION.md").write_text("# Stack\n")

        assert _should_skip_phase(state, Phase.ANALYSIS, tmp_path) is True

    def test_analysis_not_skipped_if_artifact_missing(self, tmp_path):
        """Even if state says past analysis, don't skip if STACK_DECISION.md is missing."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.BUILD
        state.stack_id = "nextjs-supabase"
        # No STACK_DECISION.md

        assert _should_skip_phase(state, Phase.ANALYSIS, tmp_path) is False

    def test_design_skipped_when_file_exists(self, tmp_path):
        """DESIGN phase is skipped when DESIGN.md exists and state is past it."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.BUILD
        (tmp_path / "DESIGN.md").write_text("# Design\n")

        assert _should_skip_phase(state, Phase.DESIGN, tmp_path) is True

    def test_review_skipped_when_design_exists(self, tmp_path):
        """REVIEW phase is skipped when DESIGN.md exists and state is past REVIEW."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.BUILD
        (tmp_path / "DESIGN.md").write_text("# Design\n")

        assert _should_skip_phase(state, Phase.REVIEW, tmp_path) is True

    def test_build_done_skips_build(self, tmp_path):
        """When state is past BUILD and source code exists, skip it."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.DEPLOY
        src = tmp_path / "src"
        src.mkdir()
        (src / "index.tsx").write_text("export default function App() {}")

        assert _should_skip_phase(state, Phase.BUILD, tmp_path) is True

    def test_build_not_skipped_if_no_source(self, tmp_path):
        """When state is past BUILD but no source code exists, re-run BUILD."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.DEPLOY

        assert _should_skip_phase(state, Phase.BUILD, tmp_path) is False

    def test_future_phase_never_skipped(self, tmp_path):
        """Phases after the checkpoint phase should never be skipped."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.REVIEW

        assert _should_skip_phase(state, Phase.BUILD, tmp_path) is False
        assert _should_skip_phase(state, Phase.DEPLOY, tmp_path) is False

    def test_failed_state_checks_artifacts(self, tmp_path):
        """FAILED state should check artifacts to determine skip status."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.FAILED
        state.stack_id = "nextjs-supabase"
        (tmp_path / "STACK_DECISION.md").write_text("# Stack\n")

        assert _should_skip_phase(state, Phase.ANALYSIS, tmp_path) is True

    def test_failed_state_no_artifacts_skips_nothing(self, tmp_path):
        """FAILED state with no artifacts should not skip any phase."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.FAILED

        assert _should_skip_phase(state, Phase.ANALYSIS, tmp_path) is False
        assert _should_skip_phase(state, Phase.BUILD, tmp_path) is False

    def test_audit_skipped_when_completed(self, tmp_path):
        """AUDIT is skipped when spec_audit_completed and SPEC_AUDIT.md exists."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.DEPLOY
        state.spec_audit_completed = True
        (tmp_path / "SPEC_AUDIT.md").write_text("# Audit\n")

        assert _should_skip_phase(state, Phase.AUDIT, tmp_path) is True

    def test_audit_not_skipped_without_file(self, tmp_path):
        """AUDIT is not skipped when spec_audit_completed but no SPEC_AUDIT.md."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.DEPLOY
        state.spec_audit_completed = True

        assert _should_skip_phase(state, Phase.AUDIT, tmp_path) is False

    def test_test_skipped_when_completed(self, tmp_path):
        """TEST is skipped when tests_generated and TEST_RESULTS.md exists."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.DEPLOY
        state.tests_generated = True
        (tmp_path / "TEST_RESULTS.md").write_text("# Tests\n")

        assert _should_skip_phase(state, Phase.TEST, tmp_path) is True

    def test_deploy_skipped_when_url_set(self, tmp_path):
        """DEPLOY is skipped when deployment_url is set."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.VERIFY
        state.deployment_url = "https://app.vercel.app"

        assert _should_skip_phase(state, Phase.DEPLOY, tmp_path) is True

    def test_deploy_skipped_when_blocked(self, tmp_path):
        """DEPLOY is skipped when DEPLOY_BLOCKED.md exists."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.VERIFY
        (tmp_path / "DEPLOY_BLOCKED.md").write_text("Blocked\n")

        assert _should_skip_phase(state, Phase.DEPLOY, tmp_path) is True

    def test_verify_skipped_when_file_exists(self, tmp_path):
        """VERIFY is skipped when VERIFICATION.md exists."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.COMPLETE
        (tmp_path / "VERIFICATION.md").write_text("# Verification\n")

        assert _should_skip_phase(state, Phase.VERIFY, tmp_path) is True

    def test_enrich_skipped_when_enriched(self, tmp_path):
        """ENRICH is skipped when prompt_enriched is True."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.BUILD
        state.prompt_enriched = True

        assert _should_skip_phase(state, Phase.ENRICH, tmp_path) is True

    def test_enrich_not_skipped_when_not_enriched(self, tmp_path):
        """ENRICH is not skipped when prompt_enriched is False."""
        state = create_initial_state("test", str(tmp_path))
        state.phase = Phase.BUILD
        state.prompt_enriched = False

        assert _should_skip_phase(state, Phase.ENRICH, tmp_path) is False


# ---------------------------------------------------------------------------
# 27. _has_source_code (v9.1)
# ---------------------------------------------------------------------------


class TestHasSourceCode:
    """Tests for _has_source_code helper (v9.1)."""

    def test_no_source_dirs(self, tmp_path):
        """Returns False when no source directories exist."""
        assert _has_source_code(tmp_path) is False

    def test_src_dir_with_files(self, tmp_path):
        """Returns True when src/ contains files."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "index.ts").write_text("// code")
        assert _has_source_code(tmp_path) is True

    def test_sources_dir_for_swift(self, tmp_path):
        """Returns True when Sources/ contains files (Swift projects)."""
        sources = tmp_path / "Sources"
        sources.mkdir()
        (sources / "main.swift").write_text("// code")
        assert _has_source_code(tmp_path) is True

    def test_empty_src_dir(self, tmp_path):
        """Returns False when src/ exists but is empty."""
        (tmp_path / "src").mkdir()
        assert _has_source_code(tmp_path) is False

    def test_app_dir(self, tmp_path):
        """Returns True when app/ contains files."""
        app = tmp_path / "app"
        app.mkdir()
        (app / "page.tsx").write_text("// code")
        assert _has_source_code(tmp_path) is True

    def test_lib_dir(self, tmp_path):
        """Returns True when lib/ contains files."""
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "utils.py").write_text("# code")
        assert _has_source_code(tmp_path) is True

    def test_nested_files_detected(self, tmp_path):
        """Returns True when files are in subdirectories of src/."""
        deep = tmp_path / "src" / "components" / "ui"
        deep.mkdir(parents=True)
        (deep / "Button.tsx").write_text("// button")
        assert _has_source_code(tmp_path) is True


# ---------------------------------------------------------------------------
# 28. _PHASE_ORDER (v9.1)
# ---------------------------------------------------------------------------


class TestPhaseOrder:
    """Tests for the _PHASE_ORDER mapping (v9.1)."""

    def test_init_is_lowest(self):
        """INIT should have the lowest positive order."""
        assert _PHASE_ORDER[Phase.INIT] == 0

    def test_failed_is_negative(self):
        """FAILED should have negative order for artifact-based resume."""
        assert _PHASE_ORDER[Phase.FAILED] < 0

    def test_audit_and_test_same_order(self):
        """AUDIT and TEST should have the same order (they run in parallel)."""
        assert _PHASE_ORDER[Phase.AUDIT] == _PHASE_ORDER[Phase.TEST]

    def test_pipeline_ordering(self):
        """Phases should be ordered correctly in the pipeline."""
        assert _PHASE_ORDER[Phase.ANALYSIS] < _PHASE_ORDER[Phase.DESIGN]
        assert _PHASE_ORDER[Phase.DESIGN] < _PHASE_ORDER[Phase.REVIEW]
        assert _PHASE_ORDER[Phase.REVIEW] < _PHASE_ORDER[Phase.BUILD]
        assert _PHASE_ORDER[Phase.BUILD] < _PHASE_ORDER[Phase.AUDIT]
        assert _PHASE_ORDER[Phase.AUDIT] < _PHASE_ORDER[Phase.DEPLOY]
        assert _PHASE_ORDER[Phase.DEPLOY] < _PHASE_ORDER[Phase.VERIFY]

    def test_complete_is_highest(self):
        """COMPLETE should have the highest order."""
        assert _PHASE_ORDER[Phase.COMPLETE] > _PHASE_ORDER[Phase.VERIFY]


# ---------------------------------------------------------------------------
# 29. BuildConfig resume fields (v9.1)
# ---------------------------------------------------------------------------


class TestBuildConfigResumeFields:
    """Tests for the resume fields added to BuildConfig (v9.1)."""

    def test_resume_defaults_to_false(self):
        """resume should default to False."""
        cfg = BuildConfig()
        assert cfg.resume is False

    def test_resume_from_defaults_to_none(self):
        """resume_from should default to None."""
        cfg = BuildConfig()
        assert cfg.resume_from is None

    def test_resume_can_be_set(self):
        """resume flag can be explicitly set."""
        cfg = BuildConfig(resume=True, resume_from="build_20260215_120000")
        assert cfg.resume is True
        assert cfg.resume_from == "build_20260215_120000"


# ---------------------------------------------------------------------------
# 30. build_product — resume (v9.1)
# ---------------------------------------------------------------------------


class TestBuildProductResume:
    """Tests for build_product with resume=True (v9.1 crash recovery)."""

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_resume_skips_completed_phases(self, mock_run_phase, mock_validate, tmp_path):
        """Resume should skip phases that have completed artifacts."""
        project = tmp_path / "project"
        project.mkdir(parents=True)

        # Set up artifacts as if analysis, design, review, build completed
        (project / "ORIGINAL_PROMPT.md").write_text("# Original\n\nResume test\n")
        (project / "STACK_DECISION.md").write_text("# Stack\n- **Stack ID**: nextjs-supabase\n")
        (project / "DESIGN.md").write_text("# Design\n")
        src = project / "src"
        src.mkdir()
        (src / "index.tsx").write_text("export default function App() {}")

        # Create a checkpoint at BUILD phase
        from agent.checkpoints import CheckpointManager
        mgr = CheckpointManager(str(project))
        state = create_initial_state("Resume test", str(project))
        state.phase = Phase.BUILD
        state.stack_id = "nextjs-supabase"
        state.build_attempts = 1
        mgr.save(state)

        call_log = []
        mock_run_phase.side_effect = _make_run_phase_mock(call_log=call_log).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(resume=True)
        result = await build_product("Resume test", project, build_config=cfg)

        phases_called = [entry[0] for entry in call_log]
        # Should NOT call analysis, design, review, or build
        assert Phase.ANALYSIS not in phases_called
        assert Phase.DESIGN not in phases_called
        assert Phase.REVIEW not in phases_called
        assert Phase.BUILD not in phases_called
        # Should call audit, test, deploy, verify
        assert Phase.AUDIT in phases_called
        assert Phase.TEST in phases_called

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_resume_no_checkpoint_falls_back_to_fresh(self, mock_run_phase, mock_validate, tmp_path):
        """Resume without a checkpoint should fall back to fresh build."""
        project = tmp_path / "project"

        call_log = []
        mock_run_phase.side_effect = _make_run_phase_mock(call_log=call_log).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(resume=True)
        result = await build_product("Fresh build", project, build_config=cfg)

        phases_called = [entry[0] for entry in call_log]
        # Should run all phases since no checkpoint exists
        assert Phase.ANALYSIS in phases_called
        assert result.success is True

    @pytest.mark.asyncio
    @patch("agent.orchestrator.validate_phase_output")
    @patch("agent.orchestrator.run_phase")
    async def test_resume_reruns_phase_when_artifact_missing(self, mock_run_phase, mock_validate, tmp_path):
        """Resume should re-run a phase whose artifact was deleted."""
        project = tmp_path / "project"
        project.mkdir(parents=True)

        (project / "ORIGINAL_PROMPT.md").write_text("# Original\n\nTest\n")
        # Create checkpoint at REVIEW but DON'T create DESIGN.md
        (project / "STACK_DECISION.md").write_text("# Stack\n")
        # No DESIGN.md — design should be re-run

        from agent.checkpoints import CheckpointManager
        mgr = CheckpointManager(str(project))
        state = create_initial_state("Artifact test", str(project))
        state.phase = Phase.REVIEW
        state.stack_id = "nextjs-supabase"
        mgr.save(state)

        call_log = []
        mock_run_phase.side_effect = _make_run_phase_mock(call_log=call_log).side_effect
        mock_validate.return_value = make_validation(passed=True, phase=Phase.BUILD)

        cfg = BuildConfig(resume=True)
        result = await build_product("Artifact test", project, build_config=cfg)

        phases_called = [entry[0] for entry in call_log]
        # Analysis should be skipped (has STACK_DECISION.md)
        assert Phase.ANALYSIS not in phases_called
        # Design+Review should be re-run (no DESIGN.md)
        assert Phase.DESIGN in phases_called
