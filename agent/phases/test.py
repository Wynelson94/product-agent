"""Test phase — generates and runs tests for the application."""

from pathlib import Path

from ..state import Phase, AgentState
from . import PhaseConfig, register_phase


def _build_prompt(state: AgentState, project_dir: Path) -> str:
    """Build the tester task prompt."""
    parts = ["Generate and run comprehensive tests for the application."]

    parts.append(f"\nProject directory: {project_dir}")
    parts.append("\n1. Read STACK_DECISION.md to understand the stack")
    parts.append("2. Read DESIGN.md to understand the architecture")
    parts.append("3. Read ORIGINAL_PROMPT.md for content verification")
    parts.append("4. Generate comprehensive tests")
    parts.append("5. Run the tests and ensure they pass")
    parts.append("6. Create TEST_RESULTS.md with the results")

    return "\n".join(parts)


register_phase(PhaseConfig(
    phase=Phase.TEST,
    agent_name="tester",
    display_name="Running tests",
    tools=[
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
        "Bash(npm *)", "Bash(npx *)",
        "Bash(swift *)",
    ],
    max_turns=30,
    max_retries=2,  # Up to 3 total attempts
    required_artifacts=["TEST_RESULTS.md"],
    build_prompt=_build_prompt,
))
