"""Level 2: Review phase integration tests — real SDK calls.

Runs the Reviewer agent with a perfect DESIGN.md and validates it either
approves or provides actionable feedback.

Run: python3 -m pytest tests/stress/test_phase_review.py -v -m stress
"""

import pytest

from agent.state import Phase
from agent.phases import run_phase
from agent.validators import validate_phase_output

from .conftest import make_state, make_progress


pytestmark = pytest.mark.stress


class TestReviewPhaseWithGoodDesign:
    """Review of the real stress test DESIGN.md (3-revision version)."""

    @pytest.fixture
    def state(self):
        return make_state(
            idea="Build a multi-tenant SaaS for professional services teams to manage "
                 "projects, time tracking, invoicing, and client billing with role-based "
                 "access control (owner/admin/member/viewer), Stripe subscription billing, "
                 "org-scoped RLS isolation, activity audit logs, and tiered pricing plans",
            stack_id="nextjs-prisma",
            phase=Phase.DESIGN,
            design_revision=0,
        )

    async def test_produces_review_md(self, project_with_design, state):
        """Reviewer should create REVIEW.md."""
        call, validation = await run_phase(
            Phase.REVIEW, state, project_with_design, make_progress()
        )

        assert call.success, f"Review failed: {call.error}"
        assert (project_with_design / "REVIEW.md").exists()

    async def test_extracts_verdict(self, project_with_design, state):
        """Validator should extract approved/needs_revision verdict."""
        call, validation = await run_phase(
            Phase.REVIEW, state, project_with_design, make_progress()
        )

        assert call.success
        # Verdict should be extractable (either approved or needs_revision)
        approved = validation.extracted.get("approved")
        assert approved is not None, "Verdict not extracted from REVIEW.md"

    async def test_review_has_checklist(self, project_with_design, state):
        """REVIEW.md should contain a structured checklist."""
        await run_phase(Phase.REVIEW, state, project_with_design, make_progress())

        content = (project_with_design / "REVIEW.md").read_text().lower()
        # Should evaluate data model, routes, components, security
        checks_found = sum(1 for term in ["data model", "route", "component", "security", "auth"]
                          if term in content)
        assert checks_found >= 3, f"Review should check at least 3 areas, found {checks_found}"

    async def test_if_rejected_provides_feedback(self, project_with_design, state):
        """If NEEDS_REVISION, should include specific actionable feedback."""
        call, validation = await run_phase(
            Phase.REVIEW, state, project_with_design, make_progress()
        )

        if validation.extracted.get("approved") is False:
            content = (project_with_design / "REVIEW.md").read_text()
            # Rejection should include specific issues, not just "needs work"
            assert len(content) > 200, "Rejection feedback should be substantial"
            # Should reference specific sections or issues
            assert "issue" in content.lower() or "fix" in content.lower() or "missing" in content.lower()


class TestReviewPhaseLenient:
    """Test that lenient mode (final revision context) encourages approval."""

    async def test_lenient_context_encourages_approval(self, project_with_design):
        state = make_state(
            stack_id="nextjs-prisma",
            phase=Phase.DESIGN,
            design_revision=2,  # Final revision
        )

        # Inject the lenient context that the orchestrator would inject
        lenient_context = (
            "FINAL REVIEW: Only block on CRITICAL structural issues "
            "(missing tables, broken relationships, security holes). "
            "Non-blocking recommendations should be noted but the design "
            "should be APPROVED so the build can proceed."
        )

        call, validation = await run_phase(
            Phase.REVIEW, state, project_with_design, make_progress(),
            retry_context=lenient_context,
        )

        assert call.success
        # With lenient context and a good design, should approve
        # (not guaranteed, but highly likely)
        approved = validation.extracted.get("approved")
        if not approved:
            content = (project_with_design / "REVIEW.md").read_text()
            # If still rejected, the issue should be genuinely CRITICAL
            assert "critical" in content.lower(), (
                "Lenient mode rejected without CRITICAL issue — reviewer may be too strict"
            )
