"""Level 2: Analysis phase integration tests — real SDK calls.

Runs the Analyzer agent with controlled prompts and validates it selects
the correct stack. Each test is ~1-2 minutes of SDK time.

Run: python3 -m pytest tests/stress/test_phase_analysis.py -v -m stress
"""

import re
import pytest

from agent.state import Phase
from agent.phases import run_phase
from agent.validators import validate_phase_output

from .conftest import make_state, make_progress


pytestmark = pytest.mark.stress


class TestAnalysisPhaseMultiTenant:
    """Complex multi-tenant prompt should select nextjs-prisma."""

    @pytest.fixture
    def state(self):
        return make_state(
            idea="Build a multi-tenant SaaS for professional services teams to manage "
                 "projects, time tracking, invoicing, and client billing with role-based "
                 "access control (owner/admin/member/viewer), Stripe subscription billing, "
                 "org-scoped RLS isolation, activity audit logs, and tiered pricing plans",
            stack_id=None,  # Don't force — let analyzer choose
            phase=Phase.INIT,
        )

    async def test_selects_prisma_stack(self, stress_project, state):
        """Multi-tenant SaaS with complex relations → nextjs-prisma."""
        call, validation = await run_phase(
            Phase.ANALYSIS, state, stress_project, make_progress()
        )

        assert call.success, f"Analysis failed: {call.error}"
        assert validation.passed, f"Validation failed: {validation.messages}"
        assert (stress_project / "STACK_DECISION.md").exists()

        # Verify stack selection
        stack_id = validation.extracted.get("stack_id")
        assert stack_id == "nextjs-prisma", f"Expected nextjs-prisma, got {stack_id}"

    async def test_output_contains_rationale(self, stress_project, state):
        """STACK_DECISION.md should explain WHY prisma was chosen."""
        await run_phase(Phase.ANALYSIS, state, stress_project, make_progress())

        content = (stress_project / "STACK_DECISION.md").read_text()
        content_lower = content.lower()
        # Should mention multi-tenant and complex relations as reasons
        assert "multi" in content_lower or "tenant" in content_lower
        assert len(content) > 200  # Not a stub


class TestAnalysisPhaseSimple:
    """Simple app prompt should select default nextjs-supabase."""

    async def test_todo_app_selects_supabase(self, simple_project):
        state = make_state(
            idea="Build a simple todo app with user authentication",
            stack_id=None,
            phase=Phase.INIT,
        )
        call, validation = await run_phase(
            Phase.ANALYSIS, state, simple_project, make_progress()
        )

        assert call.success
        stack_id = validation.extracted.get("stack_id")
        # Simple apps should default to supabase (most tested, simplest)
        assert stack_id == "nextjs-supabase", f"Expected nextjs-supabase, got {stack_id}"


class TestAnalysisPhaseEdgeCases:
    """Edge cases in stack selection."""

    async def test_mobile_keywords_select_expo(self, stress_project):
        state = make_state(
            idea="Build a mobile app for tracking fitness goals with push notifications",
            stack_id=None,
            phase=Phase.INIT,
        )
        call, validation = await run_phase(
            Phase.ANALYSIS, state, stress_project, make_progress()
        )

        assert call.success
        stack_id = validation.extracted.get("stack_id")
        assert stack_id == "expo-supabase", f"Expected expo-supabase, got {stack_id}"

    async def test_blog_keywords_select_astro(self, stress_project):
        state = make_state(
            idea="Build a blog with markdown posts and a documentation site",
            stack_id=None,
            phase=Phase.INIT,
        )
        call, validation = await run_phase(
            Phase.ANALYSIS, state, stress_project, make_progress()
        )

        assert call.success
        stack_id = validation.extracted.get("stack_id")
        # Should pick astro (content-first) or nextjs-supabase
        assert stack_id in ("astro", "nextjs-supabase"), f"Unexpected stack: {stack_id}"
