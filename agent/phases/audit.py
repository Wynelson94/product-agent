"""Audit phase — verifies build matches original requirements."""

from pathlib import Path

from ..state import Phase, AgentState
from . import PhaseConfig, register_phase


def _build_prompt(state: AgentState, project_dir: Path) -> str:
    """Build the auditor task prompt.

    v12.0: Added identity verification step. The auditor must first confirm
    the built code matches the current prompt — prevents auditing stale files
    from a previous build that contaminated the project directory.
    """
    parts = ["Audit the built application against the original requirements."]

    parts.append(f"\nProject directory: {project_dir}")
    # v12.0: Identity check must be step 1 — catches directory contamination early
    parts.append("\n1. Read ORIGINAL_PROMPT.md and verify the built application matches this prompt.")
    parts.append("   If the codebase appears to be a DIFFERENT application than described in ORIGINAL_PROMPT.md,")
    parts.append("   report this as a CRITICAL discrepancy immediately.")
    parts.append("2. Read DESIGN.md for the planned architecture")
    parts.append("3. Scan all source files to verify implementation matches requirements")
    parts.append("4. Create SPEC_AUDIT.md with your findings")

    if state.build_mode == "plugin":
        parts.append("\nThis is a Swift plugin. Verify NCBSPlugin conformance and PluginManifest.swift.")
    elif state.build_mode == "host":
        parts.append("\nThis is a Swift host app. Verify all service protocols have implementations.")

    return "\n".join(parts)


register_phase(PhaseConfig(
    phase=Phase.AUDIT,
    agent_name="auditor",
    display_name="Auditing spec",
    tools=["Read", "Glob", "Grep", "Write"],
    max_turns=20,
    max_retries=0,
    required_artifacts=["SPEC_AUDIT.md"],
    build_prompt=_build_prompt,
))
