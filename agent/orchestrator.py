"""Orchestrator for Product Agent v8.0.

Replaces the monolithic single-call architecture with a Python-controlled
phase pipeline. Each phase gets its own focused Claude call. Python validates
between phases, handles retries with error injection, and streams progress.
"""

import asyncio
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .state import AgentState, Phase, create_initial_state
from .checkpoints import CheckpointManager
from .validators import validate_phase_output, validate_build_routes
from .progress import ProgressReporter, PhaseResult
from .phases import run_phase, get_phase_config
from .cli_runner import PhaseCallResult
from .quality import compute_quality_score
from .sanitize import sanitize_idea
from . import config


@dataclass
class BuildConfig:
    """Configuration for a product build."""
    stack: str | None = None
    mode: str = "standard"  # standard | plugin | host | enhancement
    enrich: bool = False
    enrich_url: str | None = None
    verbose: bool = False
    require_tests: bool = True
    legacy: bool = False
    design_file: str | None = None
    enhance_features: list[str] = field(default_factory=list)


@dataclass
class BuildResult:
    """Result of a complete build."""
    success: bool
    url: str | None = None
    quality: str | None = None
    duration_s: float = 0.0
    test_count: str | None = None
    spec_coverage: str | None = None
    reason: str | None = None
    phase_results: list[PhaseResult] = field(default_factory=list)


async def build_product(
    idea: str,
    project_dir: str | Path,
    build_config: BuildConfig | None = None,
) -> BuildResult:
    """Build a product from an idea using the phase pipeline.

    This is the v8.0 orchestrator. Each phase gets its own Claude call.
    Python validates between phases, handles retries, and streams progress.

    Args:
        idea: The product idea to build
        project_dir: Directory to create the project in
        build_config: Build configuration (defaults applied if None)

    Returns:
        BuildResult with success status, URL, quality score, and metrics
    """
    cfg = build_config or BuildConfig()
    project_path = Path(project_dir).resolve()
    project_path.mkdir(parents=True, exist_ok=True)

    # v9.0: Sanitize user input before it enters any prompts
    idea = sanitize_idea(idea)

    # Initialize state
    state = create_initial_state(idea, str(project_path))
    if cfg.stack:
        state.stack_id = cfg.stack
    state.build_mode = cfg.mode

    # Write original prompt for builder cross-reference
    (project_path / "ORIGINAL_PROMPT.md").write_text(
        f"# Original Product Prompt\n\n{idea}\n"
    )

    # Initialize progress reporter
    progress = ProgressReporter(verbose=cfg.verbose)
    progress.build_header(idea)

    # Set phase count based on mode
    phase_count = _get_phase_count(cfg)
    progress.set_total_phases(phase_count)

    # Initialize checkpoint manager
    checkpoint_mgr = CheckpointManager(str(project_path))

    # v9.0: Track total turns across all phases
    total_turns = 0

    # Handle enhancement mode setup
    if cfg.mode == "enhancement" and cfg.design_file:
        _setup_enhancement_mode(state, cfg, project_path)

    def _track_turns(call_result: PhaseCallResult) -> None:
        """Accumulate turns and raise if limit exceeded."""
        nonlocal total_turns
        turns = call_result.num_turns if isinstance(call_result.num_turns, int) else 0
        total_turns += turns
        max_turns = getattr(config, 'MAX_TOTAL_TURNS', 300)
        if isinstance(max_turns, int) and total_turns > max_turns:
            raise _TurnLimitExceeded(
                f"Total turns ({total_turns}) exceeded limit ({max_turns})"
            )

    try:
        # ---------------------------------------------------------------
        # Phase 1: Enrich (optional)
        # ---------------------------------------------------------------
        if cfg.enrich:
            if cfg.enrich_url:
                state.enrichment_source_url = cfg.enrich_url
            call, validation = await run_phase(
                Phase.ENRICH, state, project_path, progress
            )
            _track_turns(call)
            if not call.success:
                progress.log(f"Enrichment failed: {call.error}")
                # Non-fatal — continue without enrichment
            else:
                state.prompt_enriched = True
            state.transition_to(Phase.ENRICH, "Enrichment complete")
            checkpoint_mgr.save(state)

        # ---------------------------------------------------------------
        # Phase 2: Analysis
        # ---------------------------------------------------------------
        call, validation = await run_phase(
            Phase.ANALYSIS, state, project_path, progress
        )
        _track_turns(call)
        if not call.success:
            return _build_failed(progress, "Analysis failed", call.error)

        # Extract stack ID from STACK_DECISION.md
        if validation.extracted.get("stack_id"):
            state.stack_id = validation.extracted["stack_id"]
        elif not state.stack_id:
            state.stack_id = _parse_stack_decision(project_path)

        state.transition_to(Phase.ANALYSIS, f"Stack: {state.stack_id}")
        checkpoint_mgr.save(state)

        # ---------------------------------------------------------------
        # Phase 3-4: Design + Review loop
        # ---------------------------------------------------------------
        max_revisions = config.MAX_DESIGN_REVISIONS
        approved = False

        for revision in range(max_revisions + 1):
            state.design_revision = revision

            # Design
            call, validation = await run_phase(
                Phase.DESIGN, state, project_path, progress
            )
            _track_turns(call)
            if not call.success:
                return _build_failed(progress, "Design failed", call.error)
            state.transition_to(Phase.DESIGN, f"Revision {revision}")
            checkpoint_mgr.save(state)

            # Review
            call, review_validation = await run_phase(
                Phase.REVIEW, state, project_path, progress
            )
            _track_turns(call)
            if not call.success:
                progress.log("Review call failed — treating as approved")
                approved = True
                break

            if review_validation.extracted.get("approved", True):
                approved = True
                state.review_status = state.review_status.__class__("approved")
                break

            # Not approved — prepare for next revision
            progress.log(f"Design needs revision ({revision + 1}/{max_revisions})")
            if revision >= max_revisions:
                progress.log("Max revisions reached — proceeding with current design")
                break

        state.transition_to(Phase.REVIEW, "Approved" if approved else "Max revisions")
        checkpoint_mgr.save(state)

        # ---------------------------------------------------------------
        # Phase 5: Build with smart retry
        # ---------------------------------------------------------------
        max_attempts = config.MAX_BUILD_ATTEMPTS
        build_succeeded = False
        retry_context = None

        for attempt in range(max_attempts):
            state.build_attempts = attempt + 1

            call, validation = await run_phase(
                Phase.BUILD, state, project_path, progress,
                retry_context=retry_context,
            )
            _track_turns(call)

            # Check if source code was produced
            build_validation = validate_phase_output(Phase.BUILD, project_path)
            if not call.success or not build_validation.passed:
                error_msg = call.error or "Build produced no source code"
                for msg in build_validation.messages:
                    if "FAIL" in msg:
                        error_msg += f"\n{msg}"
                retry_context = error_msg
                progress.log(f"Build attempt {attempt + 1} failed: {error_msg[:200]}")
                continue

            # v9.0: Route validation — strict on final attempt
            is_final = attempt == max_attempts - 1
            route_check = validate_build_routes(project_path, strict=is_final)
            missing = route_check.extracted.get("missing_routes", [])
            if missing and is_final:
                # Final attempt: missing routes are errors
                for msg in route_check.messages:
                    if "FAIL" in msg:
                        progress.log(msg)
            elif missing:
                # Non-final: report as warnings, inject into retry context
                retry_context = f"Missing routes from DESIGN.md: {', '.join(missing[:5])}"
                progress.log(f"Build attempt {attempt + 1}: {len(missing)} missing routes")
                continue

            build_succeeded = True
            break

        if not build_succeeded:
            return _build_failed(
                progress, "Build failed after all attempts",
                f"{max_attempts} attempts exhausted"
            )

        state.transition_to(Phase.BUILD, f"Built in {state.build_attempts} attempt(s)")
        checkpoint_mgr.save(state)

        # ---------------------------------------------------------------
        # Phase 6-7: Audit + Test (parallel)
        # ---------------------------------------------------------------
        audit_task = asyncio.create_task(
            run_phase(Phase.AUDIT, state, project_path, progress)
        )
        test_task = asyncio.create_task(
            run_phase(Phase.TEST, state, project_path, progress)
        )

        (audit_call, audit_validation), (test_call, test_validation) = await asyncio.gather(
            audit_task, test_task
        )
        _track_turns(audit_call)
        _track_turns(test_call)

        # Process audit results
        state.spec_audit_completed = True
        if audit_validation.extracted.get("requirements_met"):
            met = audit_validation.extracted["requirements_met"]
            total = audit_validation.extracted.get("requirements_total", "?")
            state.spec_audit_discrepancies = max(0, (total if isinstance(total, int) else 0) - met)
        elif audit_validation.extracted.get("discrepancies"):
            state.spec_audit_discrepancies = audit_validation.extracted["discrepancies"]

        # Process test results
        test_detail = ""
        if test_validation.extracted.get("tests_passed"):
            passed = test_validation.extracted["tests_passed"]
            total = test_validation.extracted.get("tests_total", "?")
            test_detail = f"{passed}/{total}"
            state.tests_passed = test_validation.extracted.get("all_passed", True)
        else:
            state.tests_passed = test_call.success

        state.tests_generated = test_validation.passed
        state.transition_to(Phase.TEST, f"Tests: {test_detail}")
        checkpoint_mgr.save(state)

        # Quality gate: block deploy if tests failed
        if cfg.require_tests and not state.tests_passed:
            if test_validation.extracted.get("all_passed") is False:
                return _build_failed(
                    progress, "Tests failed",
                    "Deployment blocked: tests must pass before deploy"
                )

        # ---------------------------------------------------------------
        # Phase 8: Deploy
        # ---------------------------------------------------------------
        call, deploy_validation = await run_phase(
            Phase.DEPLOY, state, project_path, progress
        )
        _track_turns(call)

        if deploy_validation.extracted.get("url"):
            state.deployment_url = deploy_validation.extracted["url"]

        # v9.0: Check for DEPLOY_BLOCKED.md or placeholder DATABASE_URL
        deploy_blocked = (project_path / "DEPLOY_BLOCKED.md").exists()
        db_placeholder = deploy_validation.extracted.get("database_placeholder", False)
        if deploy_blocked or db_placeholder:
            reason = "database not configured" if db_placeholder else "deployment blocked"
            progress.log(f"Skipping verification: {reason}")
            state.deployment_verified = False
            state.transition_to(Phase.DEPLOY, f"BLOCKED: {reason}")
            checkpoint_mgr.save(state)
        else:
            state.transition_to(Phase.DEPLOY, state.deployment_url or "deployed")
            checkpoint_mgr.save(state)

        # ---------------------------------------------------------------
        # Phase 9: Verify (skip if deploy was blocked)
        # ---------------------------------------------------------------
        if not deploy_blocked and not db_placeholder:
            call, verify_validation = await run_phase(
                Phase.VERIFY, state, project_path, progress
            )
            _track_turns(call)

            verified = verify_validation.extracted.get("verified", False)
            state.deployment_verified = verified
            state.transition_to(Phase.VERIFY, "Passed" if verified else "Partial")
            checkpoint_mgr.save(state)

        # ---------------------------------------------------------------
        # Build complete
        # ---------------------------------------------------------------
        state.mark_completed(state.deployment_url)

        # Compute quality score
        quality_report = compute_quality_score(state)
        quality = f"{quality_report.grade} ({quality_report.score}%)"

        result = BuildResult(
            success=True,
            url=state.deployment_url,
            quality=quality,
            duration_s=progress.total_duration_s,
            test_count=test_detail,
            spec_coverage=f"{audit_validation.extracted.get('requirements_met', '?')}/{audit_validation.extracted.get('requirements_total', '?')}",
            phase_results=progress.results,
        )

        progress.build_complete(state.deployment_url, quality)
        return result

    except _TurnLimitExceeded as e:
        state.mark_failed(str(e))
        checkpoint_mgr.save(state)
        progress.build_failed(str(e))
        return BuildResult(success=False, reason=str(e),
                           duration_s=progress.total_duration_s,
                           phase_results=progress.results)

    except KeyboardInterrupt:
        state.mark_failed("Interrupted by user")
        checkpoint_mgr.save(state)
        progress.build_failed("Interrupted by user")
        return BuildResult(success=False, reason="Interrupted by user",
                           duration_s=progress.total_duration_s)

    except Exception as e:
        state.mark_failed(str(e))
        checkpoint_mgr.save(state)
        progress.build_failed(str(e))
        return BuildResult(success=False, reason=str(e),
                           duration_s=progress.total_duration_s)


class _TurnLimitExceeded(Exception):
    """Raised when total turns across all phases exceeds MAX_TOTAL_TURNS."""
    pass


def _build_failed(progress: ProgressReporter, reason: str, detail: str) -> BuildResult:
    """Helper to report a build failure."""
    progress.build_failed(f"{reason}: {detail}")
    return BuildResult(
        success=False,
        reason=f"{reason}: {detail}",
        duration_s=progress.total_duration_s,
        phase_results=progress.results,
    )


def _get_phase_count(cfg: BuildConfig) -> int:
    """Get total phase count based on build mode."""
    base = 9  # analyze, design, review, build, audit, test, deploy, verify = 8, but audit+test count as 2
    if cfg.enrich:
        base += 1  # add enrichment
    if cfg.mode == "enhancement":
        base -= 1  # no analysis phase in enhancement
    return base


def _parse_stack_decision(project_path: Path) -> str:
    """Parse STACK_DECISION.md and extract the stack_id."""
    stack_file = project_path / "STACK_DECISION.md"
    if not stack_file.exists():
        return "nextjs-supabase"

    content = stack_file.read_text()
    match = re.search(r'\*\*Stack ID\*\*:\s*`?(\S+?)`?\s*$', content, re.MULTILINE)
    if match:
        return match.group(1).strip('`')

    for stack_id in ["nextjs-supabase", "nextjs-prisma", "rails", "expo-supabase", "swift-swiftui"]:
        if stack_id in content.lower():
            return stack_id

    return "nextjs-supabase"


def _setup_enhancement_mode(
    state: AgentState, cfg: BuildConfig, project_path: Path
) -> None:
    """Set up enhancement mode by copying existing design."""
    source_design = Path(cfg.design_file).resolve()
    if source_design.exists():
        shutil.copy(source_design, project_path / "DESIGN.md")

    # Infer stack from existing design
    design_content = (project_path / "DESIGN.md").read_text() if (project_path / "DESIGN.md").exists() else ""
    if "prisma" in design_content.lower():
        state.stack_id = cfg.stack or "nextjs-prisma"
    elif "supabase" in design_content.lower():
        state.stack_id = cfg.stack or "nextjs-supabase"
    elif "swift" in design_content.lower():
        state.stack_id = cfg.stack or "swift-swiftui"
    else:
        state.stack_id = cfg.stack or "nextjs-supabase"

    state.enhancement_mode = True
    state.enhance_features = cfg.enhance_features

    # Write STACK_DECISION.md for the builder
    features = ", ".join(cfg.enhance_features) if cfg.enhance_features else "enhancement"
    (project_path / "STACK_DECISION.md").write_text(
        f"# Stack Decision\n\n"
        f"## Product Analysis\n"
        f"- **Type**: Enhancement of existing design\n"
        f"- **Key Features**: {features}\n\n"
        f"## Selected Stack\n"
        f"- **Stack ID**: {state.stack_id}\n"
    )


