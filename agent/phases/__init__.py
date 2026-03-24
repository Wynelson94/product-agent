"""Phase registry and runner for Product Agent v9.0.

Each phase is a focused Claude call with its own prompt, tools, validation,
and retry strategy. Python controls the pipeline; Claude does the creative work.

v9.0: Phase prompts and responses are logged to .agent_logs/ for debuggability.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..state import Phase, AgentState
from ..validators import ValidationResult, validate_phase_output
from ..cli_runner import PhaseCallResult, run_phase_call
from ..progress import ProgressReporter, PhaseResult
from ..agents.definitions import get_agent_prompt


@dataclass
class PhaseConfig:
    """Configuration for a single pipeline phase."""
    phase: Phase
    agent_name: str
    display_name: str
    tools: list[str]
    max_turns: int = 30
    max_retries: int = 1
    model: str | None = None
    timeout_s: int | None = None  # Per-phase timeout override (defaults to config.PHASE_TIMEOUT_S)

    # Called to build the task prompt for this phase
    build_prompt: Callable[[AgentState, Path], str] | None = None

    # Files that must exist after this phase completes
    required_artifacts: list[str] = field(default_factory=list)


# Phase configs are registered by each phase module
_PHASE_CONFIGS: dict[Phase, PhaseConfig] = {}


def register_phase(config: PhaseConfig) -> None:
    """Register a phase configuration."""
    _PHASE_CONFIGS[config.phase] = config


def get_phase_config(phase: Phase) -> PhaseConfig | None:
    """Get the configuration for a phase."""
    return _PHASE_CONFIGS.get(phase)


def get_all_phase_configs() -> dict[Phase, PhaseConfig]:
    """Get all registered phase configurations."""
    return dict(_PHASE_CONFIGS)


async def run_phase(
    phase: Phase,
    state: AgentState,
    project_dir: Path,
    progress: ProgressReporter,
    retry_context: str | None = None,
) -> tuple[PhaseCallResult, ValidationResult]:
    """Execute a single phase with validation and progress reporting.

    Args:
        phase: The phase to run
        state: Current agent state
        project_dir: Project directory path
        progress: Progress reporter for real-time output
        retry_context: Optional error context from a previous failed attempt

    Returns:
        Tuple of (PhaseCallResult, ValidationResult)
    """
    config = get_phase_config(phase)
    if not config:
        raise ValueError(f"No configuration registered for phase {phase.value}")

    # Report phase start
    progress.phase_start(config.display_name)

    # Build the prompt
    if config.build_prompt:
        prompt = config.build_prompt(state, project_dir)
    else:
        prompt = f"Execute the {config.display_name} phase for: {state.idea}"

    # Inject retry context if this is a retry
    if retry_context:
        prompt = f"""RETRY — Previous attempt failed:
{retry_context}

Fix the issue and try a different approach. Do NOT repeat the same mistake.

---

{prompt}"""

    # Get the system prompt (with template injection)
    system_prompt = get_agent_prompt(
        config.agent_name,
        stack_id=state.stack_id,
        build_mode=state.build_mode,
    )

    # Run the phase
    call_result = await run_phase_call(
        prompt=prompt,
        system_prompt=system_prompt,
        allowed_tools=config.tools,
        cwd=project_dir,
        max_turns=config.max_turns,
        model=config.model,
        timeout_s=config.timeout_s,
    )

    # Log prompt, system prompt, and response for debuggability
    _log_phase_call(project_dir, phase, prompt, system_prompt, call_result)

    # Validate output
    validation = validate_phase_output(phase, project_dir)

    # Build detail string for progress output
    detail = ""
    if validation.extracted:
        if "stack_id" in validation.extracted:
            detail = f"-> {validation.extracted['stack_id']}"
        elif "tests_passed" in validation.extracted:
            total = validation.extracted.get("tests_total", "?")
            passed = validation.extracted["tests_passed"]
            detail = f"{passed}/{total} passed"
        elif "requirements_met" in validation.extracted:
            total = validation.extracted.get("requirements_total", "?")
            met = validation.extracted["requirements_met"]
            detail = f"{met}/{total} met"
        elif "approved" in validation.extracted:
            detail = "APPROVED" if validation.extracted["approved"] else "NEEDS REVISION"
        elif "url" in validation.extracted:
            detail = validation.extracted["url"]
        elif "verified" in validation.extracted:
            detail = "PASSED" if validation.extracted["verified"] else "FAILED"

    # Report completion
    phase_result = PhaseResult(
        phase_name=config.display_name,
        success=call_result.success and validation.passed,
        duration_s=call_result.duration_s,
        detail=detail,
        num_turns=call_result.num_turns,
        cost_usd=call_result.cost_usd,
    )
    progress.phase_complete(phase_result)

    return call_result, validation


def _log_phase_call(
    project_dir: Path,
    phase: Phase,
    prompt: str,
    system_prompt: str,
    call_result: PhaseCallResult,
) -> None:
    """Write phase prompt/response logs for post-mortem debugging.

    Writes to {project_dir}/.agent_logs/{phase}_{timestamp}.*.
    Failures are silently ignored — logging must never break the build.
    """
    try:
        log_dir = project_dir / ".agent_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"{phase.value}_{timestamp}"

        (log_dir / f"{prefix}.prompt.md").write_text(prompt)
        (log_dir / f"{prefix}.system.md").write_text(system_prompt)
        (log_dir / f"{prefix}.response.md").write_text(call_result.result_text or "")

        summary = {
            "phase": phase.value,
            "timestamp": datetime.now().isoformat(),
            "success": call_result.success,
            "num_turns": call_result.num_turns,
            "cost_usd": call_result.cost_usd,
            "duration_s": call_result.duration_s,
            "error": call_result.error or None,
        }
        (log_dir / f"{prefix}.summary.json").write_text(
            json.dumps(summary, indent=2)
        )
    except Exception:
        # Logging is best-effort. If disk is full, permissions fail, etc.,
        # we still want the build to complete. Logs are for debugging, not correctness.
        pass


# Import all phase modules to trigger their register_phase() calls.
# Each module (enrich.py, analyze.py, etc.) calls register_phase() at import time
# to add its PhaseConfig to the _PHASE_CONFIGS registry.
from . import (  # noqa: E402, F401
    enrich,
    analyze,
    design,
    review,
    enhance,
    build,
    audit,
    test,
    deploy,
    verify,
)
