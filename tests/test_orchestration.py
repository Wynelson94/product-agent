"""Tests for agent/main.py orchestration logic.

Tests prompt construction, mode selection, state setup, and helper functions.
Does NOT test the full pipeline (build_product calls claude CLI under the hood).
"""

import inspect
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.main import (
    _get_phase_limits_context,
    _get_agents_for_cli,
    _parse_stack_decision,
    _write_mcp_config,
    ORCHESTRATOR_SYSTEM_PROMPT,
    ENHANCEMENT_ORCHESTRATOR_PROMPT,
    PLUGIN_ORCHESTRATOR_PROMPT,
    HOST_ORCHESTRATOR_PROMPT,
    LEGACY_ORCHESTRATOR_PROMPT,
    MAX_DESIGN_REVISIONS,
    MAX_BUILD_ATTEMPTS,
    build_product,
)
from agent.state import AgentState, Phase, create_initial_state
from agent import config


# ---------------------------------------------------------------------------
# TestPhaseLimitsContext
# ---------------------------------------------------------------------------


class TestPhaseLimitsContext:
    """Tests for _get_phase_limits_context()."""

    def test_fresh_state_shows_full_remaining(self):
        """Fresh state should show zero used and full remaining counts."""
        state = create_initial_state("test idea", "/tmp/test")
        ctx = _get_phase_limits_context(state)

        assert f"Design revisions used: 0/{MAX_DESIGN_REVISIONS}" in ctx
        assert f"remaining: {MAX_DESIGN_REVISIONS}" in ctx
        assert f"Build attempts used: 0/{MAX_BUILD_ATTEMPTS}" in ctx
        assert f"remaining: {MAX_BUILD_ATTEMPTS}" in ctx

    def test_after_design_revisions_remaining_decreases(self):
        """After design revisions, remaining count should decrease."""
        state = create_initial_state("test idea", "/tmp/test")
        state.design_revision = 1
        ctx = _get_phase_limits_context(state)

        expected_remaining = MAX_DESIGN_REVISIONS - 1
        assert f"Design revisions used: 1/{MAX_DESIGN_REVISIONS}" in ctx
        assert f"remaining: {expected_remaining}" in ctx

    def test_after_build_attempts_remaining_decreases(self):
        """After build attempts, remaining count should decrease."""
        state = create_initial_state("test idea", "/tmp/test")
        state.build_attempts = 3
        ctx = _get_phase_limits_context(state)

        expected_remaining = MAX_BUILD_ATTEMPTS - 3
        assert f"Build attempts used: 3/{MAX_BUILD_ATTEMPTS}" in ctx
        assert f"remaining: {expected_remaining}" in ctx

    def test_test_status_when_test_generation_enabled(self):
        """Test status section included when ENABLE_TEST_GENERATION is true."""
        state = create_initial_state("test idea", "/tmp/test")
        state.test_attempts = 1
        state.tests_generated = True
        state.tests_passed = False

        with patch.object(config, "ENABLE_TEST_GENERATION", True):
            ctx = _get_phase_limits_context(state)

        assert "Test Status (v5.1)" in ctx
        assert "Test generation: ENABLED" in ctx
        assert f"Test attempts used: 1/{config.MAX_TEST_ATTEMPTS}" in ctx
        assert "Tests generated: Yes" in ctx
        assert "Tests passed: No" in ctx

    def test_audit_status_when_spec_audit_enabled(self):
        """Audit status section included when ENABLE_SPEC_AUDIT is true."""
        state = create_initial_state("test idea", "/tmp/test")
        state.spec_audit_completed = True
        state.spec_audit_discrepancies = 3

        with patch.object(config, "ENABLE_SPEC_AUDIT", True):
            ctx = _get_phase_limits_context(state)

        assert "Spec Audit Status (v6.0)" in ctx
        assert "Spec audit: ENABLED" in ctx
        assert "Audit completed: Yes" in ctx
        assert "Discrepancies found: 3" in ctx

    def test_exhausted_limits_include_warning(self):
        """Exhausted limits should produce a warning message."""
        state = create_initial_state("test idea", "/tmp/test")
        state.design_revision = MAX_DESIGN_REVISIONS
        state.build_attempts = MAX_BUILD_ATTEMPTS
        ctx = _get_phase_limits_context(state)

        assert "remaining: 0" in ctx
        assert "MUST report failure instead of retrying" in ctx
        assert "If design_remaining is 0" in ctx
        assert "If build_remaining is 0" in ctx


# ---------------------------------------------------------------------------
# TestGetAgentsForCli
# ---------------------------------------------------------------------------


class TestGetAgentsForCli:
    """Tests for _get_agents_for_cli()."""

    def test_returns_all_10_agents(self):
        """Should return all 10 defined agents."""
        agents = _get_agents_for_cli()
        expected_names = {
            "analyzer", "designer", "reviewer", "builder", "deployer",
            "enhancer", "verifier", "tester", "auditor", "enricher",
        }
        assert set(agents.keys()) == expected_names

    def test_each_agent_has_required_fields(self):
        """Each agent must have description, prompt, and tools."""
        agents = _get_agents_for_cli()
        for name, agent_cfg in agents.items():
            assert "description" in agent_cfg, f"{name} missing description"
            assert "prompt" in agent_cfg, f"{name} missing prompt"
            assert "tools" in agent_cfg, f"{name} missing tools"
            assert isinstance(agent_cfg["description"], str)
            assert isinstance(agent_cfg["prompt"], str)
            assert isinstance(agent_cfg["tools"], list)
            assert len(agent_cfg["description"]) > 0
            assert len(agent_cfg["prompt"]) > 0

    def test_model_field_included_when_present(self):
        """Agents with a model field should propagate it to CLI config."""
        agents = _get_agents_for_cli()
        # From definitions.py, analyzer has model="sonnet"
        assert "model" in agents["analyzer"]
        assert agents["analyzer"]["model"] == "sonnet"

        # Verify at least some agents have model fields
        agents_with_model = [n for n, c in agents.items() if "model" in c]
        assert len(agents_with_model) > 0


# ---------------------------------------------------------------------------
# TestParseStackDecision
# ---------------------------------------------------------------------------


class TestParseStackDecision:
    """Tests for _parse_stack_decision()."""

    def test_parse_valid_stack_decision_with_stack_id(self, tmp_path):
        """Parse a valid STACK_DECISION.md with **Stack ID** pattern."""
        content = """# Stack Decision

## Selected Stack
- **Stack ID**: nextjs-prisma
- **Rationale**: Best for marketplace
"""
        (tmp_path / "STACK_DECISION.md").write_text(content)
        result = _parse_stack_decision(tmp_path)
        assert result == "nextjs-prisma"

    def test_parse_with_backtick_wrapped_id(self, tmp_path):
        """Parse Stack ID when wrapped in backticks."""
        content = """# Stack Decision

## Selected Stack
- **Stack ID**: `rails`
- **Rationale**: Rapid prototyping
"""
        (tmp_path / "STACK_DECISION.md").write_text(content)
        result = _parse_stack_decision(tmp_path)
        assert result == "rails"

    def test_fallback_detection_via_stack_name_in_content(self, tmp_path):
        """Fallback to detecting stack name in body text when no ID line."""
        content = """# Stack Decision

We recommend using expo-supabase for this mobile project.
"""
        (tmp_path / "STACK_DECISION.md").write_text(content)
        result = _parse_stack_decision(tmp_path)
        assert result == "expo-supabase"

    def test_missing_file_returns_none(self, tmp_path):
        """Missing STACK_DECISION.md should return None."""
        result = _parse_stack_decision(tmp_path)
        assert result is None

    def test_default_fallback_to_nextjs_supabase(self, tmp_path):
        """Unrecognized content should fall back to nextjs-supabase."""
        content = """# Stack Decision

Some analysis text that doesn't mention any known stack ids.
"""
        (tmp_path / "STACK_DECISION.md").write_text(content)
        result = _parse_stack_decision(tmp_path)
        assert result == "nextjs-supabase"


# ---------------------------------------------------------------------------
# TestWriteMcpConfig
# ---------------------------------------------------------------------------


class TestWriteMcpConfig:
    """Tests for _write_mcp_config()."""

    def test_writes_config_file_when_servers_exist(self, tmp_path):
        """When MCP servers are configured, writes .mcp.json and returns path."""
        mock_config = {
            "mcpServers": {
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "test"},
                }
            }
        }
        with patch("agent.main.get_mcp_config_json", return_value=mock_config):
            result = _write_mcp_config(tmp_path)

        assert result is not None
        config_path = tmp_path / ".mcp.json"
        assert config_path.exists()
        assert result == str(config_path)

        written = json.loads(config_path.read_text())
        assert "mcpServers" in written
        assert "github" in written["mcpServers"]

    def test_returns_none_when_no_servers(self, tmp_path):
        """When no MCP servers are configured, returns None and writes nothing."""
        mock_config = {"mcpServers": {}}
        with patch("agent.main.get_mcp_config_json", return_value=mock_config):
            result = _write_mcp_config(tmp_path)

        assert result is None
        assert not (tmp_path / ".mcp.json").exists()


# ---------------------------------------------------------------------------
# TestOrchestratorPromptContent
# ---------------------------------------------------------------------------


class TestOrchestratorPromptContent:
    """Tests that orchestrator prompts contain expected instructions."""

    # --- Standard prompt ---

    def test_standard_prompt_mentions_all_8_phases(self):
        """Standard prompt should reference all 8 phases by name."""
        phases = [
            "Phase 1: Analysis",
            "Phase 2: Design",
            "Phase 3: Build",
            "Phase 3.5: Spec Audit",
            "Phase 4: Test",
            "Phase 5: Deploy",
            "Phase 6: Verify",
        ]
        for phase in phases:
            assert phase in ORCHESTRATOR_SYSTEM_PROMPT, (
                f"Standard prompt missing phase: {phase}"
            )

    def test_standard_prompt_mentions_all_subagents(self):
        """Standard prompt should list all subagent names in usage section."""
        subagents = [
            "analyzer", "designer", "reviewer", "builder",
            "auditor", "tester", "deployer", "verifier",
        ]
        for agent in subagents:
            assert f"`{agent}`" in ORCHESTRATOR_SYSTEM_PROMPT, (
                f"Standard prompt missing subagent: {agent}"
            )

    def test_standard_prompt_mentions_phase_output_validation(self):
        """Standard prompt should instruct verifying phase outputs before proceeding."""
        assert "Verify Phase Outputs Before Proceeding" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "STACK_DECISION.md exists" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "DESIGN.md exists" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "TEST_RESULTS.md exists" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_standard_prompt_mentions_test_blocking(self):
        """Standard prompt should warn that failed tests block deployment."""
        assert "BLOCKING" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "REQUIRE_PASSING_TESTS" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "MUST NOT proceed" in ORCHESTRATOR_SYSTEM_PROMPT

    # --- Enhancement prompt ---

    def test_enhancement_prompt_mentions_audit_phase(self):
        """Enhancement prompt should include the AUDIT phase (v7.0 fix)."""
        assert "Audit" in ENHANCEMENT_ORCHESTRATOR_PROMPT
        assert "Phase 3.5" in ENHANCEMENT_ORCHESTRATOR_PROMPT

    def test_enhancement_prompt_mentions_auditor_and_tester(self):
        """Enhancement prompt subagent list should include auditor and tester."""
        assert "`auditor`" in ENHANCEMENT_ORCHESTRATOR_PROMPT
        assert "`tester`" in ENHANCEMENT_ORCHESTRATOR_PROMPT

    # --- Plugin prompt ---

    def test_plugin_prompt_mentions_ncbs_plugin(self):
        """Plugin prompt should reference the NCBSPlugin protocol."""
        assert "NCBSPlugin" in PLUGIN_ORCHESTRATOR_PROMPT

    def test_plugin_prompt_mentions_swift_build_and_test(self):
        """Plugin prompt should mention swift build and swift test commands."""
        assert "swift build" in PLUGIN_ORCHESTRATOR_PROMPT
        assert "swift test" in PLUGIN_ORCHESTRATOR_PROMPT

    # --- Host prompt ---

    def test_host_prompt_mentions_plugin_registry(self):
        """Host prompt should mention PluginRegistry."""
        assert "PluginRegistry" in HOST_ORCHESTRATOR_PROMPT or "Plugin registry" in HOST_ORCHESTRATOR_PROMPT

    def test_host_prompt_mentions_minimum_15_tests(self):
        """Host prompt should require minimum 15 tests."""
        assert "15 tests" in HOST_ORCHESTRATOR_PROMPT

    # --- Legacy prompt ---

    def test_legacy_prompt_is_simpler(self):
        """Legacy prompt should have fewer phases than the standard prompt."""
        # Legacy has 3 phases: Design, Build, Deploy
        assert "designer" in LEGACY_ORCHESTRATOR_PROMPT
        assert "builder" in LEGACY_ORCHESTRATOR_PROMPT
        assert "deployer" in LEGACY_ORCHESTRATOR_PROMPT
        # Legacy should NOT mention auditor, tester, verifier, or analyzer
        assert "auditor" not in LEGACY_ORCHESTRATOR_PROMPT
        assert "tester" not in LEGACY_ORCHESTRATOR_PROMPT
        assert "verifier" not in LEGACY_ORCHESTRATOR_PROMPT
        assert "analyzer" not in LEGACY_ORCHESTRATOR_PROMPT

    # --- Safety rules across all prompts ---

    def test_all_prompts_mention_safety_rules(self):
        """Every orchestrator prompt should include safety rules."""
        prompts = {
            "standard": ORCHESTRATOR_SYSTEM_PROMPT,
            "enhancement": ENHANCEMENT_ORCHESTRATOR_PROMPT,
            "plugin": PLUGIN_ORCHESTRATOR_PROMPT,
            "host": HOST_ORCHESTRATOR_PROMPT,
            "legacy": LEGACY_ORCHESTRATOR_PROMPT,
        }
        for name, prompt in prompts.items():
            # All prompts should tell the agent not to ask questions
            assert "Don't ask questions" in prompt or "don't ask questions" in prompt.lower(), (
                f"{name} prompt missing 'Don't ask questions' rule"
            )
            # All prompts should instruct autonomous behavior
            assert "autonomous" in prompt.lower() or "Make decisions" in prompt or "Make reasonable" in prompt, (
                f"{name} prompt missing autonomous behavior instruction"
            )


# ---------------------------------------------------------------------------
# TestBuildModeSelection
# ---------------------------------------------------------------------------


class TestBuildModeSelection:
    """Tests for mode selection logic in build_product."""

    def test_build_product_signature_accepts_all_modes(self):
        """build_product should accept build_mode as a parameter."""
        sig = inspect.signature(build_product)
        params = sig.parameters
        assert "build_mode" in params
        assert params["build_mode"].default == "standard"
        assert "legacy_mode" in params
        assert "design_file" in params

    @patch("agent.main.run_claude")
    @patch("agent.main.check_claude_cli", return_value=(True, "claude 1.0"))
    def test_plugin_mode_sets_swift_stack(self, _mock_cli, mock_run, tmp_path):
        """Plugin mode should set stack to swift-swiftui."""
        mock_run.return_value = {"success": True, "result": "Plugin package ready at /tmp/test - Tests: PASSED - swift build: OK"}

        build_product(
            idea="Photo gallery plugin",
            project_dir=str(tmp_path / "plugin-proj"),
            build_mode="plugin",
        )

        # Verify the prompt passed to run_claude mentions swift-swiftui
        call_kwargs = mock_run.call_args
        prompt = call_kwargs.kwargs.get("prompt") or call_kwargs[1].get("prompt") or call_kwargs[0][0]
        assert "swift-swiftui" in prompt

    @patch("agent.main.run_claude")
    @patch("agent.main.check_claude_cli", return_value=(True, "claude 1.0"))
    def test_host_mode_sets_swift_stack(self, _mock_cli, mock_run, tmp_path):
        """Host mode should set stack to swift-swiftui."""
        mock_run.return_value = {"success": True, "result": "Host app ready at /tmp/test - Tests: PASSED - swift build: OK"}

        build_product(
            idea="NoCloud BS host app",
            project_dir=str(tmp_path / "host-proj"),
            build_mode="host",
        )

        call_kwargs = mock_run.call_args
        prompt = call_kwargs.kwargs.get("prompt") or call_kwargs[1].get("prompt") or call_kwargs[0][0]
        assert "swift-swiftui" in prompt

    @patch("agent.main.run_claude")
    @patch("agent.main.check_claude_cli", return_value=(True, "claude 1.0"))
    def test_each_mode_selects_correct_prompt(self, _mock_cli, mock_run, tmp_path):
        """Each mode should pass its corresponding system prompt to run_claude."""
        # We test three modes: standard, plugin, legacy

        mode_prompt_map = {
            "standard": ORCHESTRATOR_SYSTEM_PROMPT,
            "plugin": PLUGIN_ORCHESTRATOR_PROMPT,
            "host": HOST_ORCHESTRATOR_PROMPT,
        }

        for mode, expected_prompt in mode_prompt_map.items():
            mock_run.reset_mock()
            mock_run.return_value = {"success": True, "result": "done"}

            proj = tmp_path / f"proj-{mode}"
            build_product(
                idea="test idea",
                project_dir=str(proj),
                build_mode=mode,
            )

            call_kwargs = mock_run.call_args
            system_prompt = call_kwargs.kwargs.get("system_prompt") or call_kwargs[1].get("system_prompt")
            assert system_prompt == expected_prompt, (
                f"Mode '{mode}' did not select the expected system prompt"
            )

    @patch("agent.main.run_claude")
    @patch("agent.main.check_claude_cli", return_value=(True, "claude 1.0"))
    def test_legacy_mode_selects_legacy_prompt(self, _mock_cli, mock_run, tmp_path):
        """Legacy mode should use LEGACY_ORCHESTRATOR_PROMPT."""
        mock_run.return_value = {"success": True, "result": "Your app is live at https://test.vercel.app"}

        build_product(
            idea="Simple todo app",
            project_dir=str(tmp_path / "legacy-proj"),
            legacy_mode=True,
        )

        call_kwargs = mock_run.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt") or call_kwargs[1].get("system_prompt")
        assert system_prompt == LEGACY_ORCHESTRATOR_PROMPT


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for hard-coded constants."""

    def test_max_design_revisions_is_2(self):
        """MAX_DESIGN_REVISIONS should be 2."""
        assert MAX_DESIGN_REVISIONS == 2

    def test_max_build_attempts_is_5(self):
        """MAX_BUILD_ATTEMPTS should be 5."""
        assert MAX_BUILD_ATTEMPTS == 5
