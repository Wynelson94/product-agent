"""Enricher phase — expands rough ideas into detailed specifications."""

from pathlib import Path

from ..state import Phase, AgentState
from . import PhaseConfig, register_phase


def _build_prompt(state: AgentState, project_dir: Path) -> str:
    """Build the enricher task prompt."""
    parts = [f"Research and expand this product idea into a detailed specification:\n\n{state.idea}"]

    url = getattr(state, "enrichment_source_url", None)
    if url:
        parts.append(f"\nReference URL to research: {url}")

    parts.append(f"\nProject directory: {project_dir}")
    parts.append("\nCreate PROMPT.md with the detailed specification.")
    return "\n".join(parts)


register_phase(PhaseConfig(
    phase=Phase.ENRICH,
    agent_name="enricher",
    display_name="Enriching prompt",
    tools=["Read", "Write", "WebSearch", "WebFetch"],
    max_turns=20,
    max_retries=1,
    required_artifacts=["PROMPT.md"],
    build_prompt=_build_prompt,
))
