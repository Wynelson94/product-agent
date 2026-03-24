"""Level 2: Design phase integration tests — real SDK calls.

Runs the Designer agent with a perfect STACK_DECISION.md and validates
the produced DESIGN.md has the expected structure and complexity.

Run: python3 -m pytest tests/stress/test_phase_design.py -v -m stress
"""

import re
import pytest

from agent.state import Phase
from agent.phases import run_phase
from agent.validators import validate_phase_output

from .conftest import make_state, make_progress, populate_project


pytestmark = pytest.mark.stress


class TestDesignPhaseComplex:
    """Complex SaaS prompt with nextjs-prisma should produce thorough design."""

    @pytest.fixture
    def state(self):
        return make_state(
            idea="Build a multi-tenant SaaS for professional services teams to manage "
                 "projects, time tracking, invoicing, and client billing with role-based "
                 "access control (owner/admin/member/viewer), Stripe subscription billing, "
                 "org-scoped RLS isolation, activity audit logs, and tiered pricing plans",
            stack_id="nextjs-prisma",
            phase=Phase.ANALYSIS,
            design_revision=0,
        )

    async def test_produces_design_md(self, project_with_analysis, state):
        """Designer should create DESIGN.md."""
        call, validation = await run_phase(
            Phase.DESIGN, state, project_with_analysis, make_progress()
        )

        assert call.success, f"Design failed: {call.error}"
        assert validation.passed, f"Validation failed: {validation.messages}"
        assert (project_with_analysis / "DESIGN.md").exists()

    async def test_design_has_prisma_models(self, project_with_analysis, state):
        """DESIGN.md should contain Prisma model definitions."""
        await run_phase(Phase.DESIGN, state, project_with_analysis, make_progress())

        content = (project_with_analysis / "DESIGN.md").read_text()
        model_count = len(re.findall(r'^model\s+\w+', content, re.MULTILINE))
        # Multi-tenant SaaS with projects, time tracking, invoicing needs 8+ models
        assert model_count >= 8, f"Expected 8+ models, found {model_count}"

    async def test_design_has_routes(self, project_with_analysis, state):
        """DESIGN.md should define routes/pages."""
        await run_phase(Phase.DESIGN, state, project_with_analysis, make_progress())

        content = (project_with_analysis / "DESIGN.md").read_text().lower()
        # Should mention routing/pages
        assert "route" in content or "page" in content
        # Should have a route table with multiple entries
        route_matches = re.findall(r'\|\s*/[\w/\[\]-]+\s*\|', content)
        assert len(route_matches) >= 5, f"Expected 5+ routes in table, found {len(route_matches)}"

    async def test_design_has_auth_section(self, project_with_analysis, state):
        """DESIGN.md should include auth/RBAC section."""
        await run_phase(Phase.DESIGN, state, project_with_analysis, make_progress())

        content = (project_with_analysis / "DESIGN.md").read_text().lower()
        assert "auth" in content
        # Should mention the 4 roles
        assert "owner" in content
        assert "admin" in content
        assert "member" in content
        assert "viewer" in content

    async def test_design_has_sufficient_length(self, project_with_analysis, state):
        """Complex SaaS design should be substantial (500+ chars)."""
        await run_phase(Phase.DESIGN, state, project_with_analysis, make_progress())

        content = (project_with_analysis / "DESIGN.md").read_text()
        assert len(content) > 500, f"Design too short: {len(content)} chars"

    async def test_design_has_yaml_frontmatter(self, project_with_analysis, state):
        """DESIGN.md should start with YAML front-matter."""
        await run_phase(Phase.DESIGN, state, project_with_analysis, make_progress())

        content = (project_with_analysis / "DESIGN.md").read_text()
        assert content.strip().startswith("---"), "DESIGN.md should start with YAML front-matter"


class TestDesignPhaseSimple:
    """Simple todo app should produce a smaller but valid design."""

    async def test_simple_design_is_valid(self, simple_project):
        populate_project(simple_project, {
            "STACK_DECISION.md": "analysis/stack_decision_supabase.md",
        })
        state = make_state(
            idea="Build a simple todo app with user authentication",
            stack_id="nextjs-supabase",
            phase=Phase.ANALYSIS,
        )

        call, validation = await run_phase(
            Phase.DESIGN, state, simple_project, make_progress()
        )

        assert call.success
        assert validation.passed
        content = (simple_project / "DESIGN.md").read_text()
        # Simple app needs fewer models (2-5)
        model_count = len(re.findall(r'^model\s+\w+|create\s+table', content, re.MULTILINE | re.IGNORECASE))
        assert model_count >= 2, f"Expected at least 2 models/tables, found {model_count}"
