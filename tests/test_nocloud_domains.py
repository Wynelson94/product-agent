"""Tests for NoCloud BS domain mappings and patterns (v7.0)."""

import pytest

from agent.domains import get_domain_for_product_type, get_domain_patterns, list_domains
from agent.stacks.criteria import PRODUCT_TYPE_STACKS


class TestNoCloudDomainMappings:
    """NoCloud product types map to the correct domains."""

    def test_nocloud_maps_to_plugin_host(self):
        assert get_domain_for_product_type("nocloud") == "plugin_host"

    def test_nocloud_bs_maps_to_plugin_host(self):
        assert get_domain_for_product_type("nocloud_bs") == "plugin_host"

    def test_compression_app_maps_to_plugin_host(self):
        assert get_domain_for_product_type("compression_app") == "plugin_host"

    def test_file_manager_maps_to_plugin_host(self):
        assert get_domain_for_product_type("file_manager") == "plugin_host"

    def test_file_viewer_maps_to_plugin_host(self):
        assert get_domain_for_product_type("file_viewer") == "plugin_host"


class TestPluginModuleMappings:
    """Plugin module aliases map to plugin_module domain."""

    def test_nocloud_plugin_maps_to_plugin_module(self):
        assert get_domain_for_product_type("nocloud_plugin") == "plugin_module"

    def test_swift_plugin_maps_to_plugin_module(self):
        assert get_domain_for_product_type("swift_plugin") == "plugin_module"

    def test_ios_plugin_maps_to_plugin_module(self):
        assert get_domain_for_product_type("ios_plugin") == "plugin_module"

    def test_plugin_module_maps_to_plugin_module(self):
        assert get_domain_for_product_type("plugin_module") == "plugin_module"


class TestNoCloudPatternsLoad:
    """Domain pattern files load and contain expected NoCloud content."""

    def test_plugin_host_patterns_load(self):
        patterns = get_domain_patterns("plugin_host")
        assert patterns is not None

    def test_plugin_host_patterns_contain_nocloud(self):
        patterns = get_domain_patterns("plugin_host")
        assert "NoCloud BS" in patterns

    def test_plugin_host_patterns_contain_compression(self):
        patterns = get_domain_patterns("plugin_host")
        assert "compression" in patterns.lower()

    def test_plugin_host_patterns_contain_golden_rules(self):
        patterns = get_domain_patterns("plugin_host")
        assert "Golden Rules" in patterns

    def test_plugin_host_patterns_contain_algorithm_strategy(self):
        patterns = get_domain_patterns("plugin_host")
        assert "LZ4" in patterns
        assert "zstd" in patterns
        assert "LZMA" in patterns
        assert "LZFSE" in patterns

    def test_plugin_module_patterns_load(self):
        patterns = get_domain_patterns("plugin_module")
        assert patterns is not None

    def test_plugin_module_patterns_contain_ncbs_plugin(self):
        patterns = get_domain_patterns("plugin_module")
        assert "NCBSPlugin" in patterns

    def test_plugin_module_patterns_contain_quality_bar(self):
        patterns = get_domain_patterns("plugin_module")
        assert "Quality Bar" in patterns

    def test_plugin_module_patterns_contain_offline_enforcement(self):
        patterns = get_domain_patterns("plugin_module")
        assert "Offline-First Enforcement" in patterns

    def test_plugin_module_patterns_contain_golden_rules(self):
        patterns = get_domain_patterns("plugin_module")
        assert "Golden Rules" in patterns


class TestNoCloudDomainsList:
    """NoCloud domains appear in list_domains()."""

    def test_plugin_host_in_domains(self):
        domains = list_domains()
        assert "plugin_host" in domains

    def test_plugin_module_in_domains(self):
        domains = list_domains()
        assert "plugin_module" in domains


class TestNoCloudStackMappings:
    """NoCloud product types map to swift-swiftui stack."""

    def test_nocloud_stack(self):
        assert "swift-swiftui" in PRODUCT_TYPE_STACKS["nocloud"]

    def test_nocloud_bs_stack(self):
        assert "swift-swiftui" in PRODUCT_TYPE_STACKS["nocloud_bs"]

    def test_compression_app_stack(self):
        assert "swift-swiftui" in PRODUCT_TYPE_STACKS["compression_app"]

    def test_file_manager_stack(self):
        assert "swift-swiftui" in PRODUCT_TYPE_STACKS["file_manager"]

    def test_file_viewer_stack(self):
        assert "swift-swiftui" in PRODUCT_TYPE_STACKS["file_viewer"]


class TestExistingMappingsUnchanged:
    """Verify existing domain mappings were not broken."""

    def test_marketplace_unchanged(self):
        assert get_domain_for_product_type("marketplace") == "marketplace"

    def test_saas_unchanged(self):
        assert get_domain_for_product_type("saas") == "saas"

    def test_internal_tool_unchanged(self):
        assert get_domain_for_product_type("internal_tool") == "internal_tool"

    def test_content_site_unchanged(self):
        assert get_domain_for_product_type("content_site") == "content_site"

    def test_nonprofit_unchanged(self):
        assert get_domain_for_product_type("nonprofit") == "content_site"

    def test_unknown_returns_none(self):
        assert get_domain_for_product_type("unknown_type") is None
