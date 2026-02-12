"""Build phase — implements the application from design."""

from pathlib import Path

from ..state import Phase, AgentState
from . import PhaseConfig, register_phase


def _build_prompt(state: AgentState, project_dir: Path) -> str:
    """Build the builder task prompt."""
    parts = [f"Implement the application for this product:\n\n{state.idea}"]

    parts.append(f"\nProject directory: {project_dir}")
    parts.append("\n1. Read STACK_DECISION.md to understand the stack")
    parts.append("2. Read DESIGN.md to understand the architecture")
    parts.append("3. Read ORIGINAL_PROMPT.md to cross-reference specific values")
    parts.append("4. Implement the complete application")
    parts.append("5. Set up test infrastructure")
    parts.append("6. Verify the build passes")

    if state.build_mode == "plugin":
        parts.append("\nThis is a Swift Package plugin build. Create NCBSPluginSDK first, then the plugin package.")
    elif state.build_mode == "host":
        parts.append("\nThis is a Swift host app build. Create NCBSPluginSDK first, then the host app.")

    return "\n".join(parts)


# Build phase gets the most tools and turns
register_phase(PhaseConfig(
    phase=Phase.BUILD,
    agent_name="builder",
    display_name="Building application",
    tools=[
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
        "Bash(npm *)", "Bash(npx *)", "Bash(node *)",
        "Bash(git *)", "Bash(pnpm *)",
        "Bash(swift *)", "Bash(xcodebuild *)", "Bash(xcrun *)",
    ],
    max_turns=80,
    max_retries=4,  # Up to 5 total attempts (1 initial + 4 retries)
    required_artifacts=[],  # Validated by _validate_build in validators.py
    build_prompt=_build_prompt,
))
