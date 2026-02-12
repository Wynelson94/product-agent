"""Deploy phase — deploys the application to production."""

from pathlib import Path

from ..state import Phase, AgentState
from . import PhaseConfig, register_phase


def _build_prompt(state: AgentState, project_dir: Path) -> str:
    """Build the deployer task prompt."""
    parts = ["Deploy the application to production."]

    parts.append(f"\nProject directory: {project_dir}")
    parts.append("\n1. Read STACK_DECISION.md for deployment configuration")
    parts.append("2. Run pre-deployment validation")
    parts.append("3. Verify the build passes")
    parts.append("4. Deploy to the appropriate platform")
    parts.append("5. Return the production URL")

    # Check test results exist and passed
    test_file = project_dir / "TEST_RESULTS.md"
    if test_file.exists():
        content = test_file.read_text().lower()
        if "failed" in content and "status: failed" in content:
            parts.append("\nWARNING: TEST_RESULTS.md shows failures. Verify tests pass before deploying.")

    if state.build_mode in ("plugin", "host"):
        parts.append("\nThis is a Swift build. Deploy means: swift build + swift test + git tag (plugin) or xcodebuild archive (host).")

    return "\n".join(parts)


register_phase(PhaseConfig(
    phase=Phase.DEPLOY,
    agent_name="deployer",
    display_name="Deploying",
    tools=[
        "Read", "Bash", "WebFetch", "Glob",
        "Bash(npm *)", "Bash(npx *)", "Bash(vercel *)",
        "Bash(swift *)", "Bash(xcodebuild *)",
        "Bash(git *)", "Bash(railway *)",
    ],
    max_turns=25,
    max_retries=1,
    required_artifacts=[],  # URL extracted by validator
    build_prompt=_build_prompt,
))
