"""Verify phase — tests the deployed application works correctly."""

from pathlib import Path

from ..state import Phase, AgentState
from . import PhaseConfig, register_phase


def _build_prompt(state: AgentState, project_dir: Path) -> str:
    """Build the verifier task prompt."""
    parts = ["Verify the deployed application works correctly."]

    parts.append(f"\nProject directory: {project_dir}")

    if state.deployment_url:
        parts.append(f"\nDeployment URL: {state.deployment_url}")
        parts.append("\n1. Test homepage loads (200 status)")
        parts.append("2. Test authentication flow (if auth exists)")
        parts.append("3. Test at least ONE database-backed API endpoint returns valid JSON (e.g., /api/auth/providers or a data listing endpoint)")
        parts.append("4. Test core feature pages load without errors")
        parts.append("5. Read DESIGN.md to identify API routes — test at least one that queries the database")
        parts.append("\nCRITICAL: A homepage returning 200 is NOT sufficient verification.")
        parts.append("You MUST verify that the database connection works by testing an endpoint that queries data.")
    elif state.build_mode in ("plugin", "host"):
        parts.append("\nThis is a Swift build — no URL to verify.")
        parts.append("Verify: swift package resolve, swift build, swift test all pass.")
    else:
        parts.append("\nLook for the deployment URL in DEPLOYMENT.md, DEPLOY_RESULT.md, or other .md files.")

    parts.append("\nCreate VERIFICATION.md with your test results.")
    return "\n".join(parts)


register_phase(PhaseConfig(
    phase=Phase.VERIFY,
    agent_name="verifier",
    display_name="Verifying deployment",
    tools=["Read", "Bash", "WebFetch", "Glob"],
    max_turns=15,
    max_retries=1,
    required_artifacts=["VERIFICATION.md"],
    build_prompt=_build_prompt,
))
