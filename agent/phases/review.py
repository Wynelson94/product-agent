"""Review phase — validates design before implementation."""

from pathlib import Path

from ..state import Phase, AgentState
from . import PhaseConfig, register_phase


def _build_prompt(state: AgentState, project_dir: Path) -> str:
    """Build the reviewer task prompt."""
    parts = [f"Review the technical design for this product:\n\n{state.idea}"]

    parts.append(f"\nProject directory: {project_dir}")
    parts.append("\nRead DESIGN.md and validate it against the checklist.")
    parts.append("Read STACK_DECISION.md to understand the selected stack.")

    parts.append("\nCreate REVIEW.md with your verdict (APPROVED or NEEDS_REVISION).")
    return "\n".join(parts)


register_phase(PhaseConfig(
    phase=Phase.REVIEW,
    agent_name="reviewer",
    display_name="Reviewing design",
    tools=["Read", "Write", "Glob", "Grep"],
    max_turns=15,
    max_retries=0,  # Retries handled by design-review loop in orchestrator
    required_artifacts=["REVIEW.md"],
    build_prompt=_build_prompt,
))
