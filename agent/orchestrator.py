"""Orchestrator for Product Agent v11.1.

This is the brain of the pipeline. It runs 9 phases sequentially (with Audit+Test
in parallel), validating output between each phase. If a phase fails, it retries
with the error injected into the prompt so Claude can learn from the mistake.

Replaces the v7.0 monolithic single-call architecture where one 200-turn subprocess
did everything. Now Python controls ordering, validation, and retry logic.

Key design decisions:
- Each phase is a separate Claude SDK call (not one giant conversation)
- Python validates between phases so failures are caught early
- Errors from failed phases are injected into retry prompts (error learning)
- Audit and Test run in parallel to save wall-clock time
- Enhancement mode replaces Analysis+Design+Review with a single Enhance phase
- Resume (--resume) skips completed phases by checking artifacts on disk
"""

import asyncio
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .state import AgentState, Phase, ReviewStatus, create_initial_state
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
    """Configuration for a product build.

    Controls which phases run, what stack to use, and how strict the
    quality gates are. Passed to build_product() from main.py CLI args.
    """
    stack: str | None = None                   # Force a specific stack (None = auto-select)
    mode: str = "standard"                     # standard | plugin | host | enhancement
    enrich: bool = False                       # Enable prompt enrichment phase (researches domain)
    enrich_url: str | None = None              # Reference URL for enrichment research
    verbose: bool = False                      # Show detailed progress output
    require_tests: bool = True                 # Block deploy if tests fail (quality gate)
    legacy: bool = False                       # Use v7.0 single-subprocess mode
    design_file: str | None = None             # Path to existing DESIGN.md (enhancement mode)
    enhance_features: list[str] = field(default_factory=list)  # Features to add in enhancement
    resume: bool = False                       # Resume from most recent checkpoint
    resume_from: str | None = None             # Resume from specific checkpoint ID


@dataclass
class BuildResult:
    """Result of a complete build. Returned by build_product().

    On success: url is the deployed URL, quality is the grade string.
    On failure: reason explains why and which phase failed.
    phase_results contains per-phase timing and status for debugging.
    """
    success: bool
    url: str | None = None                     # Deployed URL (None if deploy blocked or failed)
    quality: str | None = None                 # Grade string e.g. "A (95%)"
    duration_s: float = 0.0                    # Total wall-clock time
    test_count: str | None = None              # e.g. "14/14" (passed/total)
    spec_coverage: str | None = None           # e.g. "12/12" (requirements met/total)
    reason: str | None = None                  # Failure reason (None on success)
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

    # Set phase count based on mode
    phase_count = _get_phase_count(cfg)
    progress.set_total_phases(phase_count)

    # Initialize checkpoint manager
    checkpoint_mgr = CheckpointManager(str(project_path))

    # v9.1: Resume from checkpoint if requested
    if cfg.resume:
        loaded = None
        if cfg.resume_from:
            loaded_state = checkpoint_mgr.load(cfg.resume_from)
            if loaded_state:
                loaded = (cfg.resume_from, loaded_state)
        else:
            loaded = checkpoint_mgr.load_latest()

        if loaded:
            checkpoint_id, loaded_state = loaded
            state = loaded_state
            if cfg.stack and not state.stack_id:
                state.stack_id = cfg.stack
            state.build_mode = cfg.mode
            progress.build_resume_header(idea, state.phase.value)
            # Verify artifacts haven't been tampered with (warning only)
            if config.ENABLE_ARTIFACT_VERIFICATION:
                all_ok, mismatched = checkpoint_mgr.verify_artifacts(checkpoint_id)
                if not all_ok:
                    progress.log(
                        f"Warning: artifacts changed since checkpoint: {', '.join(mismatched)}"
                    )
        else:
            progress.log("No checkpoint found — starting fresh build")
            cfg.resume = False
            progress.build_header(idea)
    else:
        progress.build_header(idea)

    # v9.0: Track total turns across all phases
    total_turns = 0

    # Handle enhancement mode setup — copies existing design, infers stack
    if cfg.mode == "enhancement" and cfg.design_file:
        _setup_enhancement_mode(state, cfg, project_path)

    # v10.2: Track whether we're in enhancement mode for phase skipping
    is_enhancement = cfg.mode == "enhancement"

    def _track_turns(call_result: PhaseCallResult) -> None:
        """Accumulate turns across all phases and enforce the global turn limit.

        This prevents runaway builds from consuming unlimited API credits.
        The limit (MAX_TOTAL_TURNS, default 300) applies across ALL phases
        combined, not per-phase. Per-phase limits are in PhaseConfig.max_turns.

        Why isinstance guards: In tests, mocks can set num_turns to non-int values.
        getattr on config guards against mocked config modules that don't define
        MAX_TOTAL_TURNS. Both are defensive against test environments, not production.
        """
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
        # --- Phase 1: Enrich (optional) ---
        # Researches the domain and expands the one-line idea into a detailed spec.
        # Non-fatal: if enrichment fails, we just proceed with the raw idea.
        if cfg.enrich:
            if cfg.resume and _should_skip_phase(state, Phase.ENRICH, project_path):
                progress.phase_skipped("Enrich")
            else:
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

        # --- Phase 2: Analysis ---
        # Selects the best tech stack for the product idea. Fatal if it fails
        # because all subsequent phases depend on knowing the stack.
        # In enhancement mode, stack is already set by _setup_enhancement_mode.
        if is_enhancement:
            progress.phase_skipped("Analysis", f"stack: {state.stack_id} (enhancement)")
        elif cfg.resume and _should_skip_phase(state, Phase.ANALYSIS, project_path):
            progress.phase_skipped("Analysis", f"stack: {state.stack_id}")
        else:
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

        # --- Phase 3-4: Design + Review loop ---
        # Design creates DESIGN.md, Review validates it. If NEEDS_REVISION,
        # we loop back to Design (up to max_revisions times). This catches
        # architectural issues before the expensive Build phase.
        # In enhancement mode, we skip Design+Review and run Enhance instead.
        if is_enhancement:
            progress.phase_skipped("Design", "using existing design (enhancement)")
            progress.phase_skipped("Review", "skipped (enhancement)")

            # --- Enhancement Phase ---
            # Runs the enhancer agent to modify DESIGN.md with new features.
            if cfg.resume and _should_skip_phase(state, Phase.ENHANCE, project_path):
                progress.phase_skipped("Enhance", "already applied")
            else:
                call, enhance_validation = await run_phase(
                    Phase.ENHANCE, state, project_path, progress
                )
                _track_turns(call)
                if not call.success:
                    return _build_failed(progress, "Enhancement failed", call.error)

                state.transition_to(Phase.ENHANCE, "Design enhanced")
                checkpoint_mgr.save(state)

        elif cfg.resume and _should_skip_phase(state, Phase.REVIEW, project_path):
            progress.phase_skipped("Design", f"revision {state.design_revision}")
            progress.phase_skipped("Review", "approved")
        else:
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
                    state.review_status = ReviewStatus.APPROVED
                    break

                # Not approved — prepare for next revision
                progress.log(f"Design needs revision ({revision + 1}/{max_revisions})")
                if revision >= max_revisions:
                    progress.log("Max revisions reached — proceeding with current design")
                    break

            state.transition_to(Phase.REVIEW, "Approved" if approved else "Max revisions")
            checkpoint_mgr.save(state)

        # --- Phase 5: Build with smart retry ---
        # The builder implements the full application. If it fails, the error
        # message is injected into the next attempt's prompt so Claude can
        # learn from the specific failure (missing imports, wrong patterns, etc.)
        if cfg.resume and _should_skip_phase(state, Phase.BUILD, project_path):
            progress.phase_skipped("Build", f"{state.build_attempts} attempt(s)")
        else:
            max_attempts = config.MAX_BUILD_ATTEMPTS
            build_succeeded = False
            retry_context = None  # Error context injected into retry prompts

            # v9.1: If resuming into BUILD, inject lessons from similar past builds
            if cfg.resume:
                from .history import BuildHistory
                history = BuildHistory(str(project_path))
                lessons = history.get_relevant_lessons(idea)
                if lessons:
                    retry_context = f"Previous build lessons:\n{lessons}"

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

                # Route validation strategy: lenient on early attempts, strict on final.
                # On retries, missing routes become context for the next attempt.
                # On final attempt, missing routes are hard errors that fail the build.
                is_final = attempt == max_attempts - 1
                route_check = validate_build_routes(project_path, strict=is_final)
                missing = route_check.extracted.get("missing_routes", [])
                if missing and is_final:
                    # Final attempt: missing routes are hard errors
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

        # --- Phase 6-7: Audit + Test (parallel) ---
        # Run both in parallel via asyncio.gather to save 20-60 seconds.
        # Audit checks if the build matches the original requirements.
        # Test generates and runs automated tests.
        # NOTE: audit_validation and test_validation are initialized to None here
        # because the skip branch doesn't create them, but the quality gate and
        # build-complete sections reference them. Without this, resume with both
        # phases skipped causes NameError.
        audit_skip = cfg.resume and _should_skip_phase(state, Phase.AUDIT, project_path)
        test_skip = cfg.resume and _should_skip_phase(state, Phase.TEST, project_path)
        audit_validation = None  # Set by the non-skip branch below
        test_validation = None   # Set by the non-skip branch below

        if audit_skip and test_skip:
            progress.phase_skipped("Audit", f"{state.spec_audit_discrepancies} discrepancies")
            progress.phase_skipped("Test")
            test_detail = ""
        else:
            # Re-run both even if only one was incomplete — simpler than partial re-run
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

            # Process audit results — compute discrepancies as (total - met).
            # The auditor's YAML front-matter may report total as an int or "?"
            # when it can't determine the total requirement count. We guard with
            # isinstance so "?" doesn't cause a TypeError in the subtraction.
            # When total is unknown, discrepancies defaults to 0 (optimistic).
            state.spec_audit_completed = True
            if audit_validation.extracted.get("requirements_met"):
                met = audit_validation.extracted["requirements_met"]
                total = audit_validation.extracted.get("requirements_total", "?")
                state.spec_audit_discrepancies = max(0, (total if isinstance(total, int) else 0) - met)
            elif audit_validation.extracted.get("discrepancies"):
                state.spec_audit_discrepancies = audit_validation.extracted["discrepancies"]

            # v10.0: Track CRITICAL findings count from audit validation
            if audit_validation.extracted.get("critical_count"):
                state.spec_audit_critical_count = audit_validation.extracted["critical_count"]

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

        # Quality gate: block deploy if tests failed. This prevents deploying
        # known-broken code. Can be disabled with require_tests=False.
        #
        # The check is simple: if require_tests is on AND state says tests didn't
        # pass, block the deploy. state.tests_passed is set by either:
        # - The test phase that just ran (line ~391-393 above)
        # - A previous run's checkpoint (loaded on resume)
        # Either way, state.tests_passed is the single source of truth here.
        if cfg.require_tests and not state.tests_passed:
            return _build_failed(
                progress, "Tests failed",
                "Deployment blocked: tests must pass before deploy"
            )

        # --- Phase 8: Deploy ---
        # Deploys to production (Vercel/Railway/TestFlight). Checks for
        # DEPLOY_BLOCKED.md which the deployer creates if DATABASE_URL is
        # a placeholder — prevents deploying a broken app.
        if cfg.resume and _should_skip_phase(state, Phase.DEPLOY, project_path):
            progress.phase_skipped("Deploy", state.deployment_url or "blocked")
            deploy_blocked = (project_path / "DEPLOY_BLOCKED.md").exists()
            db_placeholder = False
        else:
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

        # --- Phase 9: Verify (skip if deploy was blocked) ---
        # Tests the deployed app by hitting actual endpoints. Skipped if
        # deployment was blocked (no point verifying a non-deployed app).
        if not deploy_blocked and not db_placeholder:
            if cfg.resume and _should_skip_phase(state, Phase.VERIFY, project_path):
                progress.phase_skipped("Verify", "Passed" if state.deployment_verified else "Partial")
            else:
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

        # When audit+test were skipped on resume, audit_validation is None.
        # Fall back to state fields which were populated in the original run.
        if audit_validation is not None:
            spec_coverage_str = f"{audit_validation.extracted.get('requirements_met', '?')}/{audit_validation.extracted.get('requirements_total', '?')}"
        else:
            # Skipped phases — use approximate data from checkpoint state
            spec_coverage_str = f"?/? ({state.spec_audit_discrepancies} discrepancies)"

        result = BuildResult(
            success=True,
            url=state.deployment_url,
            quality=quality,
            duration_s=progress.total_duration_s,
            test_count=test_detail,
            spec_coverage=spec_coverage_str,
            phase_results=progress.results,
        )

        progress.build_complete(state.deployment_url, quality)
        return result

    except _TurnLimitExceeded as e:
        # Global turn limit exceeded — save checkpoint so user can resume later
        state.mark_failed(str(e))
        checkpoint_mgr.save(state)
        progress.build_failed(str(e))
        return BuildResult(success=False, reason=str(e),
                           duration_s=progress.total_duration_s,
                           phase_results=progress.results)

    except KeyboardInterrupt:
        # User pressed Ctrl+C — save progress so --resume can pick up later
        state.mark_failed("Interrupted by user")
        checkpoint_mgr.save(state)
        progress.build_failed("Interrupted by user")
        return BuildResult(success=False, reason="Interrupted by user",
                           duration_s=progress.total_duration_s)

    except Exception as e:
        # Unexpected error (SDK crash, network failure, etc.) — save state
        # and return a failure result rather than letting the exception propagate.
        # This ensures the CLI always gets a BuildResult, even on crashes.
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
    # Base phases: analyze + design + review + build + audit + test + deploy + verify = 8
    # But we count audit+test as 2 separate phases in the progress display = 9
    base = 9
    if cfg.enrich:
        base += 1  # add enrichment
    if cfg.mode == "enhancement":
        # Enhancement: skip analysis + design + review (-3), add enhance (+1) = net -2
        base -= 2
    return base


def _parse_stack_decision(project_path: Path) -> str:
    """Parse STACK_DECISION.md and extract the stack_id.

    Tries three strategies in order:
    1. Regex match on "**Stack ID**: `nextjs-supabase`" format
    2. Substring search for any known stack ID
    3. Default to nextjs-supabase (safest default — most tested stack)
    """
    stack_file = project_path / "STACK_DECISION.md"
    if not stack_file.exists():
        return "nextjs-supabase"  # Default: most tested and reliable stack

    content = stack_file.read_text()

    # Strategy 1: Parse the structured "**Stack ID**: `value`" line
    match = re.search(r'\*\*Stack ID\*\*:\s*`?(\S+?)`?\s*$', content, re.MULTILINE)
    if match:
        return match.group(1).strip('`')

    # Strategy 2: Look for any known stack ID mentioned anywhere in the file.
    # Order matters: more specific IDs first to avoid "nextjs" matching the wrong stack.
    # This list must include all stacks from criteria.py.
    known_stacks = [
        "nextjs-supabase", "nextjs-prisma", "django-htmx", "sveltekit",
        "astro", "rails", "expo-supabase", "swift-swiftui",
    ]
    for stack_id in known_stacks:
        if stack_id in content.lower():
            return stack_id

    # Strategy 3: Fall back to default
    return "nextjs-supabase"


def _setup_enhancement_mode(
    state: AgentState, cfg: BuildConfig, project_path: Path
) -> None:
    """Set up enhancement mode by copying existing design and inferring the stack.

    Enhancement mode adds features to an already-built product. Instead of running
    Analysis + Design + Review, we copy the existing DESIGN.md, infer the stack from
    its contents, and let the Enhance phase modify it.

    The stack is inferred by keyword matching (prisma → nextjs-prisma, etc.).
    An explicit --stack flag overrides the inference. If nothing matches, we
    default to nextjs-supabase as the safest choice.
    """
    source_design = Path(cfg.design_file).resolve()
    if source_design.exists():
        shutil.copy(source_design, project_path / "DESIGN.md")

    # Infer stack from keywords in existing design.
    # Explicit --stack flag (cfg.stack) always takes priority via the `or` chain.
    # Order: prisma before supabase because Prisma projects also mention supabase sometimes.
    design_content = (project_path / "DESIGN.md").read_text() if (project_path / "DESIGN.md").exists() else ""
    if "prisma" in design_content.lower():
        state.stack_id = cfg.stack or "nextjs-prisma"
    elif "supabase" in design_content.lower():
        state.stack_id = cfg.stack or "nextjs-supabase"
    elif "swift" in design_content.lower():
        state.stack_id = cfg.stack or "swift-swiftui"
    elif "django" in design_content.lower():
        state.stack_id = cfg.stack or "django-htmx"
    elif "svelte" in design_content.lower():
        state.stack_id = cfg.stack or "sveltekit"
    elif "astro" in design_content.lower():
        state.stack_id = cfg.stack or "astro"
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


# Phase ordering for resume skip logic. Phases with the same order number
# run in parallel (AUDIT + TEST). FAILED gets -1 so artifact checks
# determine the resume point instead of ordering.
_PHASE_ORDER: dict[Phase, int] = {
    Phase.INIT: 0,
    Phase.ENRICH: 1,
    Phase.ANALYSIS: 2,
    Phase.DESIGN: 3,
    Phase.REVIEW: 4,
    Phase.ENHANCE: 4,  # Same order as REVIEW — replaces Design+Review in enhancement mode
    Phase.BUILD: 5,
    Phase.AUDIT: 6,
    Phase.TEST: 6,  # Same order as AUDIT — they run in parallel
    Phase.DEPLOY: 7,
    Phase.VERIFY: 8,
    Phase.COMPLETE: 9,
    Phase.FAILED: -1,
}


def _should_skip_phase(state: AgentState, target: Phase, project_path: Path) -> bool:
    """Check if a phase can be skipped during resume.

    A phase is skippable when the checkpoint state shows it already completed
    AND its expected artifacts still exist on disk. If the checkpoint state
    is FAILED, we fall back to artifact checks alone to determine the resume
    point (since the phase field is no longer meaningful).
    """
    state_order = _PHASE_ORDER.get(state.phase, -1)
    target_order = _PHASE_ORDER.get(target, 99)

    # FAILED state: determine actual progress from artifacts, not phase ordering
    if state.phase == Phase.FAILED:
        return _artifact_exists(target, project_path, state)

    # If checkpoint hasn't reached this phase yet, can't skip
    if target_order > state_order:
        return False

    # Checkpoint indicates this phase was completed — verify artifact integrity
    return _artifact_exists(target, project_path, state)


def _artifact_exists(target: Phase, project_path: Path, state: AgentState) -> bool:
    """Check if a phase's expected artifacts exist on disk.

    Each phase produces specific files or state changes. This function verifies
    those outputs are still present, so we don't skip a phase whose artifacts
    were deleted after the checkpoint was saved.
    """
    if target == Phase.ENRICH:
        return state.prompt_enriched

    if target == Phase.ANALYSIS:
        return bool(state.stack_id) and (project_path / "STACK_DECISION.md").exists()

    if target == Phase.DESIGN:
        return (project_path / "DESIGN.md").exists()

    if target == Phase.REVIEW:
        return (project_path / "DESIGN.md").exists()

    if target == Phase.ENHANCE:
        # Enhancement is done if DESIGN.md exists and state shows enhancement mode
        return state.enhancement_mode and (project_path / "DESIGN.md").exists()

    if target == Phase.BUILD:
        return _has_source_code(project_path)

    if target == Phase.AUDIT:
        return state.spec_audit_completed and (project_path / "SPEC_AUDIT.md").exists()

    if target == Phase.TEST:
        return state.tests_generated and (project_path / "TEST_RESULTS.md").exists()

    if target == Phase.DEPLOY:
        return bool(state.deployment_url) or (project_path / "DEPLOY_BLOCKED.md").exists()

    if target == Phase.VERIFY:
        # VERIFICATION.md is the artifact — deployment_verified defaults to False
        # so checking the file is more reliable than the boolean flag
        return (project_path / "VERIFICATION.md").exists()

    return False


def _has_source_code(project_path: Path) -> bool:
    """Check if project has source code directories with files.

    Looks for common source directories (src/, Sources/, app/, lib/)
    and verifies they contain at least one file with an extension.
    """
    for dir_name in ("src", "Sources", "app", "lib"):
        d = project_path / dir_name
        if d.exists() and any(d.rglob("*.*")):
            return True
    return False
