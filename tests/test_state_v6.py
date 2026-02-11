"""Tests for v6.0 state management, config, and domain features."""

import pytest

from agent.state import (
    Phase,
    AgentState,
    create_initial_state,
    get_next_phase,
)
from agent import config


class TestPhaseAudit:
    """Tests for the new AUDIT and ENRICH phases."""

    def test_audit_phase_exists(self):
        """Test that AUDIT phase is defined."""
        assert Phase.AUDIT.value == "audit"

    def test_enrich_phase_exists(self):
        """Test that ENRICH phase is defined."""
        assert Phase.ENRICH.value == "enrich"

    def test_build_transitions_to_audit(self):
        """Test that BUILD transitions to AUDIT (not TEST)."""
        next_phase = get_next_phase(Phase.BUILD)
        assert next_phase == Phase.AUDIT

    def test_audit_transitions_to_test(self):
        """Test that AUDIT transitions to TEST."""
        next_phase = get_next_phase(Phase.AUDIT)
        assert next_phase == Phase.TEST

    def test_enrich_transitions_to_analysis(self):
        """Test that ENRICH transitions to ANALYSIS."""
        next_phase = get_next_phase(Phase.ENRICH)
        assert next_phase == Phase.ANALYSIS

    def test_full_v6_phase_chain(self):
        """Test the full v6.0 phase chain with enrich and audit."""
        chain = [
            Phase.ENRICH,
            Phase.ANALYSIS,
            Phase.DESIGN,
            Phase.REVIEW,  # REVIEW -> BUILD (when approved)
            Phase.BUILD,
            Phase.AUDIT,
            Phase.TEST,
            Phase.DEPLOY,
            Phase.VERIFY,
            Phase.COMPLETE,
        ]
        for i in range(len(chain) - 1):
            current = chain[i]
            expected_next = chain[i + 1]
            actual_next = get_next_phase(current)
            assert actual_next == expected_next, (
                f"Expected {current.value} -> {expected_next.value}, "
                f"got {current.value} -> {actual_next.value}"
            )

    def test_v51_chain_still_works(self):
        """Test that v5.1 chain (without enrich) still works."""
        chain = [
            Phase.INIT,
            Phase.ANALYSIS,
            Phase.DESIGN,
            Phase.REVIEW,
            Phase.BUILD,
            Phase.AUDIT,  # v6.0 inserts audit here
            Phase.TEST,
            Phase.DEPLOY,
            Phase.VERIFY,
            Phase.COMPLETE,
        ]
        for i in range(len(chain) - 1):
            current = chain[i]
            expected_next = chain[i + 1]
            actual_next = get_next_phase(current)
            assert actual_next == expected_next


class TestAgentStateV6Fields:
    """Tests for new v6.0 state fields."""

    def test_has_prompt_enriched_field(self):
        """Test that prompt_enriched field exists with correct default."""
        state = AgentState()
        assert state.prompt_enriched is False

    def test_has_enriched_prompt_field(self):
        """Test that enriched_prompt field exists with correct default."""
        state = AgentState()
        assert state.enriched_prompt is None

    def test_has_enrichment_source_url_field(self):
        """Test that enrichment_source_url field exists with correct default."""
        state = AgentState()
        assert state.enrichment_source_url is None

    def test_has_spec_audit_completed_field(self):
        """Test that spec_audit_completed field exists with correct default."""
        state = AgentState()
        assert state.spec_audit_completed is False

    def test_has_spec_audit_discrepancies_field(self):
        """Test that spec_audit_discrepancies field exists with correct default."""
        state = AgentState()
        assert state.spec_audit_discrepancies == 0

    def test_has_audit_fix_attempted_field(self):
        """Test that audit_fix_attempted field exists with correct default."""
        state = AgentState()
        assert state.audit_fix_attempted is False

    def test_mark_enrichment_complete(self):
        """Test mark_enrichment_complete method."""
        state = AgentState()
        state.mark_enrichment_complete(source_url="https://example.com")
        assert state.prompt_enriched is True
        assert state.enrichment_source_url == "https://example.com"

    def test_mark_enrichment_complete_no_url(self):
        """Test mark_enrichment_complete without URL."""
        state = AgentState()
        state.mark_enrichment_complete()
        assert state.prompt_enriched is True
        assert state.enrichment_source_url is None

    def test_mark_audit_complete(self):
        """Test mark_audit_complete method."""
        state = AgentState()
        state.mark_audit_complete(discrepancies=5)
        assert state.spec_audit_completed is True
        assert state.spec_audit_discrepancies == 5

    def test_mark_audit_complete_no_discrepancies(self):
        """Test mark_audit_complete with zero discrepancies."""
        state = AgentState()
        state.mark_audit_complete()
        assert state.spec_audit_completed is True
        assert state.spec_audit_discrepancies == 0

    def test_mark_audit_fix_attempted(self):
        """Test mark_audit_fix_attempted method."""
        state = AgentState()
        state.mark_audit_fix_attempted()
        assert state.audit_fix_attempted is True


class TestV6Serialization:
    """Tests for v6.0 state serialization."""

    def test_to_dict_includes_v6_fields(self):
        """Test that to_dict includes v6.0 fields."""
        state = AgentState()
        state.prompt_enriched = True
        state.enriched_prompt = "expanded prompt text"
        state.enrichment_source_url = "https://example.com"
        state.spec_audit_completed = True
        state.spec_audit_discrepancies = 3
        state.audit_fix_attempted = True

        data = state.to_dict()
        assert data["prompt_enriched"] is True
        assert data["enriched_prompt"] == "expanded prompt text"
        assert data["enrichment_source_url"] == "https://example.com"
        assert data["spec_audit_completed"] is True
        assert data["spec_audit_discrepancies"] == 3
        assert data["audit_fix_attempted"] is True

    def test_from_dict_loads_v6_fields(self):
        """Test that from_dict loads v6.0 fields."""
        data = {
            "phase": "audit",
            "prompt_enriched": True,
            "enriched_prompt": "full prompt",
            "enrichment_source_url": "https://test.com",
            "spec_audit_completed": True,
            "spec_audit_discrepancies": 7,
            "audit_fix_attempted": False,
        }
        state = AgentState.from_dict(data)
        assert state.phase == Phase.AUDIT
        assert state.prompt_enriched is True
        assert state.enriched_prompt == "full prompt"
        assert state.enrichment_source_url == "https://test.com"
        assert state.spec_audit_completed is True
        assert state.spec_audit_discrepancies == 7
        assert state.audit_fix_attempted is False

    def test_from_dict_backward_compat_missing_v6_fields(self):
        """Test that from_dict handles missing v6.0 fields (old checkpoints)."""
        data = {
            "phase": "build",
            "idea": "test app",
            "project_dir": "/tmp/test",
        }
        state = AgentState.from_dict(data)
        assert state.prompt_enriched is False
        assert state.enriched_prompt is None
        assert state.enrichment_source_url is None
        assert state.spec_audit_completed is False
        assert state.spec_audit_discrepancies == 0
        assert state.audit_fix_attempted is False

    def test_roundtrip_serialization(self):
        """Test full roundtrip: state -> dict -> state."""
        original = AgentState()
        original.phase = Phase.AUDIT
        original.idea = "test product"
        original.project_dir = "/tmp/project"
        original.prompt_enriched = True
        original.enrichment_source_url = "https://example.com"
        original.spec_audit_completed = True
        original.spec_audit_discrepancies = 2
        original.audit_fix_attempted = True

        data = original.to_dict()
        restored = AgentState.from_dict(data)

        assert restored.phase == original.phase
        assert restored.idea == original.idea
        assert restored.prompt_enriched == original.prompt_enriched
        assert restored.enrichment_source_url == original.enrichment_source_url
        assert restored.spec_audit_completed == original.spec_audit_completed
        assert restored.spec_audit_discrepancies == original.spec_audit_discrepancies
        assert restored.audit_fix_attempted == original.audit_fix_attempted


class TestV6Config:
    """Tests for v6.0 configuration flags."""

    def test_enable_prompt_enrichment_exists(self):
        """Test ENABLE_PROMPT_ENRICHMENT flag exists."""
        assert hasattr(config, "ENABLE_PROMPT_ENRICHMENT")
        assert isinstance(config.ENABLE_PROMPT_ENRICHMENT, bool)

    def test_enable_prompt_enrichment_default_off(self):
        """Test ENABLE_PROMPT_ENRICHMENT defaults to False."""
        # Default is "false" in code, so unless env var is set, it should be False
        import os
        if "ENABLE_PROMPT_ENRICHMENT" not in os.environ:
            assert config.ENABLE_PROMPT_ENRICHMENT is False

    def test_enable_spec_audit_exists(self):
        """Test ENABLE_SPEC_AUDIT flag exists."""
        assert hasattr(config, "ENABLE_SPEC_AUDIT")
        assert isinstance(config.ENABLE_SPEC_AUDIT, bool)

    def test_enable_functional_tests_exists(self):
        """Test ENABLE_FUNCTIONAL_TESTS flag exists."""
        assert hasattr(config, "ENABLE_FUNCTIONAL_TESTS")
        assert isinstance(config.ENABLE_FUNCTIONAL_TESTS, bool)

    def test_pass_original_prompt_to_builder_exists(self):
        """Test PASS_ORIGINAL_PROMPT_TO_BUILDER flag exists."""
        assert hasattr(config, "PASS_ORIGINAL_PROMPT_TO_BUILDER")
        assert isinstance(config.PASS_ORIGINAL_PROMPT_TO_BUILDER, bool)

    def test_max_audit_fix_attempts_exists(self):
        """Test MAX_AUDIT_FIX_ATTEMPTS exists and is an int."""
        assert hasattr(config, "MAX_AUDIT_FIX_ATTEMPTS")
        assert isinstance(config.MAX_AUDIT_FIX_ATTEMPTS, int)
        assert config.MAX_AUDIT_FIX_ATTEMPTS >= 1


class TestContentSiteDomain:
    """Tests for the content_site domain (v6.0)."""

    def test_content_site_patterns_load(self):
        """Test that content_site domain patterns file can be loaded."""
        from agent.domains import get_domain_patterns
        patterns = get_domain_patterns("content_site")
        assert patterns is not None
        assert "Content Site" in patterns
        assert "static-first" in patterns.lower() or "Static" in patterns

    def test_content_site_in_domain_list(self):
        """Test that content_site appears in available domains."""
        from agent.domains import list_domains
        domains = list_domains()
        assert "content_site" in domains

    def test_content_site_mapping(self):
        """Test that content_site product types map correctly."""
        from agent.domains import get_domain_for_product_type
        assert get_domain_for_product_type("content_site") == "content_site"
        assert get_domain_for_product_type("nonprofit") == "content_site"
        assert get_domain_for_product_type("marketing_site") == "content_site"
        assert get_domain_for_product_type("portfolio") == "content_site"
        assert get_domain_for_product_type("blog") == "content_site"
        assert get_domain_for_product_type("landing_page") == "content_site"
        assert get_domain_for_product_type("event_site") == "content_site"

    def test_existing_domains_unchanged(self):
        """Test that existing domain mappings still work."""
        from agent.domains import get_domain_for_product_type
        assert get_domain_for_product_type("marketplace") == "marketplace"
        assert get_domain_for_product_type("saas") == "saas"
        assert get_domain_for_product_type("internal_tool") == "internal_tool"

    def test_content_site_stack_mapping(self):
        """Test that content site product types map to correct stacks."""
        from agent.stacks.criteria import PRODUCT_TYPE_STACKS
        assert "content_site" in PRODUCT_TYPE_STACKS
        assert "nonprofit" in PRODUCT_TYPE_STACKS
        assert "portfolio" in PRODUCT_TYPE_STACKS
        assert "nextjs-supabase" in PRODUCT_TYPE_STACKS["content_site"]
        assert "nextjs-supabase" in PRODUCT_TYPE_STACKS["nonprofit"]

    def test_content_site_keyword_detection(self):
        """Test that content site keywords are detected in selector."""
        from agent.stacks.selector import analyze_product_idea
        result = analyze_product_idea("Build a nonprofit website for a charity")
        assert "nonprofit" in result["product_types"]

    def test_event_site_keyword_detection(self):
        """Test that event site keywords are detected in selector."""
        from agent.stacks.selector import analyze_product_idea
        result = analyze_product_idea("Build a site with volunteer trips and schedule")
        assert "event_site" in result["product_types"]


class TestAgentDefinitionsV6:
    """Tests for v6.0 agent definitions."""

    def test_auditor_agent_registered(self):
        """Test that auditor agent is registered."""
        from agent.agents.definitions import get_agents
        agents = get_agents()
        assert "auditor" in agents
        assert "Read" in agents["auditor"]["tools"]
        assert "Glob" in agents["auditor"]["tools"]
        assert "Grep" in agents["auditor"]["tools"]
        assert "Write" in agents["auditor"]["tools"]

    def test_enricher_agent_registered(self):
        """Test that enricher agent is registered."""
        from agent.agents.definitions import get_agents
        agents = get_agents()
        assert "enricher" in agents
        assert "Read" in agents["enricher"]["tools"]
        assert "Write" in agents["enricher"]["tools"]
        assert "WebSearch" in agents["enricher"]["tools"]
        assert "WebFetch" in agents["enricher"]["tools"]

    def test_auditor_is_read_only(self):
        """Test that auditor doesn't have Edit or Bash tools."""
        from agent.agents.definitions import get_agents
        agents = get_agents()
        assert "Edit" not in agents["auditor"]["tools"]
        assert "Bash" not in agents["auditor"]["tools"]

    def test_builder_prompt_references_original_prompt(self):
        """Test that builder prompt instructs reading ORIGINAL_PROMPT.md."""
        from agent.agents.definitions import get_agents
        agents = get_agents()
        assert "ORIGINAL_PROMPT.md" in agents["builder"]["prompt"]

    def test_tester_prompt_references_original_prompt(self):
        """Test that tester prompt instructs reading ORIGINAL_PROMPT.md."""
        from agent.agents.definitions import get_agents
        agents = get_agents()
        assert "ORIGINAL_PROMPT.md" in agents["tester"]["prompt"]

    def test_tester_minimum_tests_increased(self):
        """Test that tester minimum is now 11 tests."""
        from agent.agents.definitions import get_agents
        agents = get_agents()
        assert "11 tests" in agents["tester"]["prompt"]

    def test_existing_agents_still_present(self):
        """Test that all v5.1 agents are still registered."""
        from agent.agents.definitions import get_agents
        agents = get_agents()
        expected = ["analyzer", "designer", "reviewer", "builder",
                    "deployer", "enhancer", "verifier", "tester"]
        for name in expected:
            assert name in agents, f"Missing agent: {name}"
