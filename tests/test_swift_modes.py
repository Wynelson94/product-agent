"""Tests for v7.0 Swift/SwiftUI plugin and host mode features.

Covers:
- AgentState v7.0 fields (build_mode, plugin_packaged)
- Config v7.0 fields (SWIFT_MIN_TESTS_PLUGIN, SWIFT_MIN_TESTS_HOST)
- Stack criteria for swift-swiftui (product_types, features, deployment)
- Stack selection for iOS/plugin/widget ideas
- Orchestrator prompts for plugin and host modes
- Agent definition prompts (builder, designer, auditor, tester, reviewer)
- Domain patterns for plugin_module and plugin_host
"""

import pytest

from agent.state import AgentState, Phase
from agent import config
from agent.stacks.criteria import STACKS, PRODUCT_TYPE_STACKS
from agent.stacks.selector import analyze_product_idea, select_stack
from agent.main import PLUGIN_ORCHESTRATOR_PROMPT, HOST_ORCHESTRATOR_PROMPT
from agent.agents.definitions import get_agents, get_agent_prompt
from agent.domains import get_domain_for_product_type, get_domain_patterns


# ---------------------------------------------------------------------------
# 1. State v7.0 fields
# ---------------------------------------------------------------------------

class TestSwiftStateFields:
    """Tests for v7.0 build_mode and plugin_packaged state fields."""

    def test_build_mode_defaults_to_standard(self):
        """build_mode should default to 'standard'."""
        state = AgentState()
        assert state.build_mode == "standard"

    def test_build_mode_can_be_set_to_plugin(self):
        """build_mode should accept 'plugin'."""
        state = AgentState()
        state.build_mode = "plugin"
        assert state.build_mode == "plugin"

    def test_build_mode_can_be_set_to_host(self):
        """build_mode should accept 'host'."""
        state = AgentState()
        state.build_mode = "host"
        assert state.build_mode == "host"

    def test_plugin_packaged_defaults_to_false(self):
        """plugin_packaged should default to False."""
        state = AgentState()
        assert state.plugin_packaged is False

    def test_plugin_packaged_can_be_set_to_true(self):
        """plugin_packaged should accept True."""
        state = AgentState()
        state.plugin_packaged = True
        assert state.plugin_packaged is True

    def test_to_dict_includes_build_mode(self):
        """to_dict serializes build_mode (fixed in v10.0)."""
        state = AgentState()
        state.build_mode = "plugin"
        data = state.to_dict()
        assert data["build_mode"] == "plugin"

    def test_to_dict_includes_plugin_packaged(self):
        """to_dict serializes plugin_packaged (fixed in v10.0)."""
        state = AgentState()
        state.plugin_packaged = True
        data = state.to_dict()
        assert data["plugin_packaged"] is True


# ---------------------------------------------------------------------------
# 2. Config v7.0 fields
# ---------------------------------------------------------------------------

class TestSwiftConfig:
    """Tests for v7.0 configuration constants."""

    def test_swift_min_tests_plugin_is_8(self):
        """SWIFT_MIN_TESTS_PLUGIN should default to 8."""
        assert config.SWIFT_MIN_TESTS_PLUGIN == 8

    def test_swift_min_tests_host_is_15(self):
        """SWIFT_MIN_TESTS_HOST should default to 15."""
        assert config.SWIFT_MIN_TESTS_HOST == 15

    def test_swift_min_tests_plugin_is_int(self):
        """SWIFT_MIN_TESTS_PLUGIN should be an integer."""
        assert isinstance(config.SWIFT_MIN_TESTS_PLUGIN, int)

    def test_swift_min_tests_host_is_int(self):
        """SWIFT_MIN_TESTS_HOST should be an integer."""
        assert isinstance(config.SWIFT_MIN_TESTS_HOST, int)

    def test_apple_team_id_config_exists(self):
        """APPLE_TEAM_ID config entry should exist (may be None)."""
        assert hasattr(config, "APPLE_TEAM_ID")

    def test_apple_developer_email_config_exists(self):
        """APPLE_DEVELOPER_EMAIL config entry should exist (may be None)."""
        assert hasattr(config, "APPLE_DEVELOPER_EMAIL")


# ---------------------------------------------------------------------------
# 3. Stack criteria for swift-swiftui
# ---------------------------------------------------------------------------

class TestSwiftStackCriteria:
    """Tests for swift-swiftui stack definition and product type mappings."""

    def test_swift_swiftui_exists_in_stacks(self):
        """swift-swiftui must be a registered stack."""
        assert "swift-swiftui" in STACKS

    def test_swift_swiftui_has_6_or_more_product_types(self):
        """swift-swiftui should list at least 6 product types."""
        stack = STACKS["swift-swiftui"]
        assert len(stack.product_types) >= 6

    def test_swift_swiftui_has_6_or_more_features(self):
        """swift-swiftui should list at least 6 features."""
        stack = STACKS["swift-swiftui"]
        assert len(stack.features) >= 6

    def test_product_types_includes_widget(self):
        """swift-swiftui product_types must include 'widget'."""
        stack = STACKS["swift-swiftui"]
        assert "widget" in stack.product_types

    def test_product_types_includes_app_clip(self):
        """swift-swiftui product_types must include 'app_clip'."""
        stack = STACKS["swift-swiftui"]
        assert "app_clip" in stack.product_types

    def test_product_types_includes_utility_app(self):
        """swift-swiftui product_types must include 'utility_app'."""
        stack = STACKS["swift-swiftui"]
        assert "utility_app" in stack.product_types

    def test_product_types_includes_ios_app(self):
        """swift-swiftui product_types must include 'ios_app'."""
        stack = STACKS["swift-swiftui"]
        assert "ios_app" in stack.product_types

    def test_product_types_includes_plugin_module(self):
        """swift-swiftui product_types must include 'plugin_module'."""
        stack = STACKS["swift-swiftui"]
        assert "plugin_module" in stack.product_types

    def test_features_includes_swiftdata(self):
        """swift-swiftui features must include 'swiftdata'."""
        stack = STACKS["swift-swiftui"]
        assert "swiftdata" in stack.features

    def test_features_includes_compression(self):
        """swift-swiftui features must include 'compression'."""
        stack = STACKS["swift-swiftui"]
        assert "compression" in stack.features

    def test_features_includes_swiftui(self):
        """swift-swiftui features must include 'swiftui'."""
        stack = STACKS["swift-swiftui"]
        assert "swiftui" in stack.features

    def test_features_includes_xctest(self):
        """swift-swiftui features must include 'xctest'."""
        stack = STACKS["swift-swiftui"]
        assert "xctest" in stack.features

    def test_deployment_is_testflight(self):
        """swift-swiftui deployment target should be testflight."""
        stack = STACKS["swift-swiftui"]
        assert stack.deployment == "testflight"

    def test_deployment_type_is_mobile(self):
        """swift-swiftui deployment_type should be 'mobile'."""
        stack = STACKS["swift-swiftui"]
        assert stack.deployment_type == "mobile"

    def test_product_type_stacks_widget_maps_to_swift(self):
        """PRODUCT_TYPE_STACKS['widget'] must include swift-swiftui."""
        assert "widget" in PRODUCT_TYPE_STACKS
        assert "swift-swiftui" in PRODUCT_TYPE_STACKS["widget"]

    def test_product_type_stacks_app_clip_maps_to_swift(self):
        """PRODUCT_TYPE_STACKS['app_clip'] must include swift-swiftui."""
        assert "app_clip" in PRODUCT_TYPE_STACKS
        assert "swift-swiftui" in PRODUCT_TYPE_STACKS["app_clip"]

    def test_product_type_stacks_utility_app_maps_to_swift(self):
        """PRODUCT_TYPE_STACKS['utility_app'] must include swift-swiftui."""
        assert "utility_app" in PRODUCT_TYPE_STACKS
        assert "swift-swiftui" in PRODUCT_TYPE_STACKS["utility_app"]

    def test_product_type_stacks_ios_app_maps_to_swift(self):
        """PRODUCT_TYPE_STACKS['ios_app'] must include swift-swiftui."""
        assert "ios_app" in PRODUCT_TYPE_STACKS
        assert "swift-swiftui" in PRODUCT_TYPE_STACKS["ios_app"]

    def test_product_type_stacks_plugin_module_maps_to_swift(self):
        """PRODUCT_TYPE_STACKS['plugin_module'] must include swift-swiftui."""
        assert "plugin_module" in PRODUCT_TYPE_STACKS
        assert "swift-swiftui" in PRODUCT_TYPE_STACKS["plugin_module"]

    def test_complexity_is_medium_high(self):
        """swift-swiftui complexity should be 'medium-high'."""
        stack = STACKS["swift-swiftui"]
        assert stack.complexity == "medium-high"


# ---------------------------------------------------------------------------
# 4. Stack selection for iOS/plugin/widget ideas
# ---------------------------------------------------------------------------

class TestSwiftStackSelection:
    """Tests for keyword-based stack selection towards swift-swiftui."""

    def test_ios_plugin_idea_selects_swift(self):
        """'Build an iOS plugin' should select swift-swiftui."""
        stack_id, _rationale = select_stack("Build an iOS plugin")
        assert stack_id == "swift-swiftui"

    def test_widget_idea_selects_swift(self):
        """'Build a widget' should select swift-swiftui."""
        stack_id, _rationale = select_stack("Build a widget")
        assert stack_id == "swift-swiftui"

    def test_widgetkit_idea_selects_swift(self):
        """'Build a WidgetKit extension' should select swift-swiftui."""
        stack_id, _rationale = select_stack("Build a WidgetKit extension")
        assert stack_id == "swift-swiftui"

    def test_app_clip_idea_selects_swift(self):
        """'Build an app clip' should select swift-swiftui."""
        stack_id, _rationale = select_stack("Build an app clip")
        assert stack_id == "swift-swiftui"

    def test_swift_keyword_idea_selects_swift(self):
        """'Build a Swift note-taking app' should select swift-swiftui."""
        stack_id, _rationale = select_stack("Build a Swift note-taking app")
        assert stack_id == "swift-swiftui"

    def test_analyze_swift_detects_ios_app(self):
        """analyze_product_idea('swift') should include ios_app in product_types."""
        result = analyze_product_idea("Build something with swift")
        assert "ios_app" in result["product_types"]

    def test_analyze_widget_detects_widget_type(self):
        """analyze_product_idea('widget') should include widget in product_types."""
        result = analyze_product_idea("A home screen widget for weather")
        assert "widget" in result["product_types"]

    def test_analyze_swiftdata_detects_feature(self):
        """analyze_product_idea('swiftdata model') should detect swiftdata feature."""
        result = analyze_product_idea("An app using swiftdata model for persistence")
        assert "swiftdata" in result["features"]

    def test_analyze_plugin_detects_plugin_module(self):
        """analyze_product_idea('plugin') should include plugin_module."""
        result = analyze_product_idea("Build a photo gallery plugin")
        assert "plugin_module" in result["product_types"]

    def test_analyze_iphone_detects_ios_app(self):
        """analyze_product_idea('iphone') should include ios_app."""
        result = analyze_product_idea("An iphone fitness tracker")
        assert "ios_app" in result["product_types"]

    def test_analyze_compression_detects_feature(self):
        """analyze_product_idea('compression') should detect compression feature."""
        result = analyze_product_idea("A tool with lossless compression support")
        assert "compression" in result["features"]


# ---------------------------------------------------------------------------
# 5. Orchestrator prompts for plugin and host modes
# ---------------------------------------------------------------------------

class TestSwiftOrchestratorPrompts:
    """Tests for PLUGIN_ORCHESTRATOR_PROMPT and HOST_ORCHESTRATOR_PROMPT."""

    # Plugin orchestrator prompt

    def test_plugin_prompt_mentions_ncbs_plugin(self):
        """Plugin orchestrator prompt should mention NCBSPlugin."""
        assert "NCBSPlugin" in PLUGIN_ORCHESTRATOR_PROMPT

    def test_plugin_prompt_mentions_swift_build(self):
        """Plugin orchestrator prompt should mention 'swift build'."""
        assert "swift build" in PLUGIN_ORCHESTRATOR_PROMPT

    def test_plugin_prompt_mentions_swift_test(self):
        """Plugin orchestrator prompt should mention 'swift test'."""
        assert "swift test" in PLUGIN_ORCHESTRATOR_PROMPT

    def test_plugin_prompt_mentions_minimum_8_tests(self):
        """Plugin orchestrator prompt should specify minimum 8 tests."""
        assert "8 tests" in PLUGIN_ORCHESTRATOR_PROMPT

    def test_plugin_prompt_mentions_plugin_context(self):
        """Plugin orchestrator prompt should mention PluginContext."""
        assert "PluginContext" in PLUGIN_ORCHESTRATOR_PROMPT

    def test_plugin_prompt_mentions_plugin_manifest(self):
        """Plugin orchestrator prompt should mention PluginManifest."""
        assert "PluginManifest" in PLUGIN_ORCHESTRATOR_PROMPT

    def test_plugin_prompt_mentions_spec_audit(self):
        """Plugin orchestrator prompt should reference spec audit."""
        assert "SPEC_AUDIT" in PLUGIN_ORCHESTRATOR_PROMPT

    # Host orchestrator prompt

    def test_host_prompt_mentions_plugin_registry(self):
        """Host orchestrator prompt should mention Plugin registry."""
        assert "Plugin registry" in HOST_ORCHESTRATOR_PROMPT

    def test_host_prompt_mentions_minimum_15_tests(self):
        """Host orchestrator prompt should specify minimum 15 tests."""
        assert "15 tests" in HOST_ORCHESTRATOR_PROMPT

    def test_host_prompt_mentions_dashboard_view(self):
        """Host orchestrator prompt should mention DashboardView."""
        assert "DashboardView" in HOST_ORCHESTRATOR_PROMPT

    def test_host_prompt_mentions_ncbs_plugin_sdk(self):
        """Host orchestrator prompt should mention NCBSPluginSDK."""
        assert "NCBSPluginSDK" in HOST_ORCHESTRATOR_PROMPT

    def test_host_prompt_mentions_swift_build(self):
        """Host orchestrator prompt should mention 'swift build'."""
        assert "swift build" in HOST_ORCHESTRATOR_PROMPT

    def test_host_prompt_mentions_swift_test(self):
        """Host orchestrator prompt should mention 'swift test'."""
        assert "swift test" in HOST_ORCHESTRATOR_PROMPT

    def test_host_prompt_mentions_shared_services(self):
        """Host orchestrator prompt should mention shared services."""
        assert "CompressionService" in HOST_ORCHESTRATOR_PROMPT
        assert "StorageService" in HOST_ORCHESTRATOR_PROMPT
        assert "NetworkService" in HOST_ORCHESTRATOR_PROMPT

    def test_host_prompt_mentions_settings_view(self):
        """Host orchestrator prompt should mention SettingsView."""
        assert "SettingsView" in HOST_ORCHESTRATOR_PROMPT


# ---------------------------------------------------------------------------
# 6. Agent definition prompts (builder, designer, auditor, tester, reviewer)
# ---------------------------------------------------------------------------

class TestSwiftAgentPrompts:
    """Tests for Swift/SwiftUI content in assembled builder prompt (core + templates)."""

    def test_builder_prompt_contains_ncbs_plugin_sdk(self):
        """Assembled Swift builder prompt must include NCBSPluginSDK definition."""
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "NCBSPluginSDK" in prompt

    def test_builder_prompt_contains_plugin_manifest(self):
        """Assembled Swift builder prompt must describe PluginManifest pattern."""
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "PluginManifest" in prompt

    def test_builder_prompt_contains_color_nocloudbs(self):
        """Assembled Swift builder prompt must reference Color+NoCloudBS."""
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "Color+NoCloudBS" in prompt

    def test_builder_prompt_contains_observable(self):
        """Assembled Swift builder prompt must require @Observable macro."""
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "@Observable" in prompt

    def test_builder_prompt_contains_plugin_context_protocol(self):
        """Assembled Swift builder prompt must define PluginContext as a protocol."""
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "protocol PluginContext" in prompt

    def test_builder_prompt_contains_compression_service_protocol(self):
        """Assembled Swift builder prompt must define CompressionServiceProtocol."""
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "CompressionServiceProtocol" in prompt

    def test_builder_prompt_contains_storage_service_protocol(self):
        """Assembled Swift builder prompt must define StorageServiceProtocol."""
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "StorageServiceProtocol" in prompt

    def test_builder_prompt_contains_plugin_permission(self):
        """Assembled Swift builder prompt must define PluginPermission enum."""
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        assert "PluginPermission" in prompt

    def test_auditor_prompt_contains_swift_audit_section(self):
        """Auditor prompt must include Swift/SwiftUI audit section."""
        agents = get_agents()
        assert "Swift/SwiftUI Audit" in agents["auditor"]["prompt"]

    def test_auditor_prompt_contains_protocol_compliance(self):
        """Auditor prompt must mention protocol compliance checks."""
        agents = get_agents()
        assert "Protocol Compliance" in agents["auditor"]["prompt"]

    def test_tester_prompt_contains_swift_section(self):
        """Tester prompt must include Swift/SwiftUI XCTest section."""
        agents = get_agents()
        assert "Swift + SwiftUI" in agents["tester"]["prompt"]

    def test_tester_prompt_contains_plugin_mode_minimum_8(self):
        """Tester prompt must specify minimum 8 tests for plugin mode."""
        agents = get_agents()
        assert "8 tests" in agents["tester"]["prompt"]

    def test_tester_prompt_contains_host_mode_minimum_15(self):
        """Tester prompt must specify minimum 15 tests for host mode."""
        agents = get_agents()
        assert "15 tests" in agents["tester"]["prompt"]

    def test_designer_prompt_contains_swift_design_section(self):
        """Designer prompt must include Swift/SwiftUI design section."""
        agents = get_agents()
        assert "Swift/SwiftUI Design" in agents["designer"]["prompt"]

    def test_designer_prompt_contains_observable_requirement(self):
        """Designer prompt must require @Observable macro."""
        agents = get_agents()
        assert "@Observable" in agents["designer"]["prompt"]

    def test_designer_prompt_mentions_plugin_manifest(self):
        """Designer prompt must mention Manifest in checklist."""
        agents = get_agents()
        assert "Manifest" in agents["designer"]["prompt"]

    def test_reviewer_prompt_contains_swift_validation(self):
        """Reviewer prompt must include Swift/SwiftUI validation checklist."""
        agents = get_agents()
        assert "Swift/SwiftUI Validation" in agents["reviewer"]["prompt"]

    def test_reviewer_prompt_checks_observable(self):
        """Reviewer prompt must flag ObservableObject as incorrect for Swift."""
        agents = get_agents()
        prompt = agents["reviewer"]["prompt"]
        assert "@Observable" in prompt
        assert "ObservableObject" in prompt

    def test_reviewer_prompt_checks_plugin_id_format(self):
        """Reviewer prompt must check for reverse-DNS plugin ID format."""
        agents = get_agents()
        assert "com.nocloudbs" in agents["reviewer"]["prompt"]

    def test_verifier_prompt_contains_swift_verification(self):
        """Verifier prompt must include Swift/SwiftUI verification section."""
        agents = get_agents()
        assert "Swift/SwiftUI Verification" in agents["verifier"]["prompt"]

    def test_analyzer_prompt_mentions_swift_swiftui_stack(self):
        """Analyzer prompt must describe the Swift + SwiftUI stack option."""
        agents = get_agents()
        assert "Swift + SwiftUI" in agents["analyzer"]["prompt"]

    def test_analyzer_prompt_describes_build_modes(self):
        """Analyzer prompt must mention host and plugin build modes."""
        agents = get_agents()
        prompt = agents["analyzer"]["prompt"]
        assert "--mode host" in prompt or "host" in prompt
        assert "--mode plugin" in prompt or "plugin" in prompt


# ---------------------------------------------------------------------------
# 7. get_agent_prompt with stack and build_mode injection
# ---------------------------------------------------------------------------

class TestGetAgentPromptInjection:
    """Tests for get_agent_prompt template and pattern injection."""

    def test_builder_prompt_with_swift_stack_includes_protocol_ref(self):
        """Builder prompt for swift-swiftui should inject plugin protocol reference."""
        prompt = get_agent_prompt("builder", stack_id="swift-swiftui")
        # The prompt should have the base builder prompt content
        assert "NCBSPluginSDK" in prompt

    def test_builder_prompt_with_plugin_mode_and_domain(self):
        """Builder prompt with plugin_module domain should inject domain patterns."""
        prompt = get_agent_prompt(
            "builder",
            stack_id="swift-swiftui",
            build_mode="plugin",
            product_type="plugin_module",
        )
        assert "Domain Patterns" in prompt

    def test_designer_prompt_with_swift_stack_includes_protocol_ref(self):
        """Designer prompt for swift-swiftui should inject plugin protocol reference."""
        prompt = get_agent_prompt("designer", stack_id="swift-swiftui")
        # Designer gets plugin protocol reference for Swift builds
        assert "Swift/SwiftUI Design" in prompt

    def test_auditor_prompt_with_swift_stack_includes_protocol_ref(self):
        """Auditor prompt for swift-swiftui should inject plugin protocol reference."""
        prompt = get_agent_prompt("auditor", stack_id="swift-swiftui")
        assert "Swift/SwiftUI Audit" in prompt


# ---------------------------------------------------------------------------
# 8. Domain patterns for plugin_module and plugin_host
# ---------------------------------------------------------------------------

class TestSwiftDomainPatterns:
    """Tests for v7.0 plugin_module and plugin_host domain patterns."""

    def test_plugin_module_patterns_load(self):
        """plugin_module domain patterns file must load."""
        patterns = get_domain_patterns("plugin_module")
        assert patterns is not None

    def test_plugin_host_patterns_load(self):
        """plugin_host domain patterns file must load."""
        patterns = get_domain_patterns("plugin_host")
        assert patterns is not None

    def test_nocloud_plugin_maps_to_plugin_module(self):
        """nocloud_plugin product type should map to plugin_module domain."""
        assert get_domain_for_product_type("nocloud_plugin") == "plugin_module"

    def test_ios_plugin_maps_to_plugin_module(self):
        """ios_plugin product type should map to plugin_module domain."""
        assert get_domain_for_product_type("ios_plugin") == "plugin_module"

    def test_swift_plugin_maps_to_plugin_module(self):
        """swift_plugin product type should map to plugin_module domain."""
        assert get_domain_for_product_type("swift_plugin") == "plugin_module"

    def test_plugin_module_type_maps_to_plugin_module(self):
        """plugin_module product type should map to plugin_module domain."""
        assert get_domain_for_product_type("plugin_module") == "plugin_module"

    def test_nocloud_maps_to_plugin_host(self):
        """nocloud product type should map to plugin_host domain."""
        assert get_domain_for_product_type("nocloud") == "plugin_host"

    def test_nocloud_bs_maps_to_plugin_host(self):
        """nocloud_bs product type should map to plugin_host domain."""
        assert get_domain_for_product_type("nocloud_bs") == "plugin_host"

    def test_compression_app_maps_to_plugin_host(self):
        """compression_app product type should map to plugin_host domain."""
        assert get_domain_for_product_type("compression_app") == "plugin_host"

    def test_plugin_module_patterns_contain_ncbs_plugin(self):
        """plugin_module patterns must reference NCBSPlugin."""
        patterns = get_domain_patterns("plugin_module")
        assert "NCBSPlugin" in patterns

    def test_plugin_module_patterns_contain_quality_bar(self):
        """plugin_module patterns must mention Quality Bar."""
        patterns = get_domain_patterns("plugin_module")
        assert "Quality Bar" in patterns

    def test_plugin_host_patterns_contain_compression(self):
        """plugin_host patterns must reference compression."""
        patterns = get_domain_patterns("plugin_host")
        assert "compression" in patterns.lower()

    def test_plugin_host_patterns_contain_golden_rules(self):
        """plugin_host patterns must include Golden Rules."""
        patterns = get_domain_patterns("plugin_host")
        assert "Golden Rules" in patterns

    def test_plugin_module_patterns_mention_color_palette(self):
        """plugin_module patterns must describe the host color palette."""
        patterns = get_domain_patterns("plugin_module")
        assert "#CFB53B" in patterns  # gold
        assert "#008080" in patterns  # teal

    def test_plugin_host_patterns_mention_color_palette(self):
        """plugin_host patterns must describe the host color palette."""
        patterns = get_domain_patterns("plugin_host")
        assert "#CFB53B" in patterns  # gold
        assert "#008080" in patterns  # teal
