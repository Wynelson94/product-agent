"""Tests for enhancement mode (v10.2).

Validates:
- Phase.ENHANCE exists in the enum and is registered
- Enhancement validator checks DESIGN.md for new features
- Orchestrator skips Analysis + Design/Review in enhancement mode
- _setup_enhancement_mode copies design and infers stack
- Phase ordering includes ENHANCE
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent.state import Phase, AgentState
from agent.validators import validate_phase_output, ValidationResult
from agent.orchestrator import (
    BuildConfig,
    _get_phase_count,
    _setup_enhancement_mode,
    _PHASE_ORDER,
)
from agent.phases import get_phase_config, get_all_phase_configs


# =====================================================================
# 1. Phase enum and registration
# =====================================================================


class TestEnhancePhaseExists:
    """Verify Phase.ENHANCE exists and is properly registered."""

    def test_enhance_in_phase_enum(self):
        assert hasattr(Phase, "ENHANCE")
        assert Phase.ENHANCE.value == "enhance"

    def test_enhance_phase_registered(self):
        config = get_phase_config(Phase.ENHANCE)
        assert config is not None

    def test_enhance_agent_name(self):
        config = get_phase_config(Phase.ENHANCE)
        assert config.agent_name == "enhancer"

    def test_enhance_display_name(self):
        config = get_phase_config(Phase.ENHANCE)
        assert config.display_name == "Enhancing design"

    def test_enhance_max_turns(self):
        config = get_phase_config(Phase.ENHANCE)
        assert config.max_turns == 40

    def test_enhance_tools(self):
        config = get_phase_config(Phase.ENHANCE)
        assert "Read" in config.tools
        assert "Write" in config.tools
        assert "Edit" in config.tools

    def test_enhance_required_artifacts(self):
        config = get_phase_config(Phase.ENHANCE)
        assert "DESIGN.md" in config.required_artifacts

    def test_ten_phases_total(self):
        """Enhancement adds a 10th registered phase."""
        configs = get_all_phase_configs()
        assert len(configs) == 10


# =====================================================================
# 2. Enhancement validator
# =====================================================================


class TestEnhanceValidator:
    """Test _validate_enhance checks DESIGN.md for enhancement evidence."""

    def test_missing_design_fails(self, tmp_path):
        result = validate_phase_output(Phase.ENHANCE, tmp_path)
        assert not result.passed

    def test_short_design_fails(self, tmp_path):
        (tmp_path / "DESIGN.md").write_text("# Design\nToo short.")
        result = validate_phase_output(Phase.ENHANCE, tmp_path)
        assert not result.passed

    def test_design_with_new_markers_passes(self, tmp_path):
        content = "# Enhanced Design\n" + "x " * 200 + "\n## New Feature (NEW)\nSome feature."
        (tmp_path / "DESIGN.md").write_text(content)
        result = validate_phase_output(Phase.ENHANCE, tmp_path)
        assert result.passed
        assert result.extracted.get("new_items", 0) >= 1

    def test_design_with_enhancement_keyword_passes(self, tmp_path):
        content = "# Design\n" + "x " * 200 + "\n## Enhanced Section\nThis was enhanced."
        (tmp_path / "DESIGN.md").write_text(content)
        result = validate_phase_output(Phase.ENHANCE, tmp_path)
        assert result.passed

    def test_design_without_markers_warns(self, tmp_path):
        content = "# Design\n" + "x " * 200 + "\n## Section\nPlain content."
        (tmp_path / "DESIGN.md").write_text(content)
        result = validate_phase_output(Phase.ENHANCE, tmp_path)
        # Should pass but with a warning
        assert result.passed
        has_warning = any("no (new) markers" in m.lower() for m in result.messages)
        assert has_warning

    def test_counts_multiple_new_markers(self, tmp_path):
        content = "# Design\n" + "x " * 200
        content += "\n## Feature A (NEW)\n## Feature B (NEW)\n## Feature C (NEW)"
        (tmp_path / "DESIGN.md").write_text(content)
        result = validate_phase_output(Phase.ENHANCE, tmp_path)
        assert result.passed
        assert result.extracted.get("new_items") == 3


# =====================================================================
# 3. Orchestrator integration
# =====================================================================


class TestEnhancementModePhaseCount:
    """Enhancement mode adjusts phase count correctly."""

    def test_enhancement_mode_7_phases(self):
        # Standard (9) - analysis - design - review + enhance = 7
        cfg = BuildConfig(mode="enhancement")
        assert _get_phase_count(cfg) == 7

    def test_enhancement_with_enrich_8_phases(self):
        cfg = BuildConfig(mode="enhancement", enrich=True)
        assert _get_phase_count(cfg) == 8

    def test_standard_mode_9_phases(self):
        cfg = BuildConfig()
        assert _get_phase_count(cfg) == 9


class TestSetupEnhancementMode:
    """Test _setup_enhancement_mode copies design and infers stack."""

    def test_copies_design_file(self, tmp_path):
        source = tmp_path / "source_design.md"
        source.write_text("# Original Design\nWith Supabase tables.")
        project = tmp_path / "project"
        project.mkdir()

        state = AgentState()
        cfg = BuildConfig(mode="enhancement", design_file=str(source))
        _setup_enhancement_mode(state, cfg, project)

        assert (project / "DESIGN.md").exists()
        assert "Original Design" in (project / "DESIGN.md").read_text()

    def test_infers_supabase_stack(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n" + "x " * 100 + "\nUsing Supabase RLS policies.")
        project = tmp_path / "project"
        project.mkdir()

        state = AgentState()
        cfg = BuildConfig(mode="enhancement", design_file=str(source))
        _setup_enhancement_mode(state, cfg, project)

        assert state.stack_id == "nextjs-supabase"

    def test_infers_prisma_stack(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n" + "x " * 100 + "\nUsing Prisma schema.")
        project = tmp_path / "project"
        project.mkdir()

        state = AgentState()
        cfg = BuildConfig(mode="enhancement", design_file=str(source))
        _setup_enhancement_mode(state, cfg, project)

        assert state.stack_id == "nextjs-prisma"

    def test_infers_swift_stack(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n" + "x " * 100 + "\nUsing Swift and SwiftUI views.")
        project = tmp_path / "project"
        project.mkdir()

        state = AgentState()
        cfg = BuildConfig(mode="enhancement", design_file=str(source))
        _setup_enhancement_mode(state, cfg, project)

        assert state.stack_id == "swift-swiftui"

    def test_defaults_to_nextjs_supabase(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n" + "x " * 100 + "\nA generic web app.")
        project = tmp_path / "project"
        project.mkdir()

        state = AgentState()
        cfg = BuildConfig(mode="enhancement", design_file=str(source))
        _setup_enhancement_mode(state, cfg, project)

        assert state.stack_id == "nextjs-supabase"

    def test_sets_enhancement_mode_flag(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n" + "x " * 100)
        project = tmp_path / "project"
        project.mkdir()

        state = AgentState()
        cfg = BuildConfig(mode="enhancement", design_file=str(source),
                          enhance_features=["dashboards", "board-views"])
        _setup_enhancement_mode(state, cfg, project)

        assert state.enhancement_mode is True
        assert state.enhance_features == ["dashboards", "board-views"]

    def test_writes_stack_decision(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n" + "x " * 100)
        project = tmp_path / "project"
        project.mkdir()

        state = AgentState()
        cfg = BuildConfig(mode="enhancement", design_file=str(source))
        _setup_enhancement_mode(state, cfg, project)

        assert (project / "STACK_DECISION.md").exists()
        content = (project / "STACK_DECISION.md").read_text()
        assert "Enhancement" in content

    def test_respects_explicit_stack(self, tmp_path):
        source = tmp_path / "design.md"
        source.write_text("# Design\n" + "x " * 100 + "\nUsing Supabase.")
        project = tmp_path / "project"
        project.mkdir()

        state = AgentState()
        cfg = BuildConfig(mode="enhancement", design_file=str(source), stack="rails")
        _setup_enhancement_mode(state, cfg, project)

        # Explicit stack override should win
        assert state.stack_id == "rails"


# =====================================================================
# 4. Phase ordering
# =====================================================================


class TestEnhancePhaseOrdering:
    """ENHANCE phase is in the ordering map at the right position."""

    def test_enhance_in_phase_order(self):
        assert Phase.ENHANCE in _PHASE_ORDER

    def test_enhance_same_as_review(self):
        # ENHANCE replaces Design+Review in enhancement mode
        assert _PHASE_ORDER[Phase.ENHANCE] == _PHASE_ORDER[Phase.REVIEW]

    def test_enhance_before_build(self):
        assert _PHASE_ORDER[Phase.ENHANCE] < _PHASE_ORDER[Phase.BUILD]

    def test_enhance_after_analysis(self):
        assert _PHASE_ORDER[Phase.ENHANCE] > _PHASE_ORDER[Phase.ANALYSIS]


# =====================================================================
# 5. State serialization
# =====================================================================


class TestEnhanceStateSerialization:
    """Phase.ENHANCE roundtrips through JSON serialization."""

    def test_enhance_phase_serializes(self):
        state = AgentState()
        state.phase = Phase.ENHANCE
        d = state.to_dict()
        assert d["phase"] == "enhance"

    def test_enhance_phase_deserializes(self):
        state = AgentState.from_dict({"phase": "enhance"})
        assert state.phase == Phase.ENHANCE

    def test_enhancement_mode_roundtrip(self):
        state = AgentState()
        state.enhancement_mode = True
        state.enhance_features = ["dashboards"]
        state.phase = Phase.ENHANCE

        restored = AgentState.from_dict(state.to_dict())
        assert restored.enhancement_mode is True
        assert restored.enhance_features == ["dashboards"]
        assert restored.phase == Phase.ENHANCE


# =====================================================================
# 6. Build prompt
# =====================================================================


class TestEnhanceBuildPrompt:
    """Enhancement phase builds correct prompts."""

    def test_prompt_includes_features(self, tmp_path):
        config = get_phase_config(Phase.ENHANCE)
        state = AgentState()
        state.idea = "A task management app"
        state.enhance_features = ["board-views", "dashboards"]

        prompt = config.build_prompt(state, tmp_path)
        assert "board-views" in prompt
        assert "dashboards" in prompt

    def test_prompt_includes_idea(self, tmp_path):
        config = get_phase_config(Phase.ENHANCE)
        state = AgentState()
        state.idea = "A CRM for dentists"
        state.enhance_features = []

        prompt = config.build_prompt(state, tmp_path)
        assert "CRM for dentists" in prompt

    def test_prompt_includes_instructions(self, tmp_path):
        config = get_phase_config(Phase.ENHANCE)
        state = AgentState()
        state.idea = "Test app"
        state.enhance_features = ["feature1"]

        prompt = config.build_prompt(state, tmp_path)
        assert "PRESERVING" in prompt
        assert "(NEW)" in prompt
