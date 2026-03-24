"""Enhancer phase — adds features to existing DESIGN.md.

Used in enhancement mode to modify an already-built product's design
with new features while preserving all existing functionality.
"""

from pathlib import Path

from ..state import Phase, AgentState
from . import PhaseConfig, register_phase


def _build_prompt(state: AgentState, project_dir: Path) -> str:
    """Build the enhancer task prompt.

    Includes the enhancement request and lists the specific features
    to add. The enhancer agent reads the existing DESIGN.md and updates
    it in-place, marking all additions with '(NEW)' for traceability.
    """
    features = state.enhance_features
    feature_list = "\n".join(f"- {f}" for f in features) if features else "- General improvements"

    parts = [
        f"Enhance the existing application design with the following features:\n",
        f"## Features to Add\n{feature_list}\n",
        f"## Original Product Idea\n{state.idea}\n",
        f"## Instructions",
        f"1. Read the existing DESIGN.md in {project_dir}",
        f"2. Add the requested features while PRESERVING all existing functionality",
        f"3. Mark all new additions with '(NEW)' in the design document",
        f"4. Update the YAML front-matter with the new table/page/component counts",
        f"5. Write the updated DESIGN.md back to {project_dir}",
        f"\nProject directory: {project_dir}",
    ]
    return "\n".join(parts)


register_phase(PhaseConfig(
    phase=Phase.ENHANCE,
    agent_name="enhancer",
    display_name="Enhancing design",
    tools=["Read", "Write", "Edit", "Glob", "Grep"],
    max_turns=40,
    max_retries=1,
    required_artifacts=["DESIGN.md"],
    build_prompt=_build_prompt,
))
