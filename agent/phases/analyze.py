"""Analysis phase — selects optimal technology stack."""

from pathlib import Path

from ..state import Phase, AgentState
from . import PhaseConfig, register_phase


def _build_prompt(state: AgentState, project_dir: Path) -> str:
    """Build the analyzer task prompt."""
    parts = [f"Analyze this product idea and select the optimal technology stack:\n\n{state.idea}"]

    parts.append(f"\nProject directory: {project_dir}")

    # If enriched, reference PROMPT.md
    prompt_md = project_dir / "PROMPT.md"
    if prompt_md.exists():
        parts.append("\nIMPORTANT: Read PROMPT.md first — it contains the enriched specification.")

    # If stack is forced
    if state.stack_id:
        parts.append(f"\nNote: Stack has been pre-selected as `{state.stack_id}`. Confirm this choice in STACK_DECISION.md.")

    # Build mode hint
    if state.build_mode != "standard":
        parts.append(f"\nBuild mode: {state.build_mode}")

    parts.append("\nCreate STACK_DECISION.md with your analysis and stack selection.")
    return "\n".join(parts)


register_phase(PhaseConfig(
    phase=Phase.ANALYSIS,
    agent_name="analyzer",
    display_name="Analyzing stack",
    tools=["Read", "Write", "WebSearch"],
    max_turns=15,
    max_retries=1,
    required_artifacts=["STACK_DECISION.md"],
    build_prompt=_build_prompt,
))
