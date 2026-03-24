"""Shared fixtures and helpers for isolated phase stress testing.

Provides controlled inputs for each phase so failures can be isolated
to the specific phase that caused them, not cascading from earlier phases.

Level 1 tests (validators): No SDK calls, run instantly, test parsing logic.
Level 2 tests (integration): Real SDK calls, marked @pytest.mark.stress.
"""

import shutil
from pathlib import Path

import pytest

from agent.state import AgentState, Phase, ReviewStatus
from agent.progress import ProgressReporter


# Root directory for fixture files
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(relative_path: str) -> str:
    """Load a fixture file by relative path from the fixtures directory."""
    path = FIXTURES_DIR / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return path.read_text()


def make_state(
    idea: str = "Build a multi-tenant SaaS for professional services teams",
    stack_id: str | None = "nextjs-prisma",
    phase: Phase = Phase.INIT,
    design_revision: int = 0,
    build_mode: str = "standard",
    enhancement_mode: bool = False,
    enhance_features: list[str] | None = None,
    tests_passed: bool = False,
    tests_generated: bool = False,
    spec_audit_completed: bool = False,
    deployment_url: str | None = None,
) -> AgentState:
    """Create an AgentState with controlled values for isolated phase testing.

    Each test sets only the fields relevant to the phase being tested.
    Fields not set use safe defaults that won't interfere with validation.
    """
    state = AgentState()
    state.idea = idea
    state.phase = phase
    state.stack_id = stack_id
    state.design_revision = design_revision
    state.build_mode = build_mode
    state.enhancement_mode = enhancement_mode
    state.enhance_features = enhance_features or []
    state.tests_passed = tests_passed
    state.tests_generated = tests_generated
    state.spec_audit_completed = spec_audit_completed
    state.deployment_url = deployment_url
    state.mark_started()
    return state


def populate_project(
    project_dir: Path,
    fixtures: dict[str, str],
) -> None:
    """Populate a project directory with fixture files.

    Args:
        project_dir: Target directory (should exist)
        fixtures: Dict mapping target filename → fixture relative path.
            Example: {"STACK_DECISION.md": "analysis/stack_decision_prisma.md"}
    """
    for target_name, fixture_path in fixtures.items():
        content = load_fixture(fixture_path)
        (project_dir / target_name).write_text(content)


def make_progress() -> ProgressReporter:
    """Create a silent progress reporter for testing."""
    return ProgressReporter(verbose=False)


# ── Pytest Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def stress_project(tmp_path):
    """Create a temp project directory with ORIGINAL_PROMPT.md pre-populated."""
    project = tmp_path / "test-project"
    project.mkdir()
    content = load_fixture("original_prompt.md")
    (project / "ORIGINAL_PROMPT.md").write_text(content)
    return project


@pytest.fixture
def simple_project(tmp_path):
    """Create a temp project with a simple todo app prompt."""
    project = tmp_path / "test-project"
    project.mkdir()
    content = load_fixture("original_prompt_simple.md")
    (project / "ORIGINAL_PROMPT.md").write_text(content)
    return project


@pytest.fixture
def project_with_analysis(stress_project):
    """Project with ORIGINAL_PROMPT.md + STACK_DECISION.md (Prisma)."""
    populate_project(stress_project, {
        "STACK_DECISION.md": "analysis/stack_decision_prisma.md",
    })
    return stress_project


@pytest.fixture
def project_with_design(project_with_analysis):
    """Project with analysis + DESIGN.md."""
    populate_project(project_with_analysis, {
        "DESIGN.md": "design/design_proserv.md",
    })
    return project_with_analysis


@pytest.fixture
def project_with_review(project_with_design):
    """Project with analysis + design + approved REVIEW.md."""
    populate_project(project_with_design, {
        "REVIEW.md": "review/review_approved.md",
    })
    return project_with_design
