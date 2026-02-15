"""Tests for agent definitions and prompt injection (v7.0).

Validates the agent registry, tool assignments, prompt content for all 10 agents,
and template injection via get_agent_prompt().
"""

import pytest

from agent.agents.definitions import get_agents, get_agent_prompt


# ---------------------------------------------------------------------------
# TestAgentRegistry: validate the shape and completeness of get_agents()
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    """Verify get_agents() returns the correct registry structure."""

    def test_returns_exactly_ten_agents(self):
        agents = get_agents()
        assert len(agents) == 10

    def test_all_expected_agent_names_present(self):
        agents = get_agents()
        expected = {
            "analyzer", "designer", "reviewer", "builder", "deployer",
            "enhancer", "verifier", "tester", "auditor", "enricher",
        }
        assert set(agents.keys()) == expected

    def test_each_agent_has_required_fields(self):
        agents = get_agents()
        for name, agent in agents.items():
            assert "description" in agent, f"{name} missing description"
            assert "prompt" in agent, f"{name} missing prompt"
            assert "tools" in agent, f"{name} missing tools"
            assert isinstance(agent["description"], str), f"{name} description not str"
            assert isinstance(agent["prompt"], str), f"{name} prompt not str"
            assert isinstance(agent["tools"], list), f"{name} tools not list"

    def test_all_agents_have_model_set_to_sonnet(self):
        agents = get_agents()
        for name, agent in agents.items():
            assert "model" in agent, f"{name} missing model field"
            assert agent["model"] == "sonnet", f"{name} model is {agent['model']!r}, expected 'sonnet'"


# ---------------------------------------------------------------------------
# TestAgentTools: validate the tool list for every agent
# ---------------------------------------------------------------------------

class TestAgentTools:
    """Verify each agent has exactly the expected tools."""

    def test_analyzer_tools(self):
        tools = get_agents()["analyzer"]["tools"]
        assert tools == ["Read", "Write", "WebSearch"]

    def test_designer_tools(self):
        tools = get_agents()["designer"]["tools"]
        assert tools == ["Read", "Write", "Glob", "Grep"]

    def test_reviewer_tools(self):
        tools = get_agents()["reviewer"]["tools"]
        assert tools == ["Read", "Write", "Glob", "Grep"]

    def test_builder_tools(self):
        tools = get_agents()["builder"]["tools"]
        assert tools == ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]

    def test_deployer_tools(self):
        tools = get_agents()["deployer"]["tools"]
        assert tools == ["Read", "Bash", "WebFetch", "Glob"]

    def test_tester_tools(self):
        tools = get_agents()["tester"]["tools"]
        assert tools == ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]

    def test_auditor_tools(self):
        tools = get_agents()["auditor"]["tools"]
        assert tools == ["Read", "Glob", "Grep", "Write"]

    def test_enricher_tools(self):
        tools = get_agents()["enricher"]["tools"]
        assert tools == ["Read", "Write", "WebSearch", "WebFetch"]

    def test_verifier_tools(self):
        tools = get_agents()["verifier"]["tools"]
        assert tools == ["Read", "Bash", "WebFetch", "Glob"]

    def test_enhancer_tools(self):
        tools = get_agents()["enhancer"]["tools"]
        assert tools == ["Read", "Write", "Glob", "Grep"]


# ---------------------------------------------------------------------------
# TestAnalyzerPrompt
# ---------------------------------------------------------------------------

class TestAnalyzerPrompt:
    """Verify the analyzer prompt covers stack selection and deployment concerns."""

    @pytest.fixture(autouse=True)
    def _load_prompt(self):
        self.prompt = get_agents()["analyzer"]["prompt"]

    def test_mentions_stack_selection(self):
        assert "technology stack" in self.prompt

    def test_mentions_deployment_compatibility(self):
        assert "Deployment Compatibility" in self.prompt

    def test_mentions_sqlite_vercel_warning(self):
        assert "SQLite" in self.prompt
        assert "Vercel" in self.prompt
        assert "WILL FAIL" in self.prompt

    def test_mentions_prompt_md_enricher_output(self):
        assert "PROMPT.md" in self.prompt

    def test_mentions_swift_swiftui_stack_option(self):
        assert "swift-swiftui" in self.prompt
        assert "Swift + SwiftUI" in self.prompt

    def test_mentions_stack_decision_output_format(self):
        assert "STACK_DECISION.md" in self.prompt


# ---------------------------------------------------------------------------
# TestDesignerPrompt
# ---------------------------------------------------------------------------

class TestDesignerPrompt:
    """Verify the designer prompt covers design output and Swift/SwiftUI patterns."""

    @pytest.fixture(autouse=True)
    def _load_prompt(self):
        self.prompt = get_agents()["designer"]["prompt"]

    def test_mentions_design_md_output(self):
        assert "DESIGN.md" in self.prompt

    def test_mentions_prompt_md_enricher_output(self):
        assert "PROMPT.md" in self.prompt

    def test_mentions_swift_swiftui_section(self):
        assert "Swift/SwiftUI" in self.prompt

    def test_mentions_observable_requirement(self):
        assert "@Observable" in self.prompt

    def test_mentions_plugin_manifest(self):
        assert "Manifest" in self.prompt

    def test_mentions_plugin_storage_key_convention(self):
        assert "Storage Key Convention" in self.prompt
        assert "namespaced" in self.prompt

    def test_mentions_error_loading_states_section(self):
        assert "Error & Loading States" in self.prompt

    def test_mentions_form_validation_section(self):
        assert "Form Validation" in self.prompt


# ---------------------------------------------------------------------------
# TestBuilderPrompt
# ---------------------------------------------------------------------------

class TestBuilderPrompt:
    """Verify the builder prompt covers core principles and stack templates inject correctly."""

    @pytest.fixture(autouse=True)
    def _load_prompt(self):
        self.prompt = get_agents()["builder"]["prompt"]

    def test_mentions_original_prompt_cross_reference(self):
        assert "ORIGINAL_PROMPT.md" in self.prompt

    def test_mentions_error_handling(self):
        assert "Error Handling" in self.prompt

    def test_core_prompt_is_concise(self):
        # After extracting per-stack content, core should be under 200 lines
        line_count = self.prompt.count("\n")
        assert line_count < 200, f"Core builder prompt is {line_count} lines, expected < 200"

    def test_swift_builder_template_injects_sdk(self):
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "NCBSPluginSDK" in prompt

    def test_swift_builder_template_injects_observable(self):
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "@Observable" in prompt

    def test_swift_builder_template_injects_color_constants(self):
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "Color+NoCloudBS" in prompt

    def test_swift_builder_template_injects_plugin_manifest(self):
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "PluginManifest" in prompt

    def test_nextjs_builder_template_injects_test_infra(self):
        prompt = get_agent_prompt("builder", stack_id="nextjs-supabase")
        assert "vitest.config.ts" in prompt

    def test_builder_template_injects_build_process(self):
        prompt = get_agent_prompt("builder", stack_id="nextjs-prisma")
        assert "Build Process Reference" in prompt


# ---------------------------------------------------------------------------
# TestDeployerPrompt
# ---------------------------------------------------------------------------

class TestDeployerPrompt:
    """Verify the deployer prompt covers pre-deployment validation and Swift modes."""

    @pytest.fixture(autouse=True)
    def _load_prompt(self):
        self.prompt = get_agents()["deployer"]["prompt"]

    def test_mentions_pre_deployment_validation(self):
        assert "Pre-Deployment Validation" in self.prompt

    def test_mentions_sqlite_vercel_check(self):
        assert "SQLite + Serverless Check" in self.prompt

    def test_mentions_swift_plugin_mode(self):
        assert "Plugin Mode" in self.prompt

    def test_mentions_swift_host_mode(self):
        assert "Host Mode" in self.prompt

    def test_mentions_deploy_blocked_md(self):
        assert "DEPLOY_BLOCKED.md" in self.prompt


# ---------------------------------------------------------------------------
# TestTesterPrompt
# ---------------------------------------------------------------------------

class TestTesterPrompt:
    """Verify the tester prompt covers cross-referencing and minimum test counts."""

    @pytest.fixture(autouse=True)
    def _load_prompt(self):
        self.prompt = get_agents()["tester"]["prompt"]

    def test_mentions_original_prompt_md(self):
        assert "ORIGINAL_PROMPT.md" in self.prompt

    def test_mentions_minimum_11_tests_for_web(self):
        assert "11 tests" in self.prompt

    def test_mentions_minimum_8_tests_for_plugin(self):
        assert "8 tests" in self.prompt

    def test_mentions_minimum_15_tests_for_host(self):
        assert "15 tests" in self.prompt

    def test_mentions_swift_xctest(self):
        assert "XCTest" in self.prompt


# ---------------------------------------------------------------------------
# TestAuditorPrompt
# ---------------------------------------------------------------------------

class TestAuditorPrompt:
    """Verify the auditor prompt covers spec audit output and Swift compliance."""

    @pytest.fixture(autouse=True)
    def _load_prompt(self):
        self.prompt = get_agents()["auditor"]["prompt"]

    def test_mentions_spec_audit_md_output(self):
        assert "SPEC_AUDIT.md" in self.prompt

    def test_mentions_original_prompt_md(self):
        assert "ORIGINAL_PROMPT.md" in self.prompt

    def test_mentions_swift_plugin_protocol_compliance(self):
        assert "NCBSPlugin" in self.prompt
        assert "Protocol Compliance" in self.prompt

    def test_mentions_host_mode_verification(self):
        assert "Host Mode" in self.prompt

    def test_mentions_read_only_constraint(self):
        assert "read-only" in self.prompt.lower()

    def test_mentions_error_boundary_verification(self):
        assert "error.tsx" in self.prompt

    def test_mentions_loading_verification(self):
        assert "loading.tsx" in self.prompt


# ---------------------------------------------------------------------------
# TestReviewerPrompt
# ---------------------------------------------------------------------------

class TestReviewerPrompt:
    """Verify the reviewer prompt covers design validation with error/loading states."""

    @pytest.fixture(autouse=True)
    def _load_prompt(self):
        self.prompt = get_agents()["reviewer"]["prompt"]

    def test_mentions_error_states_checklist(self):
        assert "Error states" in self.prompt

    def test_mentions_loading_states_checklist(self):
        assert "Loading" in self.prompt or "loading" in self.prompt

    def test_mentions_empty_states_checklist(self):
        assert "Empty states" in self.prompt


# ---------------------------------------------------------------------------
# TestEnricherPrompt
# ---------------------------------------------------------------------------

class TestEnricherPrompt:
    """Verify the enricher prompt covers output format and research tools."""

    @pytest.fixture(autouse=True)
    def _load_prompt(self):
        self.prompt = get_agents()["enricher"]["prompt"]

    def test_mentions_prompt_md_output(self):
        assert "PROMPT.md" in self.prompt

    def test_mentions_web_search_and_web_fetch(self):
        assert "WebSearch" in self.prompt
        assert "WebFetch" in self.prompt

    def test_mentions_platform_context_detection(self):
        assert "Platform Context" in self.prompt


# ---------------------------------------------------------------------------
# TestGetAgentPromptTemplateInjection
# ---------------------------------------------------------------------------

class TestGetAgentPromptTemplateInjection:
    """Verify get_agent_prompt() injects templates based on stack/mode/product_type."""

    def test_builder_with_nextjs_supabase_gets_scaffold_injected(self):
        prompt = get_agent_prompt("builder", stack_id="nextjs-supabase")
        assert "Scaffolding Reference" in prompt

    def test_builder_with_nextjs_supabase_gets_patterns_injected(self):
        prompt = get_agent_prompt("builder", stack_id="nextjs-supabase")
        assert "Code Patterns Reference" in prompt

    def test_builder_with_swift_swiftui_gets_plugin_protocol_injected(self):
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "Plugin Protocol Reference" in prompt

    def test_builder_with_swift_swiftui_plugin_mode_gets_scaffold_plugin(self):
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui", build_mode="plugin")
        assert "Scaffolding Reference" in prompt

    def test_deployer_with_stack_gets_deploy_template_injected(self):
        prompt = get_agent_prompt("deployer", stack_id="nextjs-supabase")
        assert "Deployment Reference" in prompt

    def test_tester_with_stack_gets_test_template_injected(self):
        prompt = get_agent_prompt("tester", stack_id="nextjs-supabase")
        assert "Test Patterns Reference" in prompt

    def test_designer_with_swift_swiftui_gets_plugin_protocol_injected(self):
        prompt = get_agent_prompt("designer", stack_id="swift-swiftui")
        assert "Plugin Protocol Reference" in prompt

    def test_auditor_with_swift_swiftui_gets_plugin_protocol_injected(self):
        prompt = get_agent_prompt("auditor", stack_id="swift-swiftui")
        assert "Plugin Protocol Reference" in prompt

    def test_builder_with_product_type_gets_domain_patterns_injected(self):
        prompt = get_agent_prompt("builder", product_type="marketplace")
        assert "Domain Patterns" in prompt

    def test_designer_with_product_type_gets_domain_patterns_injected(self):
        prompt = get_agent_prompt("designer", product_type="saas")
        assert "Domain Patterns" in prompt

    def test_builder_with_nextjs_supabase_gets_builder_template_injected(self):
        prompt = get_agent_prompt("builder", stack_id="nextjs-supabase")
        assert "Build Process Reference" in prompt

    def test_builder_with_rails_gets_builder_template_injected(self):
        prompt = get_agent_prompt("builder", stack_id="rails")
        assert "Build Process Reference" in prompt

    def test_builder_with_expo_gets_builder_template_injected(self):
        prompt = get_agent_prompt("builder", stack_id="expo-supabase")
        assert "Build Process Reference" in prompt

    def test_unknown_agent_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown agent"):
            get_agent_prompt("nonexistent_agent")
