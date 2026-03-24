"""Level 2: Audit phase integration tests — real SDK calls.

Runs the Auditor agent against built source code and validates it
produces accurate requirement coverage reports.

Prerequisite: Build phase must have produced source code in the project dir.
For isolated testing, use the stress-test-proserv fixtures.

Run: python3 -m pytest tests/stress/test_phase_audit.py -v -m stress
"""

import pytest
from pathlib import Path

from agent.state import Phase
from agent.phases import run_phase
from agent.validators import validate_phase_output

from .conftest import make_state, make_progress, populate_project, FIXTURES_DIR


pytestmark = pytest.mark.stress


# Path to the actual stress test output (has real source code)
STRESS_TEST_PROJECT = Path(__file__).parent.parent.parent / "projects" / "stress-test-proserv"


@pytest.fixture
def project_with_source(tmp_path):
    """Create a project with real source code from the stress test.

    Copies key artifacts (not node_modules) for the auditor to inspect.
    Returns None if stress-test-proserv doesn't exist (skip test).
    """
    if not STRESS_TEST_PROJECT.exists():
        pytest.skip("stress-test-proserv not found — run stress test first")

    import shutil
    project = tmp_path / "audit-test"
    project.mkdir()

    # Copy artifacts the auditor needs
    for name in ["ORIGINAL_PROMPT.md", "STACK_DECISION.md", "DESIGN.md", "package.json"]:
        src = STRESS_TEST_PROJECT / name
        if src.exists():
            shutil.copy(src, project / name)

    # Copy source directory (not node_modules)
    src_dir = STRESS_TEST_PROJECT / "src"
    if src_dir.exists():
        shutil.copytree(src_dir, project / "src")

    prisma_dir = STRESS_TEST_PROJECT / "prisma"
    if prisma_dir.exists():
        shutil.copytree(prisma_dir, project / "prisma")

    return project


class TestAuditPhaseWithRealSource:
    """Audit against real stress test source code."""

    async def test_produces_spec_audit(self, project_with_source):
        state = make_state(
            idea="Build a multi-tenant SaaS for professional services teams",
            stack_id="nextjs-prisma",
            phase=Phase.BUILD,
            spec_audit_completed=False,
        )

        call, validation = await run_phase(
            Phase.AUDIT, state, project_with_source, make_progress()
        )

        assert call.success, f"Audit failed: {call.error}"
        assert (project_with_source / "SPEC_AUDIT.md").exists()

    async def test_extracts_requirements_count(self, project_with_source):
        state = make_state(
            stack_id="nextjs-prisma",
            phase=Phase.BUILD,
        )

        call, validation = await run_phase(
            Phase.AUDIT, state, project_with_source, make_progress()
        )

        assert call.success
        # Should extract numeric requirement counts
        met = validation.extracted.get("requirements_met")
        total = validation.extracted.get("requirements_total")
        assert met is not None or total is not None, (
            "Auditor should report requirements met/total"
        )

    async def test_identity_matches_prompt(self, project_with_source):
        """v12.0: Auditor should verify the project matches ORIGINAL_PROMPT.md."""
        state = make_state(
            stack_id="nextjs-prisma",
            phase=Phase.BUILD,
        )

        await run_phase(Phase.AUDIT, state, project_with_source, make_progress())

        content = (project_with_source / "SPEC_AUDIT.md").read_text().lower()
        # Should NOT flag an identity mismatch (source matches the prompt)
        assert "different application" not in content, (
            "Auditor incorrectly flagged identity mismatch"
        )


class TestAuditPhaseIdentityMismatch:
    """Auditor should detect when source code doesn't match the prompt."""

    async def test_detects_wrong_project(self, project_with_source):
        """Overwrite ORIGINAL_PROMPT.md with a different project description."""
        # Change the prompt to something completely different
        (project_with_source / "ORIGINAL_PROMPT.md").write_text(
            "# Original Product Prompt\n\nBuild a recipe sharing social network\n"
        )

        state = make_state(
            idea="Build a recipe sharing social network",
            stack_id="nextjs-prisma",
            phase=Phase.BUILD,
        )

        call, validation = await run_phase(
            Phase.AUDIT, state, project_with_source, make_progress()
        )

        assert call.success
        content = (project_with_source / "SPEC_AUDIT.md").read_text().lower()
        # Should detect that the built app (ProServ SaaS) doesn't match
        # the prompt (recipe social network)
        has_mismatch = (
            "mismatch" in content
            or "different" in content
            or "does not match" in content
            or "critical" in content
        )
        assert has_mismatch, (
            "Auditor should flag identity mismatch between prompt and source code"
        )
