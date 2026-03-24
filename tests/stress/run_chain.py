#!/usr/bin/env python3
"""Level 3: Sequential phase chain runner.

Runs phases one at a time, saving artifacts between each phase for inspection.
Stops after the specified phases so you can examine intermediate output.

Usage:
    # Run analysis only
    python3 tests/stress/run_chain.py --phases analysis --idea "Build a todo app"

    # Run analysis + design
    python3 tests/stress/run_chain.py --phases analysis,design --idea "Build a SaaS app"

    # Run analysis through review
    python3 tests/stress/run_chain.py --phases analysis,design,review

    # Custom project directory
    python3 tests/stress/run_chain.py --phases analysis,design --project-dir ./my-test

    # Force a specific stack
    python3 tests/stress/run_chain.py --phases design --stack nextjs-prisma

The default idea is the stress test prompt. Each phase's output feeds the next.
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.state import Phase, AgentState, create_initial_state
from agent.phases import run_phase
from agent.progress import ProgressReporter
from agent.sanitize import sanitize_idea
from agent.validators import validate_phase_output


STRESS_PROMPT = (
    "Build a multi-tenant SaaS for professional services teams to manage "
    "projects, time tracking, invoicing, and client billing with role-based "
    "access control (owner/admin/member/viewer), Stripe subscription billing, "
    "org-scoped RLS isolation, activity audit logs, and tiered pricing plans"
)

PHASE_MAP = {
    "analysis": Phase.ANALYSIS,
    "design": Phase.DESIGN,
    "review": Phase.REVIEW,
    "enhance": Phase.ENHANCE,
    "build": Phase.BUILD,
    "audit": Phase.AUDIT,
    "test": Phase.TEST,
    "deploy": Phase.DEPLOY,
    "verify": Phase.VERIFY,
}


async def run_chain(
    phases: list[str],
    idea: str,
    project_dir: Path,
    stack: str | None = None,
) -> None:
    """Run a chain of phases sequentially with output inspection."""
    project_dir.mkdir(parents=True, exist_ok=True)

    idea = sanitize_idea(idea)
    state = create_initial_state(idea, str(project_dir))
    if stack:
        state.stack_id = stack

    progress = ProgressReporter(verbose=True)

    # Write original prompt
    (project_dir / "ORIGINAL_PROMPT.md").write_text(
        f"# Original Product Prompt\n\n{idea}\n"
    )

    print(f"\n{'='*60}")
    print(f"PHASE CHAIN RUNNER")
    print(f"{'='*60}")
    print(f"Phases: {', '.join(phases)}")
    print(f"Idea: {idea[:80]}...")
    print(f"Project: {project_dir}")
    if stack:
        print(f"Stack: {stack} (forced)")
    print(f"{'='*60}\n")

    total_start = time.time()

    for i, phase_name in enumerate(phases):
        phase = PHASE_MAP.get(phase_name)
        if not phase:
            print(f"ERROR: Unknown phase '{phase_name}'. Valid: {', '.join(PHASE_MAP.keys())}")
            return

        print(f"\n--- Phase {i+1}/{len(phases)}: {phase_name.upper()} ---")
        phase_start = time.time()

        try:
            call, validation = await run_phase(phase, state, project_dir, progress)
        except Exception as e:
            print(f"EXCEPTION in {phase_name}: {e}")
            break

        phase_time = time.time() - phase_start

        # Update state based on phase results
        if phase == Phase.ANALYSIS and validation.extracted.get("stack_id"):
            state.stack_id = validation.extracted["stack_id"]

        # Print results
        print(f"\nResult: {'SUCCESS' if call.success else 'FAILED'} ({phase_time:.0f}s)")
        if call.error:
            print(f"Error: {call.error[:200]}")
        print(f"Turns: {call.num_turns}")
        if validation.extracted:
            print(f"Extracted: {validation.extracted}")
        if not validation.passed:
            print(f"Validation: FAILED")
            for msg in validation.messages:
                print(f"  - {msg}")
        else:
            print(f"Validation: PASSED")

        # Show artifacts created
        print(f"\nArtifacts in {project_dir}:")
        for f in sorted(project_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                size = f.stat().st_size
                print(f"  {f.name} ({size:,} bytes)")

        if not call.success:
            print(f"\n--- CHAIN STOPPED: {phase_name} failed ---")
            break

    total_time = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"CHAIN COMPLETE — {total_time:.0f}s total")
    print(f"Project directory: {project_dir}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Run product agent phases sequentially")
    parser.add_argument("--phases", required=True,
                        help="Comma-separated phases: analysis,design,review,build,audit,test,deploy,verify")
    parser.add_argument("--idea", default=STRESS_PROMPT,
                        help="Product idea (default: stress test prompt)")
    parser.add_argument("--project-dir", default="./projects/chain-test",
                        help="Project directory (default: ./projects/chain-test)")
    parser.add_argument("--stack", default=None,
                        help="Force a specific stack (default: auto-select)")

    args = parser.parse_args()
    phases = [p.strip() for p in args.phases.split(",")]

    asyncio.run(run_chain(
        phases=phases,
        idea=args.idea,
        project_dir=Path(args.project_dir).resolve(),
        stack=args.stack,
    ))


if __name__ == "__main__":
    main()
