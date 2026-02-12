"""Design phase — creates technical design from stack decision."""

from pathlib import Path

from ..state import Phase, AgentState
from . import PhaseConfig, register_phase


def _build_prompt(state: AgentState, project_dir: Path) -> str:
    """Build the designer task prompt."""
    parts = [f"Create a comprehensive technical design for this product:\n\n{state.idea}"]

    parts.append(f"\nProject directory: {project_dir}")
    parts.append("\nRead STACK_DECISION.md first to understand the selected stack.")

    # If enriched, reference PROMPT.md
    prompt_md = project_dir / "PROMPT.md"
    if prompt_md.exists():
        parts.append("Read PROMPT.md for the detailed specification.")

    # Build mode
    if state.build_mode != "standard":
        parts.append(f"\nBuild mode: {state.build_mode}")

    # If this is a design revision, include review feedback
    review_file = project_dir / "REVIEW.md"
    if state.design_revision > 0 and review_file.exists():
        feedback = review_file.read_text()
        parts.append(f"\n## Design Revision #{state.design_revision}")
        parts.append("The reviewer requested changes. Read REVIEW.md and address the feedback:")
        parts.append(f"\n{feedback[:2000]}")

    parts.append("\nCreate DESIGN.md with the complete technical design.")
    return "\n".join(parts)


register_phase(PhaseConfig(
    phase=Phase.DESIGN,
    agent_name="designer",
    display_name="Designing architecture",
    tools=["Read", "Write", "Glob", "Grep"],
    max_turns=25,
    max_retries=0,  # Retries handled by design-review loop in orchestrator
    required_artifacts=["DESIGN.md"],
    build_prompt=_build_prompt,
))
