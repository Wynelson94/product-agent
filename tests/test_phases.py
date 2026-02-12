"""Comprehensive tests for the phases package — registration, config, prompts, and run_phase."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.phases import (
    PhaseConfig,
    get_all_phase_configs,
    get_phase_config,
    register_phase,
    run_phase,
)
from agent.state import AgentState, Phase, create_initial_state
from agent.cli_runner import PhaseCallResult
from agent.validators import ValidationResult
from agent.progress import ProgressReporter, PhaseResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTERED_PHASES = [
    Phase.ENRICH,
    Phase.ANALYSIS,
    Phase.DESIGN,
    Phase.REVIEW,
    Phase.BUILD,
    Phase.AUDIT,
    Phase.TEST,
    Phase.DEPLOY,
    Phase.VERIFY,
]

EXPECTED_AGENT_NAMES = {
    Phase.ENRICH: "enricher",
    Phase.ANALYSIS: "analyzer",
    Phase.DESIGN: "designer",
    Phase.REVIEW: "reviewer",
    Phase.BUILD: "builder",
    Phase.AUDIT: "auditor",
    Phase.TEST: "tester",
    Phase.DEPLOY: "deployer",
    Phase.VERIFY: "verifier",
}

EXPECTED_MAX_TURNS = {
    Phase.ENRICH: 20,
    Phase.ANALYSIS: 15,
    Phase.DESIGN: 25,
    Phase.REVIEW: 15,
    Phase.BUILD: 80,
    Phase.AUDIT: 20,
    Phase.TEST: 30,
    Phase.DEPLOY: 25,
    Phase.VERIFY: 15,
}

EXPECTED_MAX_RETRIES = {
    Phase.ENRICH: 1,
    Phase.ANALYSIS: 1,
    Phase.DESIGN: 0,
    Phase.REVIEW: 0,
    Phase.BUILD: 4,
    Phase.AUDIT: 0,
    Phase.TEST: 2,
    Phase.DEPLOY: 1,
    Phase.VERIFY: 1,
}


def _make_state(idea: str = "Build a task tracker") -> AgentState:
    """Create a minimal AgentState for testing."""
    return create_initial_state(idea=idea, project_dir="/tmp/test-project")


def _make_progress() -> ProgressReporter:
    """Create a ProgressReporter that writes to nowhere."""
    import io
    return ProgressReporter(output=io.StringIO())


def _make_call_result(success: bool = True) -> PhaseCallResult:
    """Create a stub PhaseCallResult."""
    return PhaseCallResult(
        success=success,
        result_text="ok",
        duration_s=1.5,
        num_turns=3,
        cost_usd=0.02,
        session_id="sess-123",
    )


def _make_validation(passed: bool = True) -> ValidationResult:
    """Create a stub ValidationResult."""
    return ValidationResult(passed=passed, phase=Phase.ENRICH)


# =====================================================================
# 1. Registration completeness
# =====================================================================

class TestPhaseRegistration:
    """Verify that importing agent.phases registers all 9 phases."""

    def test_all_nine_phases_registered(self):
        configs = get_all_phase_configs()
        assert len(configs) == 9

    @pytest.mark.parametrize("phase", REGISTERED_PHASES)
    def test_phase_is_registered(self, phase):
        assert get_phase_config(phase) is not None

    def test_init_phase_not_registered(self):
        assert get_phase_config(Phase.INIT) is None

    def test_complete_phase_not_registered(self):
        assert get_phase_config(Phase.COMPLETE) is None

    def test_failed_phase_not_registered(self):
        assert get_phase_config(Phase.FAILED) is None

    def test_get_all_returns_dict(self):
        configs = get_all_phase_configs()
        assert isinstance(configs, dict)

    def test_get_all_keys_match_registered_phases(self):
        configs = get_all_phase_configs()
        assert set(configs.keys()) == set(REGISTERED_PHASES)

    def test_get_all_returns_copy(self):
        """get_all_phase_configs should return a copy, not the internal dict."""
        a = get_all_phase_configs()
        b = get_all_phase_configs()
        assert a is not b


# =====================================================================
# 2. PhaseConfig dataclass fields
# =====================================================================

class TestPhaseConfigDataclass:
    """Verify PhaseConfig field structure and defaults."""

    def test_has_required_fields(self):
        cfg = PhaseConfig(
            phase=Phase.ENRICH,
            agent_name="test",
            display_name="Test Phase",
            tools=["Read"],
        )
        assert cfg.phase is Phase.ENRICH
        assert cfg.agent_name == "test"
        assert cfg.display_name == "Test Phase"
        assert cfg.tools == ["Read"]

    def test_default_max_turns(self):
        cfg = PhaseConfig(
            phase=Phase.ENRICH,
            agent_name="test",
            display_name="Test",
            tools=[],
        )
        assert cfg.max_turns == 30

    def test_default_max_retries(self):
        cfg = PhaseConfig(
            phase=Phase.ENRICH,
            agent_name="test",
            display_name="Test",
            tools=[],
        )
        assert cfg.max_retries == 1

    def test_default_model_is_none(self):
        cfg = PhaseConfig(
            phase=Phase.ENRICH,
            agent_name="test",
            display_name="Test",
            tools=[],
        )
        assert cfg.model is None

    def test_default_build_prompt_is_none(self):
        cfg = PhaseConfig(
            phase=Phase.ENRICH,
            agent_name="test",
            display_name="Test",
            tools=[],
        )
        assert cfg.build_prompt is None

    def test_default_required_artifacts_is_empty_list(self):
        cfg = PhaseConfig(
            phase=Phase.ENRICH,
            agent_name="test",
            display_name="Test",
            tools=[],
        )
        assert cfg.required_artifacts == []


# =====================================================================
# 3. Agent names
# =====================================================================

class TestAgentNames:
    """Each phase must map to the correct agent_name."""

    @pytest.mark.parametrize("phase,expected_name", list(EXPECTED_AGENT_NAMES.items()))
    def test_agent_name(self, phase, expected_name):
        cfg = get_phase_config(phase)
        assert cfg.agent_name == expected_name


# =====================================================================
# 4. Max turns
# =====================================================================

class TestMaxTurns:
    """Each phase must have the correct max_turns."""

    @pytest.mark.parametrize("phase,expected_turns", list(EXPECTED_MAX_TURNS.items()))
    def test_max_turns(self, phase, expected_turns):
        cfg = get_phase_config(phase)
        assert cfg.max_turns == expected_turns

    def test_build_has_highest_max_turns(self):
        configs = get_all_phase_configs()
        build_turns = configs[Phase.BUILD].max_turns
        for phase, cfg in configs.items():
            if phase is not Phase.BUILD:
                assert cfg.max_turns < build_turns, (
                    f"{phase.value} has max_turns={cfg.max_turns} >= BUILD's {build_turns}"
                )


# =====================================================================
# 5. Max retries
# =====================================================================

class TestMaxRetries:
    """Each phase must have the correct max_retries."""

    @pytest.mark.parametrize("phase,expected_retries", list(EXPECTED_MAX_RETRIES.items()))
    def test_max_retries(self, phase, expected_retries):
        cfg = get_phase_config(phase)
        assert cfg.max_retries == expected_retries

    def test_design_no_retries(self):
        cfg = get_phase_config(Phase.DESIGN)
        assert cfg.max_retries == 0

    def test_review_no_retries(self):
        cfg = get_phase_config(Phase.REVIEW)
        assert cfg.max_retries == 0

    def test_audit_no_retries(self):
        cfg = get_phase_config(Phase.AUDIT)
        assert cfg.max_retries == 0

    def test_build_has_highest_max_retries(self):
        configs = get_all_phase_configs()
        build_retries = configs[Phase.BUILD].max_retries
        for phase, cfg in configs.items():
            if phase is not Phase.BUILD:
                assert cfg.max_retries <= build_retries


# =====================================================================
# 6. Tools
# =====================================================================

class TestTools:
    """Each phase must include expected key tools."""

    def test_enrich_tools(self):
        cfg = get_phase_config(Phase.ENRICH)
        for tool in ["Read", "Write", "WebSearch", "WebFetch"]:
            assert tool in cfg.tools

    def test_analysis_tools(self):
        cfg = get_phase_config(Phase.ANALYSIS)
        for tool in ["Read", "Write", "WebSearch"]:
            assert tool in cfg.tools

    def test_design_tools(self):
        cfg = get_phase_config(Phase.DESIGN)
        for tool in ["Read", "Write", "Glob", "Grep"]:
            assert tool in cfg.tools

    def test_review_tools(self):
        cfg = get_phase_config(Phase.REVIEW)
        for tool in ["Read", "Write", "Glob", "Grep"]:
            assert tool in cfg.tools

    def test_build_tools_include_bash(self):
        cfg = get_phase_config(Phase.BUILD)
        assert "Bash" in cfg.tools
        assert "Read" in cfg.tools
        assert "Write" in cfg.tools

    def test_build_tools_include_edit(self):
        cfg = get_phase_config(Phase.BUILD)
        assert "Edit" in cfg.tools

    def test_audit_tools(self):
        cfg = get_phase_config(Phase.AUDIT)
        for tool in ["Read", "Glob", "Grep", "Write"]:
            assert tool in cfg.tools

    def test_test_tools_include_bash(self):
        cfg = get_phase_config(Phase.TEST)
        assert "Bash" in cfg.tools

    def test_deploy_tools_include_bash(self):
        cfg = get_phase_config(Phase.DEPLOY)
        assert "Bash" in cfg.tools
        assert "Read" in cfg.tools

    def test_verify_tools(self):
        cfg = get_phase_config(Phase.VERIFY)
        for tool in ["Read", "Bash", "WebFetch", "Glob"]:
            assert tool in cfg.tools

    def test_build_has_most_tools(self):
        configs = get_all_phase_configs()
        build_tools_count = len(configs[Phase.BUILD].tools)
        for phase, cfg in configs.items():
            if phase is not Phase.BUILD:
                assert len(cfg.tools) <= build_tools_count, (
                    f"{phase.value} has {len(cfg.tools)} tools >= BUILD's {build_tools_count}"
                )

    def test_all_phases_have_at_least_one_tool(self):
        for phase in REGISTERED_PHASES:
            cfg = get_phase_config(phase)
            assert len(cfg.tools) >= 1


# =====================================================================
# 7. Display names
# =====================================================================

class TestDisplayNames:
    """Each phase must have a non-empty display name."""

    @pytest.mark.parametrize("phase", REGISTERED_PHASES)
    def test_display_name_non_empty(self, phase):
        cfg = get_phase_config(phase)
        assert cfg.display_name
        assert isinstance(cfg.display_name, str)
        assert len(cfg.display_name) > 0


# =====================================================================
# 8. Build prompt callables
# =====================================================================

class TestBuildPrompt:
    """Each registered phase must have a build_prompt callable that produces a string."""

    @pytest.mark.parametrize("phase", REGISTERED_PHASES)
    def test_build_prompt_is_callable(self, phase):
        cfg = get_phase_config(phase)
        assert cfg.build_prompt is not None
        assert callable(cfg.build_prompt)

    @pytest.mark.parametrize("phase", REGISTERED_PHASES)
    def test_build_prompt_returns_nonempty_string(self, phase, tmp_path):
        cfg = get_phase_config(phase)
        state = _make_state()
        prompt = cfg.build_prompt(state, tmp_path)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_enrich_prompt_contains_idea(self, tmp_path):
        cfg = get_phase_config(Phase.ENRICH)
        state = _make_state("Build a task tracker")
        prompt = cfg.build_prompt(state, tmp_path)
        assert "task tracker" in prompt.lower()

    def test_analysis_prompt_contains_idea(self, tmp_path):
        cfg = get_phase_config(Phase.ANALYSIS)
        state = _make_state("Build a task tracker")
        prompt = cfg.build_prompt(state, tmp_path)
        assert "task tracker" in prompt.lower()

    def test_design_prompt_references_stack_decision(self, tmp_path):
        cfg = get_phase_config(Phase.DESIGN)
        state = _make_state()
        prompt = cfg.build_prompt(state, tmp_path)
        assert "STACK_DECISION" in prompt

    def test_review_prompt_references_design(self, tmp_path):
        cfg = get_phase_config(Phase.REVIEW)
        state = _make_state()
        prompt = cfg.build_prompt(state, tmp_path)
        assert "DESIGN" in prompt

    def test_build_prompt_references_design_and_stack(self, tmp_path):
        cfg = get_phase_config(Phase.BUILD)
        state = _make_state()
        prompt = cfg.build_prompt(state, tmp_path)
        assert "DESIGN" in prompt
        assert "STACK_DECISION" in prompt

    def test_audit_prompt_references_original_prompt(self, tmp_path):
        cfg = get_phase_config(Phase.AUDIT)
        state = _make_state()
        prompt = cfg.build_prompt(state, tmp_path)
        assert "ORIGINAL_PROMPT" in prompt

    def test_test_prompt_references_stack_and_design(self, tmp_path):
        cfg = get_phase_config(Phase.TEST)
        state = _make_state()
        prompt = cfg.build_prompt(state, tmp_path)
        assert "STACK_DECISION" in prompt
        assert "DESIGN" in prompt

    def test_deploy_prompt_mentions_deploy(self, tmp_path):
        cfg = get_phase_config(Phase.DEPLOY)
        state = _make_state()
        prompt = cfg.build_prompt(state, tmp_path)
        assert "deploy" in prompt.lower() or "Deploy" in prompt

    def test_verify_prompt_mentions_project_dir(self, tmp_path):
        cfg = get_phase_config(Phase.VERIFY)
        state = _make_state()
        prompt = cfg.build_prompt(state, tmp_path)
        assert str(tmp_path) in prompt

    def test_verify_prompt_includes_deployment_url_when_set(self, tmp_path):
        cfg = get_phase_config(Phase.VERIFY)
        state = _make_state()
        state.deployment_url = "https://my-app.vercel.app"
        prompt = cfg.build_prompt(state, tmp_path)
        assert "https://my-app.vercel.app" in prompt

    def test_design_prompt_includes_revision_feedback(self, tmp_path):
        """When design_revision > 0 and REVIEW.md exists, feedback is injected."""
        cfg = get_phase_config(Phase.DESIGN)
        state = _make_state()
        state.design_revision = 1
        review_file = tmp_path / "REVIEW.md"
        review_file.write_text("Missing auth flow")
        prompt = cfg.build_prompt(state, tmp_path)
        assert "Revision" in prompt
        assert "Missing auth flow" in prompt

    def test_build_prompt_plugin_mode(self, tmp_path):
        cfg = get_phase_config(Phase.BUILD)
        state = _make_state()
        state.build_mode = "plugin"
        prompt = cfg.build_prompt(state, tmp_path)
        assert "plugin" in prompt.lower()


# =====================================================================
# 9. Required artifacts
# =====================================================================

class TestRequiredArtifacts:
    """Verify required_artifacts for key phases."""

    def test_enrich_requires_prompt_md(self):
        cfg = get_phase_config(Phase.ENRICH)
        assert "PROMPT.md" in cfg.required_artifacts

    def test_analysis_requires_stack_decision(self):
        cfg = get_phase_config(Phase.ANALYSIS)
        assert "STACK_DECISION.md" in cfg.required_artifacts

    def test_design_requires_design_md(self):
        cfg = get_phase_config(Phase.DESIGN)
        assert "DESIGN.md" in cfg.required_artifacts

    def test_review_requires_review_md(self):
        cfg = get_phase_config(Phase.REVIEW)
        assert "REVIEW.md" in cfg.required_artifacts

    def test_audit_requires_spec_audit_md(self):
        cfg = get_phase_config(Phase.AUDIT)
        assert "SPEC_AUDIT.md" in cfg.required_artifacts

    def test_test_requires_test_results_md(self):
        cfg = get_phase_config(Phase.TEST)
        assert "TEST_RESULTS.md" in cfg.required_artifacts

    def test_verify_requires_verification_md(self):
        cfg = get_phase_config(Phase.VERIFY)
        assert "VERIFICATION.md" in cfg.required_artifacts


# =====================================================================
# 10. run_phase — error cases
# =====================================================================

class TestRunPhaseErrors:
    """run_phase must reject unregistered phases."""

    async def test_raises_for_init_phase(self):
        state = _make_state()
        progress = _make_progress()
        with pytest.raises(ValueError, match="No configuration registered"):
            await run_phase(Phase.INIT, state, Path("/tmp"), progress)

    async def test_raises_for_complete_phase(self):
        state = _make_state()
        progress = _make_progress()
        with pytest.raises(ValueError, match="No configuration registered"):
            await run_phase(Phase.COMPLETE, state, Path("/tmp"), progress)

    async def test_raises_for_failed_phase(self):
        state = _make_state()
        progress = _make_progress()
        with pytest.raises(ValueError, match="No configuration registered"):
            await run_phase(Phase.FAILED, state, Path("/tmp"), progress)


# =====================================================================
# 11. run_phase — happy path (mocked SDK call)
# =====================================================================

class TestRunPhaseHappyPath:
    """run_phase should call the SDK with correct parameters and return results."""

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="You are an agent.")
    async def test_calls_run_phase_call(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        mock_call.assert_awaited_once()

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="You are an agent.")
    async def test_passes_correct_tools(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        _, kwargs = mock_call.call_args
        assert kwargs["allowed_tools"] == ["Read", "Write", "WebSearch", "WebFetch"]

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="You are an agent.")
    async def test_passes_correct_max_turns(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        _, kwargs = mock_call.call_args
        assert kwargs["max_turns"] == 20

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="You are an agent.")
    async def test_passes_cwd(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        _, kwargs = mock_call.call_args
        assert kwargs["cwd"] == tmp_path

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="You are an agent.")
    async def test_passes_system_prompt(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        _, kwargs = mock_call.call_args
        assert kwargs["system_prompt"] == "You are an agent."

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="You are an agent.")
    async def test_returns_call_result_and_validation(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        call_result = _make_call_result()
        validation = _make_validation()
        mock_call.return_value = call_result
        mock_validate.return_value = validation
        state = _make_state()
        progress = _make_progress()

        result = await run_phase(Phase.ENRICH, state, tmp_path, progress)

        assert result == (call_result, validation)

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="You are an agent.")
    async def test_calls_get_agent_prompt_with_agent_name(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        mock_prompt.assert_called_once_with(
            "enricher",
            stack_id=state.stack_id,
            build_mode=state.build_mode,
        )

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="You are an agent.")
    async def test_calls_validate_phase_output(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        mock_validate.assert_called_once_with(Phase.ENRICH, tmp_path)

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="You are an agent.")
    async def test_reports_phase_start(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()
        progress.phase_start = MagicMock()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        progress.phase_start.assert_called_once_with("Enriching prompt")

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="You are an agent.")
    async def test_reports_phase_complete(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        progress.phase_complete.assert_called_once()
        phase_result = progress.phase_complete.call_args[0][0]
        assert isinstance(phase_result, PhaseResult)
        assert phase_result.phase_name == "Enriching prompt"
        assert phase_result.success is True


# =====================================================================
# 12. run_phase — retry context injection
# =====================================================================

class TestRunPhaseRetryContext:
    """run_phase must prepend retry context when provided."""

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_retry_context_injected_into_prompt(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()

        await run_phase(
            Phase.ENRICH, state, tmp_path, progress,
            retry_context="npm install failed with exit code 1",
        )

        _, kwargs = mock_call.call_args
        prompt = kwargs["prompt"]
        assert "RETRY" in prompt
        assert "npm install failed with exit code 1" in prompt
        assert "Fix the issue" in prompt

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_no_retry_prefix_without_context(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.ENRICH, state, tmp_path, progress, retry_context=None)

        _, kwargs = mock_call.call_args
        prompt = kwargs["prompt"]
        assert "RETRY" not in prompt

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_retry_context_appears_before_original_prompt(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state("Build a task tracker")
        progress = _make_progress()

        await run_phase(
            Phase.ENRICH, state, tmp_path, progress,
            retry_context="Validation failed",
        )

        _, kwargs = mock_call.call_args
        prompt = kwargs["prompt"]
        retry_pos = prompt.index("RETRY")
        idea_pos = prompt.index("task tracker")
        assert retry_pos < idea_pos


# =====================================================================
# 13. run_phase — model passthrough
# =====================================================================

class TestRunPhaseModelPassthrough:
    """run_phase should forward the config model to run_phase_call."""

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_default_model_is_none(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = _make_validation()
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        _, kwargs = mock_call.call_args
        assert kwargs["model"] is None


# =====================================================================
# 14. run_phase — different phases route correctly
# =====================================================================

class TestRunPhaseRouting:
    """Verify run_phase routes to the correct config for various phases."""

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_build_phase_uses_80_turns(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = ValidationResult(passed=True, phase=Phase.BUILD)
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.BUILD, state, tmp_path, progress)

        _, kwargs = mock_call.call_args
        assert kwargs["max_turns"] == 80

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_verify_phase_uses_15_turns(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = ValidationResult(passed=True, phase=Phase.VERIFY)
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.VERIFY, state, tmp_path, progress)

        _, kwargs = mock_call.call_args
        assert kwargs["max_turns"] == 15

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_build_phase_calls_with_builder_agent(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        mock_validate.return_value = ValidationResult(passed=True, phase=Phase.BUILD)
        state = _make_state()
        progress = _make_progress()

        await run_phase(Phase.BUILD, state, tmp_path, progress)

        mock_prompt.assert_called_once_with(
            "builder",
            stack_id=state.stack_id,
            build_mode=state.build_mode,
        )


# =====================================================================
# 15. run_phase — phase_result detail extraction
# =====================================================================

class TestRunPhaseDetailExtraction:
    """run_phase builds detail strings from validation.extracted."""

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_stack_id_detail(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        v = ValidationResult(passed=True, phase=Phase.ANALYSIS)
        v.extracted = {"stack_id": "nextjs-supabase"}
        mock_validate.return_value = v
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.ANALYSIS, state, tmp_path, progress)

        phase_result = progress.phase_complete.call_args[0][0]
        assert phase_result.detail == "-> nextjs-supabase"

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_tests_passed_detail(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        v = ValidationResult(passed=True, phase=Phase.TEST)
        v.extracted = {"tests_passed": 10, "tests_total": 12}
        mock_validate.return_value = v
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.TEST, state, tmp_path, progress)

        phase_result = progress.phase_complete.call_args[0][0]
        assert phase_result.detail == "10/12 passed"

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_approved_detail(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        v = ValidationResult(passed=True, phase=Phase.REVIEW)
        v.extracted = {"approved": True}
        mock_validate.return_value = v
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.REVIEW, state, tmp_path, progress)

        phase_result = progress.phase_complete.call_args[0][0]
        assert phase_result.detail == "APPROVED"

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_needs_revision_detail(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        v = ValidationResult(passed=True, phase=Phase.REVIEW)
        v.extracted = {"approved": False}
        mock_validate.return_value = v
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.REVIEW, state, tmp_path, progress)

        phase_result = progress.phase_complete.call_args[0][0]
        assert phase_result.detail == "NEEDS REVISION"

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_url_detail(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        v = ValidationResult(passed=True, phase=Phase.DEPLOY)
        v.extracted = {"url": "https://my-app.vercel.app"}
        mock_validate.return_value = v
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.DEPLOY, state, tmp_path, progress)

        phase_result = progress.phase_complete.call_args[0][0]
        assert phase_result.detail == "https://my-app.vercel.app"

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_verified_detail(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result()
        v = ValidationResult(passed=True, phase=Phase.VERIFY)
        v.extracted = {"verified": True}
        mock_validate.return_value = v
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.VERIFY, state, tmp_path, progress)

        phase_result = progress.phase_complete.call_args[0][0]
        assert phase_result.detail == "PASSED"

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_empty_detail_when_no_extracted(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result()
        v = ValidationResult(passed=True, phase=Phase.BUILD)
        v.extracted = {}
        mock_validate.return_value = v
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.BUILD, state, tmp_path, progress)

        phase_result = progress.phase_complete.call_args[0][0]
        assert phase_result.detail == ""


# =====================================================================
# 16. run_phase — success flag combines call + validation
# =====================================================================

class TestRunPhaseSuccessFlag:
    """PhaseResult.success should be True only when both call and validation pass."""

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_success_when_both_pass(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result(success=True)
        mock_validate.return_value = _make_validation(passed=True)
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        phase_result = progress.phase_complete.call_args[0][0]
        assert phase_result.success is True

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_failure_when_call_fails(self, mock_prompt, mock_call, mock_validate, tmp_path):
        mock_call.return_value = _make_call_result(success=False)
        mock_validate.return_value = _make_validation(passed=True)
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        phase_result = progress.phase_complete.call_args[0][0]
        assert phase_result.success is False

    @patch("agent.phases.validate_phase_output")
    @patch("agent.phases.run_phase_call", new_callable=AsyncMock)
    @patch("agent.phases.get_agent_prompt", return_value="sys")
    async def test_failure_when_validation_fails(
        self, mock_prompt, mock_call, mock_validate, tmp_path
    ):
        mock_call.return_value = _make_call_result(success=True)
        mock_validate.return_value = _make_validation(passed=False)
        state = _make_state()
        progress = _make_progress()
        progress.phase_complete = MagicMock()

        await run_phase(Phase.ENRICH, state, tmp_path, progress)

        phase_result = progress.phase_complete.call_args[0][0]
        assert phase_result.success is False
