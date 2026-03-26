#!/usr/bin/env python3
"""Product Agent v8.0 - Autonomous app builder.

Uses claude-code-sdk for phase-by-phase orchestration. Each phase gets its own
focused Claude call. Python validates between phases, handles retries with error
injection, and streams progress in real time.

v8.0: Phase-by-phase orchestration, parallel audit+test, build memory, quality scoring
v7.0: Swift/SwiftUI plugin architecture with host/plugin build modes
v6.0: Spec auditing, optional prompt enrichment
v5.0: Deployment-aware stack selection, automated testing, post-deploy verification

Usage:
    python -m agent.main "Build me a todo app"
    python -m agent.main --project-dir ./my-app "Build me a todo app"
    python -m agent.main --stack nextjs-prisma "Build a marketplace"
    python -m agent.main --stack swift-swiftui --mode host "NoCloud BS host app"
    python -m agent.main --stack swift-swiftui --mode plugin "Photo gallery plugin"
    python -m agent.main --resume "Build me a todo app"
    python -m agent.main --legacy "Build me a todo app"
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

from .cli_runner import run_claude, check_claude_cli, check_claude_auth
from .agents.definitions import get_agents, get_agent_prompt
from .mcp.servers import get_mcp_servers, get_mcp_config_json
from .state import AgentState, Phase, ReviewStatus, create_initial_state, get_next_phase
from .checkpoints import CheckpointManager, save_checkpoint, resume_from_checkpoint
from .recovery import get_build_fix_prompt, get_deploy_fix_prompt
from .stacks.selector import select_stack, get_all_stacks_for_prompt
from .orchestrator import BuildConfig, BuildResult, build_product as build_product_v8
from . import config

# Hard-coded retry limits (enforced, not just documented)
MAX_DESIGN_REVISIONS = 2
MAX_BUILD_ATTEMPTS = 5


def _get_phase_limits_context(state: AgentState) -> str:
    """Generate context about remaining attempts for the orchestrator.

    This helps enforce limits in the prompt since the orchestrator
    can see how many attempts remain.
    """
    design_remaining = max(0, MAX_DESIGN_REVISIONS - state.design_revision)
    build_remaining = max(0, MAX_BUILD_ATTEMPTS - state.build_attempts)
    test_remaining = max(0, config.MAX_TEST_ATTEMPTS - state.test_attempts)

    test_status = ""
    if config.ENABLE_TEST_GENERATION:
        test_status = f"""
## Test Status (v5.1)
- Test generation: ENABLED
- Test attempts used: {state.test_attempts}/{config.MAX_TEST_ATTEMPTS} (remaining: {test_remaining})
- Tests generated: {'Yes' if state.tests_generated else 'No'}
- Tests passed: {'Yes' if state.tests_passed else 'No'}
- Require passing tests: {'Yes' if config.REQUIRE_PASSING_TESTS else 'No'}
"""

    audit_status = ""
    if config.ENABLE_SPEC_AUDIT:
        audit_remaining = max(0, config.MAX_AUDIT_FIX_ATTEMPTS - (1 if state.audit_fix_attempted else 0))
        audit_status = f"""
## Spec Audit Status (v6.0)
- Spec audit: ENABLED
- Audit completed: {'Yes' if state.spec_audit_completed else 'No'}
- Discrepancies found: {state.spec_audit_discrepancies}
- Fix attempts remaining: {audit_remaining}/{config.MAX_AUDIT_FIX_ATTEMPTS}
"""

    return f"""
## Current Limits Status (ENFORCED)
- Design revisions used: {state.design_revision}/{MAX_DESIGN_REVISIONS} (remaining: {design_remaining})
- Build attempts used: {state.build_attempts}/{MAX_BUILD_ATTEMPTS} (remaining: {build_remaining})
{test_status}{audit_status}
IMPORTANT: If limits are exhausted, you MUST report failure instead of retrying.
- If design_remaining is 0, proceed to build even if review says NEEDS_REVISION
- If build_remaining is 0, report build failure and stop
"""


def _get_agents_for_cli() -> dict:
    """Get agent definitions in format suitable for CLI --agents flag."""
    agents = get_agents()
    cli_agents = {}

    for name, agent_config in agents.items():
        cli_agents[name] = {
            "description": agent_config["description"],
            "prompt": agent_config["prompt"],
            "tools": agent_config.get("tools", []),
        }
        # Add model if specified
        if "model" in agent_config:
            cli_agents[name]["model"] = agent_config["model"]

    return cli_agents


def _parse_stack_decision(project_path: Path) -> str | None:
    """Parse STACK_DECISION.md and extract the stack_id."""
    stack_file = project_path / "STACK_DECISION.md"
    if not stack_file.exists():
        return None

    content = stack_file.read_text()

    # Look for "Stack ID: nextjs-supabase" or similar patterns
    match = re.search(r'\*\*Stack ID\*\*:\s*(\S+)', content)
    if match:
        return match.group(1).strip('`')

    # Fallback: look for stack name in content
    for stack_id in ["nextjs-supabase", "nextjs-prisma", "rails", "expo-supabase", "swift-swiftui"]:
        if stack_id in content.lower():
            return stack_id

    return "nextjs-supabase"  # Default


def _write_mcp_config(project_path: Path) -> str | None:
    """Write MCP config file and return path if servers are configured."""
    mcp_config = get_mcp_config_json()
    if not mcp_config.get("mcpServers"):
        return None

    config_path = project_path / ".mcp.json"
    import json
    config_path.write_text(json.dumps(mcp_config, indent=2))
    return str(config_path)


# v6.0 Orchestrator prompt with iterative flow, testing, audit, and verification
ORCHESTRATOR_SYSTEM_PROMPT = """You are an autonomous Product Agent v6.0 that builds web applications end-to-end.

## Your Mission
Take the product idea provided and deliver a deployed, TESTED, VERIFIED, working application.
Work autonomously. Don't ask questions. Make reasonable decisions.

## CRITICAL: Verify Phase Outputs Before Proceeding

Before starting each phase, VERIFY that the previous phase created its required artifact:
- Before DESIGN: Verify STACK_DECISION.md exists (created by analyzer)
- Before BUILD: Verify DESIGN.md exists (created by designer)
- Before AUDIT: Verify source code exists in src/ or Sources/ (created by builder)
- Before TEST: Verify SPEC_AUDIT.md exists (created by auditor)
- Before DEPLOY: Verify TEST_RESULTS.md exists AND status is PASSED (created by tester)

If any artifact is MISSING, re-run the responsible subagent before continuing.
If TEST_RESULTS.md status is FAILED, DO NOT proceed to DEPLOY — report build failure instead.

## Process (Iterative with Feedback Loops)

### Phase 1: Analysis
1. Use the `analyzer` subagent to analyze the product and select a stack
2. Read STACK_DECISION.md to confirm:
   - Stack choice
   - Deployment target (vercel/railway/etc.)
   - Database type (postgresql - NEVER sqlite for serverless!)
   - Compatibility check passed

### Phase 2: Design (with review loop)
1. Use the `designer` subagent to create DESIGN.md
2. Use the `reviewer` subagent to validate the design
3. Read REVIEW.md:
   - If "APPROVED": proceed to Phase 3
   - If "NEEDS_REVISION": use `designer` again with the feedback
   - IMPORTANT: Check the "Current Limits Status" in your prompt - if design revisions exhausted, proceed anyway

### Phase 3: Build (with error recovery)
1. Use the `builder` subagent to implement the app
2. The builder reads ORIGINAL_PROMPT.md to cross-reference specific values (v6.0)
3. The builder will set up test infrastructure (vitest/jest/minitest)
4. If build fails, check the error and use `builder` again to fix
5. IMPORTANT: Check the "Current Limits Status" in your prompt - if build attempts exhausted, report failure

### Phase 3.5: Spec Audit (v6.0)
1. Use the `auditor` subagent to verify the build matches ORIGINAL_PROMPT.md
2. Read SPEC_AUDIT.md:
   - If "PASS": proceed to Phase 4
   - If "NEEDS_FIX": use `builder` to fix CRITICAL discrepancies (max 1 fix attempt)
3. Proceed to Phase 4 regardless after fix attempt

### Phase 4: Test (v5.1)
1. Use the `tester` subagent to generate and run tests
2. Read TEST_RESULTS.md:
   - If "PASSED": proceed to Phase 5
   - If "FAILED": attempt to fix tests or code (max 3 attempts)
3. **BLOCKING**: If REQUIRE_PASSING_TESTS is enabled (see Test Status) AND tests FAILED after all attempts, you MUST NOT proceed to Phase 5. Instead, report failure: "Build blocked: tests failed after N attempts."

### Phase 5: Deploy (with pre-validation)
**PRE-CHECK**: Before calling the deployer, verify:
- TEST_RESULTS.md exists and shows Status: PASSED
- If REQUIRE_PASSING_TESTS is enabled and tests failed, STOP HERE and report failure
1. Use the `deployer` subagent to deploy
2. If DEPLOY_BLOCKED.md exists, address the compatibility issue first
3. Get the production URL

### Phase 6: Verify (v5.0)
1. Use the `verifier` subagent to test the deployed app
2. Read VERIFICATION.md:
   - If "PASSED": deployment is complete
   - If "PARTIAL": document limitations and complete
   - If "FAILED": attempt to fix and re-verify (max 2 attempts)
3. Only report success after PASSED or PARTIAL verification

## Subagent Usage
Use the Task tool with these subagent types:
- `analyzer` - Selects stack AND validates deployment compatibility (use FIRST)
- `designer` - Creates DESIGN.md (use after analyzer)
- `reviewer` - Validates design (use after designer)
- `builder` - Implements app AND sets up test infrastructure (use after design APPROVED)
- `auditor` - Verifies build matches original prompt (use AFTER builder, BEFORE tester) [v6.0]
- `tester` - Generates and runs tests (use AFTER auditor, BEFORE deployer) [v5.1]
- `deployer` - Deploys to production (use after tests pass)
- `verifier` - Tests deployed app (use AFTER deployer succeeds) [v5.0]

## Safety Rules
NEVER run these commands:
- rm -rf / or rm -rf ~
- sudo anything
- Commands that modify system files outside the project

## Critical: Database Compatibility (v5.0)
- NEVER use SQLite with Vercel/serverless deployments
- Always use PostgreSQL (Supabase, Neon, Vercel Postgres)
- If analyzer outputs SQLite + Vercel, STOP and fix before building

## Swift Build Mode (v7.0)
For Swift/SwiftUI builds, use `--mode host` or `--mode plugin` via CLI (or the analyzer infers the mode).
Swift builds skip web deployment (Vercel/Railway) and instead verify via `swift build` + `swift test`.
The verifier agent checks build success instead of URL reachability for Swift projects.

## Rules
- Don't ask the user questions. Make decisions.
- If something is unclear, use reasonable defaults.
- Handle errors by attempting fixes, not by asking.
- Track progress and provide status updates.
- Work through phases sequentially.
- Tests must pass before deployment (if REQUIRE_PASSING_TESTS is enabled).

## Output
When complete and VERIFIED, your final message should be ONLY:
"Your app is live at https://[deployment-url] - Tests: PASSED - Verification: PASSED"

If verification is partial:
"Your app is live at https://[url] - Tests: PASSED - Verification: PARTIAL (see VERIFICATION.md)"

If deployment blocked:
"Deployment blocked: [reason]. See DEPLOY_BLOCKED.md for fix instructions."
"""

# Enhancement mode orchestrator prompt
ENHANCEMENT_ORCHESTRATOR_PROMPT = """You are an autonomous Product Agent v6.0 in ENHANCEMENT MODE.

## Your Mission
Take the existing DESIGN.md and enhance it with the requested features, then build, deploy, and VERIFY.
Work autonomously. Don't ask questions. Make reasonable decisions.

## Enhancement Mode Rules
- PRESERVE all existing functionality from the original design
- ADD the requested features cleanly integrated with existing architecture
- EXTEND data models with new tables/fields, don't restructure existing ones
- MAINTAIN the multi-tenant architecture for all new features
- FOLLOW existing patterns (naming conventions, code style, etc.)

## Process (Enhancement Flow)

### Phase 1: Enhancement
1. Read the existing DESIGN.md thoroughly
2. Use the `enhancer` subagent to add the requested features
3. The enhancer will create ENHANCED_DESIGN.md with all original content plus new features

### Phase 2: Review
1. Use the `reviewer` subagent to validate the enhanced design
2. If NEEDS_REVISION: use enhancer again with feedback (max 2 revisions)
3. Once APPROVED: rename ENHANCED_DESIGN.md to DESIGN.md

### Phase 3: Build
1. Use the `builder` subagent to implement the enhanced app
2. If build fails, analyze error and fix (max 5 attempts)

### Phase 3.5: Audit (v7.0)
1. Use the `auditor` subagent to verify the enhanced build matches ORIGINAL_PROMPT.md
2. Specifically verify that enhanced features don't break existing functionality
3. If NEEDS_FIX: use builder to fix CRITICAL discrepancies (max 1 fix attempt)

### Phase 4: Test
1. Use the `tester` subagent to generate and run tests
2. Tests MUST cover both original AND enhanced functionality
3. If REQUIRE_PASSING_TESTS is enabled and tests fail, DO NOT proceed to deploy

### Phase 5: Deploy
1. Use the `deployer` subagent to deploy
2. If DEPLOY_BLOCKED.md exists, address the compatibility issue first
3. Get the production URL

### Phase 6: Verify (v5.0)
1. Use the `verifier` subagent to test the deployed app
2. Read VERIFICATION.md and confirm functionality
3. Only report success after PASSED or PARTIAL verification

## Subagent Usage
- `enhancer` - Adds features to existing DESIGN.md (use FIRST in enhancement mode)
- `reviewer` - Validates enhanced design
- `builder` - Implements the enhanced app
- `auditor` - Verifies build matches requirements (use AFTER builder, BEFORE tester)
- `tester` - Generates and runs tests (use AFTER auditor, BEFORE deployer)
- `deployer` - Deploys to production
- `verifier` - Tests deployed app (use AFTER deployer succeeds) [v5.0]

## Output
When complete and VERIFIED: "Your enhanced app is live at https://[deployment-url] - Verification: PASSED"
"""

# v7.0: Plugin mode orchestrator prompt
PLUGIN_ORCHESTRATOR_PROMPT = """You are an autonomous Product Agent v7.0 that builds Swift Package plugin modules for the NoCloud BS app.

## Your Mission
Take the plugin idea provided and deliver a complete, tested Swift Package that conforms to the NCBSPlugin protocol.
Work autonomously. Don't ask questions. Make reasonable decisions.

## Context
NoCloud BS is an iOS app that uses a patented 10:1 lossless compression algorithm (SHA-256 verified)
to replace cloud storage with local storage. Plugins are self-contained Swift Packages that snap into
the host app via the NCBSPlugin protocol, receiving shared services through PluginContext.

## Process

### Phase 1: Analysis
1. Use the `analyzer` subagent to analyze the plugin idea
2. Confirm stack is `swift-swiftui` and mode is `plugin`
3. Verify STACK_DECISION.md was created with Stack ID and Build Mode fields

### Phase 2: Design
1. Use the `designer` subagent to create DESIGN.md with:
   - Plugin manifest (id, name, description, icon, version)
   - Data models (Codable structs)
   - Views hierarchy (MainView, SettingsView, components)
   - ViewModels with load/save lifecycle
   - Storage key namespace
   - Required PluginPermissions
2. Use the `reviewer` subagent to validate the design

### Phase 3: Build
1. Use the `builder` subagent to implement the Swift Package
2. **FIRST**: Builder MUST create `NCBSPluginSDK/` as a local package with the EXACT protocol definitions
   from the builder prompt (NCBSPlugin, PluginContext as protocol, service protocols, PluginPermission).
   Do NOT let the builder simplify or redesign the SDK — it must match the spec exactly.
3. Builder then creates plugin Package.swift with `.package(path: "./NCBSPluginSDK")` dependency,
   implements NCBSPlugin conformance, creates views/models/viewmodels
4. Plugin's `PluginManifest.swift` must use the `PluginManifest.pluginType` struct pattern (NOT typealias, NOT a data struct)
5. Verify with `swift build`

### Phase 4: Audit (v6.0)
1. Use the `auditor` subagent to verify the build matches ORIGINAL_PROMPT.md
2. Specifically verify:
   - NCBSPlugin conformance with ALL required protocol members (static id/name/description/icon/version, init(context:), mainView)
   - `PluginContext` is a **protocol** in NCBSPluginSDK (NOT a struct or class)
   - Service protocols exist: `CompressionServiceProtocol`, `StorageServiceProtocol`, `NetworkServiceProtocol`
   - PluginManifest.swift uses `pluginType: any NCBSPlugin.Type` pattern (NOT typealias, NOT data struct)
   - Plugin ID format: `com.nocloudbs.[slug]`
   - All views and models from DESIGN.md have corresponding files

### Phase 5: Test
1. Use the `tester` subagent to generate and run XCTests
2. Minimum 8 tests (3 ViewModel, 2 plugin lifecycle, 2 model, 1 service)
3. Run with `swift test`

### Phase 5.5: Pre-Package Verification
1. Verify `swift test` passes (ALL tests green) — do NOT proceed to packaging if tests fail
2. Verify `swift package resolve` succeeds
3. Verify `swift build` produces no errors

### Phase 6: Package
1. All verifications from Phase 5.5 must have passed
2. The plugin is ready to be added to the host app's Package.swift

## Required Artifact Files
Each phase MUST create its artifact file. Verify these exist before reporting success:

| Phase | File | Created By |
|-------|------|-----------|
| Analysis | STACK_DECISION.md | analyzer |
| Design | DESIGN.md | designer |
| Review | REVIEW.md | reviewer |
| Build | (source files) | builder |
| Audit | SPEC_AUDIT.md | auditor |
| Test | TEST_RESULTS.md | tester |

If any artifact is missing after its phase completes, instruct the responsible subagent to create it.

## Subagent Usage
- `analyzer` - Confirms swift-swiftui stack (use FIRST)
- `designer` - Creates DESIGN.md with plugin architecture
- `reviewer` - Validates design
- `builder` - Implements the Swift Package
- `auditor` - Verifies build matches requirements
- `tester` - Generates and runs XCTests

## Output
When complete: "Plugin package ready at [project-dir] - Tests: PASSED - swift build: OK"
"""

# v7.0: Host mode orchestrator prompt
HOST_ORCHESTRATOR_PROMPT = """You are an autonomous Product Agent v7.0 that builds the NoCloud BS plugin host app.

## Your Mission
Build the complete host application shell with plugin infrastructure, shared services,
and core UI. Work autonomously. Don't ask questions. Make reasonable decisions.

## Context
NoCloud BS is an iOS app that uses a patented 10:1 lossless compression algorithm (SHA-256 verified)
to replace cloud storage with local storage. The host app provides:
- Plugin registry for discovering and managing plugins
- Shared services (compression, storage, network) via PluginContext
- Core UI: storage dashboard with compression stats, settings
- Dynamic TabView navigation where plugins register their own tabs

## Process

### Phase 1: Analysis
1. Use the `analyzer` subagent to analyze the host app requirements
2. Confirm stack is `swift-swiftui` and mode is `host`

### Phase 2: Design
1. Use the `designer` subagent to create DESIGN.md with:
   - NCBSPluginSDK package (protocol definitions, service protocols)
   - Plugin registry architecture
   - Shared service implementations (CompressionService, StorageService, NetworkService)
   - Core views: DashboardView (storage stats, compression ratio), SettingsView
   - App entry point with plugin registration
   - Navigation architecture (TabView with dynamic plugin tabs)
2. Use the `reviewer` subagent to validate the design

### Phase 3: Build
1. Use the `builder` subagent to implement the host app
2. **FIRST**: Builder MUST create NCBSPluginSDK as a local package with ALL protocol definitions
3. Verify NCBSPluginSDK builds independently: `cd NCBSPluginSDK && swift build`
4. Then build host app with local path dependency: `.package(path: "../NCBSPluginSDK")`
5. Implement services, create host app with TabView, set up XCTest infrastructure
6. Verify with `swift build`

### Phase 4: Audit (v6.0)
1. Use the `auditor` subagent to verify completeness
2. Check NCBSPluginSDK has ALL protocols: NCBSPlugin, PluginContext, CompressionServiceProtocol, StorageServiceProtocol, NetworkServiceProtocol, PluginPermission
3. Check all service protocols have concrete implementations in host app
4. Verify registry works, DashboardView and SettingsView exist

### Phase 5: Test
1. Use the `tester` subagent to generate and run XCTests
2. Minimum 15 tests with this breakdown:
   - 3 registry tests (register, activate/deactivate, lookup)
   - 4 service tests (compression round-trip, storage save/load/delete, listKeys)
   - 3 viewmodel tests (dashboard state, settings state, loading)
   - 3 model tests (StorageStats, PluginInfo, Codable round-trip)
   - 2 integration tests (plugin registration → activation → service access)
3. Run with `swift test`

### Phase 6: Deploy
1. Verify `swift build` passes cleanly
2. If Xcode project available: `xcodebuild` archive for TestFlight

## Subagent Usage
- `analyzer` - Confirms swift-swiftui stack (use FIRST)
- `designer` - Creates DESIGN.md with host architecture
- `reviewer` - Validates design
- `builder` - Implements the host app and SDK
- `auditor` - Verifies build completeness
- `tester` - Generates and runs XCTests
- `deployer` - Builds archive for TestFlight (if applicable)

## Output
When complete: "Host app ready at [project-dir] - Tests: PASSED - swift build: OK"
"""

# Legacy v3.0 orchestrator prompt (for --legacy mode)
LEGACY_ORCHESTRATOR_PROMPT = """You are an autonomous Product Agent that builds web applications end-to-end.

## Your Mission
Take the product idea provided and deliver a deployed, working application.
Work autonomously. Don't ask questions. Make reasonable decisions.

## Stack (Non-negotiable)
- Next.js 14 (App Router, TypeScript)
- Supabase (Postgres + Auth + Storage)
- Tailwind CSS + shadcn/ui
- Vercel deployment

## Process
1. **Design**: Use the `designer` subagent to create DESIGN.md
2. **Build**: Use the `builder` subagent to implement the app
3. **Deploy**: Use the `deployer` subagent to deploy to Vercel

## Subagent Usage
Use the Task tool with these subagent types:
- `designer` - Creates DESIGN.md (use FIRST)
- `builder` - Implements the app (use after DESIGN.md exists)
- `deployer` - Deploys to Vercel (use after build passes)

## Safety Rules
NEVER run these commands:
- rm -rf / or rm -rf ~
- sudo anything
- Commands that modify system files outside the project

## Rules
- Don't ask the user questions. Make decisions.
- If something is unclear, use reasonable defaults.
- Handle errors by attempting fixes, not by asking.
- Work through design → build → deploy sequentially.

## Output
When complete, your final message should be ONLY:
"Your app is live at https://[deployment-url]"
"""


def build_product(
    idea: str,
    project_dir: str,
    enable_checkpoints: bool = False,
    force_stack: str | None = None,
    resume: bool = False,
    resume_checkpoint: str | None = None,
    legacy_mode: bool = False,
    design_file: str | None = None,
    enhance_features: list[str] | None = None,
    enrich: bool = False,
    enrich_url: str | None = None,
    build_mode: str = "standard",
    verbose: bool = False,
    json_output: bool = False,
) -> str | dict | None:
    """Run the autonomous product agent.

    v8.0: Uses phase-by-phase orchestration via claude-code-sdk by default.
    Pass legacy_mode=True to use the v7.0 single-call architecture.

    Args:
        idea: The product idea to build
        project_dir: Directory to create the project in
        enable_checkpoints: If True, pause for human approval at each phase
        force_stack: Force a specific stack (e.g., "nextjs-prisma")
        resume: If True, resume from the latest checkpoint
        resume_checkpoint: Specific checkpoint ID to resume from
        legacy_mode: If True, use v7.0 single-call architecture
        design_file: Path to existing DESIGN.md to enhance (enables enhancement mode)
        enhance_features: List of features to add (e.g., ["board-views", "dashboards"])
        enrich: If True, run prompt enrichment phase before analysis (v6.0)
        enrich_url: Optional reference URL for enrichment research (v6.0)
        build_mode: Build mode - "standard", "host", or "plugin" (v7.0)
        verbose: If True, show detailed progress output

    Returns:
        The final result message (deployment URL) or None if failed
    """
    # v8.0: Use new phase-by-phase orchestrator unless legacy mode
    if not legacy_mode:
        build_cfg = BuildConfig(
            stack=force_stack,
            mode=build_mode if not design_file else "enhancement",
            enrich=enrich,
            enrich_url=enrich_url,
            verbose=verbose,
            require_tests=config.REQUIRE_PASSING_TESTS,
            design_file=design_file,
            enhance_features=enhance_features or [],
            resume=resume,
            resume_from=resume_checkpoint,
        )
        result = asyncio.run(build_product_v8(idea, project_dir, build_cfg))

        # v12.1: Return structured dict for Shipwright JSON output mode
        if json_output:
            return {
                "success": result.success,
                "url": result.url,
                "quality": result.quality,
                "duration_s": result.duration_s,
                "test_count": result.test_count,
                "spec_coverage": result.spec_coverage,
                "reason": result.reason,
                "phase_results": [
                    {
                        "phase_name": pr.phase_name,
                        "success": pr.success,
                        "duration_s": pr.duration_s,
                        "detail": pr.detail,
                        "num_turns": pr.num_turns,
                    }
                    for pr in result.phase_results
                ],
            }

        if result.success:
            parts = []
            if result.url:
                parts.append(f"Your app is live at {result.url}")
            if result.test_count:
                parts.append(f"Tests: {result.test_count}")
            if result.quality:
                parts.append(f"Quality: {result.quality}")
            return " - ".join(parts) if parts else "Build complete"
        else:
            print(f"Build failed: {result.reason}", file=sys.stderr)
            return None
    import shutil
    # Ensure project directory exists
    project_path = Path(project_dir).resolve()
    project_path.mkdir(parents=True, exist_ok=True)

    # Initialize or resume state
    if resume or resume_checkpoint:
        result = resume_from_checkpoint(str(project_path), resume_checkpoint)
        if result:
            checkpoint_id, state, resume_prompt = result
            print(f"Resuming from checkpoint: {checkpoint_id}", file=sys.stderr)
            print(resume_prompt, file=sys.stderr)
        else:
            print("No checkpoint found, starting fresh", file=sys.stderr)
            state = create_initial_state(idea, str(project_path))
    else:
        state = create_initial_state(idea, str(project_path))

    # v6.0: Write original prompt for builder cross-reference
    if config.PASS_ORIGINAL_PROMPT_TO_BUILDER:
        (project_path / "ORIGINAL_PROMPT.md").write_text(
            f"# Original Product Prompt\n\n{idea}\n"
        )

    # Determine if we're in enhancement mode
    enhancement_mode = design_file is not None

    print(f"Building product in: {project_path}", file=sys.stderr)
    print(f"Idea: {idea}", file=sys.stderr)
    if enhancement_mode:
        print("Mode: Enhancement (adding features to existing design)", file=sys.stderr)
        print(f"Source design: {design_file}", file=sys.stderr)
        if enhance_features:
            print(f"Features to add: {', '.join(enhance_features)}", file=sys.stderr)
    elif legacy_mode:
        print("Mode: Legacy (v3.0 - fixed stack, linear flow)", file=sys.stderr)
    elif build_mode == "plugin":
        print("Mode: Plugin (v7.0 - Swift Package module)", file=sys.stderr)
    elif build_mode == "host":
        print("Mode: Host (v7.0 - iOS plugin host app)", file=sys.stderr)
    else:
        print("Mode: v7.0 (flexible stack, iterative flow)", file=sys.stderr)
        if enrich:
            print("Enrichment: ENABLED", file=sys.stderr)
            if enrich_url:
                print(f"Reference URL: {enrich_url}", file=sys.stderr)
    print("", file=sys.stderr)

    # Handle enhancement mode setup
    if enhancement_mode:
        source_design = Path(design_file).resolve()
        if not source_design.exists():
            print(f"ERROR: Design file not found: {source_design}", file=sys.stderr)
            return None

        # Copy existing design to project directory
        target_design = project_path / "DESIGN.md"
        shutil.copy(source_design, target_design)
        print(f"Copied design to: {target_design}", file=sys.stderr)

        # Infer stack from existing design
        design_content = target_design.read_text()
        if "prisma" in design_content.lower() or "Prisma" in design_content:
            inferred_stack = "nextjs-prisma"
        elif "supabase" in design_content.lower():
            inferred_stack = "nextjs-supabase"
        elif "rails" in design_content.lower() or "ruby" in design_content.lower():
            inferred_stack = "rails"
        else:
            inferred_stack = "nextjs-supabase"  # Default

        state.stack_id = force_stack or inferred_stack
        print(f"Stack: {state.stack_id}", file=sys.stderr)

        # Write STACK_DECISION.md for the builder
        stack_decision = f"""# Stack Decision

## Product Analysis
- **Type**: Enhancement of existing design
- **Complexity**: medium-high
- **Key Features**: {', '.join(enhance_features or ['enhancement'])}

## Selected Stack
- **Stack ID**: {state.stack_id}
- **Rationale**: Inferred from existing DESIGN.md

## Stack-Specific Considerations
- Preserve existing architecture
- Add new features without breaking existing functionality
"""
        (project_path / "STACK_DECISION.md").write_text(stack_decision)

    # Get agent definitions for CLI
    agents_config = _get_agents_for_cli()

    # Write MCP config if servers are available
    mcp_config_path = _write_mcp_config(project_path)

    # Select system prompt based on mode
    # Plugin/host modes take priority over generic legacy
    if enhancement_mode:
        system_prompt = ENHANCEMENT_ORCHESTRATOR_PROMPT
    elif build_mode == "plugin":
        system_prompt = PLUGIN_ORCHESTRATOR_PROMPT
    elif build_mode == "host":
        system_prompt = HOST_ORCHESTRATOR_PROMPT
    elif legacy_mode:
        system_prompt = LEGACY_ORCHESTRATOR_PROMPT
    else:
        system_prompt = ORCHESTRATOR_SYSTEM_PROMPT

    # Define allowed tools for auto-approval
    allowed_tools = [
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
        "Task", "WebSearch", "WebFetch",
        # Safe bash patterns
        "Bash(npm *)", "Bash(npx *)", "Bash(node *)",
        "Bash(git *)", "Bash(vercel *)", "Bash(pnpm *)",
        # v7.0: Swift build tools
        "Bash(swift *)", "Bash(xcodebuild *)", "Bash(xcrun *)",
    ]

    # Build the prompt
    if enhancement_mode:
        # Enhancement mode prompt
        features_list = ", ".join(enhance_features) if enhance_features else "requested features"
        limits_context = _get_phase_limits_context(state)

        prompt = f"""Enhance this product: {idea}

Project directory: {project_path}
Stack: {state.stack_id}

## Existing Design
DESIGN.md has been copied to the project directory. Read it first.

## Features to Add
{features_list}

{limits_context}

## Available Feature Enhancements

### board-views
Add multiple view types for tasks/projects:
- Timeline/Gantt view with dependencies
- Calendar view (day/week/month)
- Table view (spreadsheet-style)
- View switcher component

### dashboards
Add customizable dashboard system:
- Dashboard model with widgets
- Widget types: charts, metrics, lists
- Drag-and-drop layout

### automations
Add workflow automation system:
- Automation rules (trigger + conditions + actions)
- Triggers: status_changed, due_date_approaching, task_created
- Actions: notify, change_status, assign_to

## Process
1. Use the `enhancer` subagent to add features to DESIGN.md
2. Use the `reviewer` subagent to validate the enhanced design
3. Once APPROVED, use the `builder` subagent to implement
4. Use the `auditor` subagent to verify the build matches ORIGINAL_PROMPT.md
5. Use the `tester` subagent to generate and run tests
6. Use the `deployer` subagent to deploy
7. Use the `verifier` subagent to verify the deployment

Start now by reading DESIGN.md, then use the enhancer."""

    elif build_mode == "plugin":
        # v7.0: Plugin build mode
        limits_context = _get_phase_limits_context(state)
        state.stack_id = force_stack or "swift-swiftui"
        state.build_mode = build_mode

        prompt = f"""Build this plugin: {idea}

Project directory: {project_path}
Stack: swift-swiftui
Mode: plugin (Swift Package module)

{limits_context}

## Plugin Architecture
This plugin will be a Swift Package conforming to the NCBSPlugin protocol.
It receives shared services (compression, storage, network) via PluginContext.
Read the plugin-protocol and scaffold-plugin templates for reference.

## Process
1. Use the analyzer subagent to confirm stack and analyze requirements
2. Use the designer subagent to create DESIGN.md with plugin manifest, views, models
3. Use the reviewer subagent to validate the design
4. Use the builder subagent to implement the Swift Package
5. Use the auditor subagent to verify the build matches ORIGINAL_PROMPT.md
6. Use the tester subagent to generate and run XCTests (minimum 8 tests)
7. Verify `swift build` and `swift test` pass

Start now with the analyzer."""

    elif build_mode == "host":
        # v7.0: Host app build mode
        limits_context = _get_phase_limits_context(state)
        state.stack_id = force_stack or "swift-swiftui"
        state.build_mode = build_mode

        prompt = f"""Build this host app: {idea}

Project directory: {project_path}
Stack: swift-swiftui
Mode: host (Plugin host application)

{limits_context}

## Host App Architecture
Build the NoCloud BS host app with:
- NCBSPluginSDK local package (plugin protocol, service protocols)
- Plugin registry for managing plugin lifecycle
- Shared service implementations (CompressionService, StorageService, NetworkService)
- Core UI: DashboardView (storage stats), SettingsView
- Dynamic TabView with plugin tab registration

## Process
1. Use the analyzer subagent to confirm stack and analyze requirements
2. Use the designer subagent to create DESIGN.md with host architecture
3. Use the reviewer subagent to validate the design
4. Use the builder subagent to implement the host app and SDK
5. Use the auditor subagent to verify build completeness
6. Use the tester subagent to generate and run XCTests (minimum 15 tests)
7. Verify `swift build` and `swift test` pass

Start now with the analyzer."""

    elif legacy_mode:
        prompt = f"""Build this product: {idea}

Project directory: {project_path}

Process:
1. First, use the designer subagent to create DESIGN.md
2. Then, use the builder subagent to implement the app
3. Finally, use the deployer subagent to deploy to Vercel

Start now with the designer."""

    else:
        # Standard prompt with stack selection
        stack_info = ""
        if force_stack:
            stack_info = f"\nNote: Stack has been pre-selected as `{force_stack}`."
            state.stack_id = force_stack
        else:
            stack_info = "\n" + get_all_stacks_for_prompt()

        # Get current limits context
        limits_context = _get_phase_limits_context(state)

        # Build test generation info
        test_info = ""
        if config.ENABLE_TEST_GENERATION:
            test_info = f"""
## Test Generation: ENABLED
- Use the tester subagent after builder completes
- Tests must pass before deployment{'  (REQUIRED)' if config.REQUIRE_PASSING_TESTS else ' (recommended)'}
"""

        # v6.0: Build enrichment context
        enrich_info = ""
        enrich_start = ""
        if enrich and config.ENABLE_PROMPT_ENRICHMENT:
            url_note = f"\nReference URL: {enrich_url}" if enrich_url else ""
            enrich_info = f"""
## Prompt Enrichment: ENABLED (v6.0)
- Use the enricher subagent FIRST to research and expand the idea into PROMPT.md
- All subsequent agents should read PROMPT.md as the primary specification{url_note}
"""
            enrich_start = "0. Use the enricher subagent to research and produce PROMPT.md\n"

        prompt = f"""Build this product: {idea}

Project directory: {project_path}
{stack_info}
{limits_context}
{test_info}{enrich_info}

Process:
{enrich_start}1. First, use the analyzer subagent to select the optimal stack
2. Then, use the designer subagent to create DESIGN.md
3. Then, use the reviewer subagent to validate the design
4. If review says NEEDS_REVISION, use designer again (max {MAX_DESIGN_REVISIONS} revisions)
5. Once APPROVED, use the builder subagent to implement
6. If build fails, analyze error and use builder to fix (max {MAX_BUILD_ATTEMPTS} attempts)
7. Use the auditor subagent to verify the build matches ORIGINAL_PROMPT.md
8. If SPEC_AUDIT.md says NEEDS_FIX, use builder to fix CRITICAL discrepancies (max {config.MAX_AUDIT_FIX_ATTEMPTS} fix attempt)
9. Use the tester subagent to generate and run tests
10. If tests fail, fix them (max {config.MAX_TEST_ATTEMPTS} attempts)
11. Finally, use the deployer subagent to deploy
12. Use the verifier subagent to verify the deployment

Start now with the {"enricher" if enrich and config.ENABLE_PROMPT_ENRICHMENT else "analyzer"}."""

    # Initialize checkpoint manager
    checkpoint_mgr = CheckpointManager(str(project_path))

    print("Starting Claude Code...", file=sys.stderr)
    print("This may take several minutes. Claude is working autonomously.", file=sys.stderr)
    print("", file=sys.stderr)

    try:
        # Run Claude Code CLI
        result = run_claude(
            prompt=prompt,
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            agents_config=agents_config,
            cwd=str(project_path),
            max_turns=config.MAX_TURNS,
            timeout=7200,  # 120 minute timeout for complex apps
            mcp_config_path=mcp_config_path,
        )

        if not result.get("success"):
            error = result.get("error", "Unknown error")
            print(f"Agent failed: {error}", file=sys.stderr)
            state.mark_failed(error)
            checkpoint_mgr.save(state)
            return None

        # Extract final result
        final_result = result.get("result")

        # Check for deployment URL or Swift build success in result
        if final_result:
            if "Your app is live at" in final_result or "Your app is deployed at" in final_result:
                url_match = re.search(r'https://[^\s]+', final_result)
                if url_match:
                    state.mark_completed(url_match.group())
                else:
                    state.mark_completed()
                checkpoint_mgr.save(state)
                return final_result
            # v7.0: Swift plugin/host success
            if "Plugin package ready" in final_result or "Host app ready" in final_result:
                state.mark_completed()
                checkpoint_mgr.save(state)
                return final_result

        # If no clear result, check for common success indicators
        if final_result:
            state.mark_completed()
            checkpoint_mgr.save(state)
            return final_result

        # No result returned
        print("Agent completed but no result was returned.", file=sys.stderr)
        return None

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        state.mark_failed("Interrupted by user")
        checkpoint_mgr.save(state)
        return None
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        state.mark_failed(str(e))
        checkpoint_mgr.save(state)
        return None


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Product Agent v8.0 - Build web and native iOS apps from ideas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Build with automatic stack selection
    python -m agent.main "Build me a todo app"

    # Force a specific stack
    python -m agent.main --stack nextjs-prisma "Build a freelancer marketplace"

    # Custom project directory
    python -m agent.main --project-dir ./my-todo "Build a todo app"

    # Build a Swift plugin module (v7.0)
    python -m agent.main --stack swift-swiftui --mode plugin "Photo gallery with compressed albums"

    # Build the host app (v7.0)
    python -m agent.main --stack swift-swiftui --mode host "NoCloud BS host app"

    # Resume from last checkpoint
    python -m agent.main --resume "Build a todo app"

    # Legacy mode (v3.0 - fixed Next.js + Supabase stack)
    python -m agent.main --legacy "Build a simple todo app"

    # Enable manual checkpoints
    python -m agent.main --checkpoints "Build a blog platform"

Stacks:
    nextjs-supabase  - Default. Best for SaaS, internal tools
    nextjs-prisma    - Best for marketplaces, complex data models
    rails            - Best for rapid prototyping, admin-heavy apps
    expo-supabase    - Best for cross-platform mobile apps
    swift-swiftui    - Best for native iOS apps and plugin modules (v7.0)

Build Modes (v7.0):
    standard         - Default. Build a complete web or mobile app
    host             - Build the iOS plugin host app (use with swift-swiftui)
    plugin           - Build a Swift Package plugin module (use with swift-swiftui)

Requirements:
    - Claude Code CLI must be installed and authenticated
    - Claude Pro subscription (uses your existing subscription)
        """
    )

    parser.add_argument(
        "idea",
        help="The product idea to build"
    )

    parser.add_argument(
        "--project-dir",
        default="./projects/new-product",
        help="Directory for the project (default: ./projects/new-product)"
    )

    parser.add_argument(
        "--stack",
        choices=["nextjs-supabase", "nextjs-prisma", "rails", "expo-supabase", "swift-swiftui"],
        help="Force a specific stack instead of auto-selection"
    )

    parser.add_argument(
        "--mode",
        choices=["standard", "host", "plugin"],
        default="standard",
        help="Build mode: standard (web app), host (iOS plugin host app), or plugin (Swift Package module) (v7.0)"
    )

    parser.add_argument(
        "--checkpoints",
        action="store_true",
        help="Enable checkpoints for human approval at each phase"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the most recent checkpoint"
    )

    parser.add_argument(
        "--resume-from",
        metavar="CHECKPOINT_ID",
        help="Resume from a specific checkpoint ID"
    )

    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy v3.0 mode (fixed stack, linear flow)"
    )

    parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="List available checkpoints and exit"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed progress output"
    )

    # v12.1: Shipwright integration flags
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Output BuildResult as JSON to stdout (for programmatic use by Shipwright plugin)"
    )

    parser.add_argument(
        "--progress-mode",
        choices=["technical", "friendly"],
        default="technical",
        help="Progress output style: technical (default) or friendly (emoji, beginner-friendly)"
    )

    # Enhancement mode arguments
    parser.add_argument(
        "--design-file",
        metavar="PATH",
        help="Path to existing DESIGN.md to enhance (enables enhancement mode)"
    )

    parser.add_argument(
        "--enhance-features",
        metavar="FEATURES",
        help="Comma-separated features to add: board-views,dashboards,automations"
    )

    # v6.0: Enrichment arguments
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Enable prompt enrichment phase — research and expand the idea before building (v6.0)"
    )

    parser.add_argument(
        "--enrich-url",
        metavar="URL",
        help="Reference URL for enrichment research (implies --enrich)"
    )

    args = parser.parse_args()

    # Handle checkpoint listing
    if args.list_checkpoints:
        project_path = Path(args.project_dir).resolve()
        if not project_path.exists():
            print(f"Project directory does not exist: {project_path}")
            sys.exit(1)

        checkpoint_mgr = CheckpointManager(str(project_path))
        checkpoints = checkpoint_mgr.list_checkpoints()

        if not checkpoints:
            print("No checkpoints found.")
        else:
            print("Available checkpoints:")
            for cp in checkpoints:
                print(f"  {cp['id']} - Phase: {cp['phase']} - {cp['timestamp']}")
        sys.exit(0)

    # Check for Claude CLI
    cli_available, cli_info = check_claude_cli()
    if not cli_available:
        print(f"ERROR: {cli_info}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Make sure Claude Code is installed and you're logged in.", file=sys.stderr)
        print("Install: npm install -g @anthropic-ai/claude-code", file=sys.stderr)
        print("Login: claude login", file=sys.stderr)
        sys.exit(1)

    print(f"Using Claude Code: {cli_info}", file=sys.stderr)

    # v12.2: Auth pre-flight check — verify subscription/login before
    # starting 9 expensive phase calls that would all fail if not authenticated.
    print("Verifying authentication...", file=sys.stderr)
    auth_ok, auth_detail = check_claude_auth()
    if not auth_ok:
        print(f"ERROR: {auth_detail}", file=sys.stderr)
        if args.json_output:
            import json
            print(json.dumps({"success": False, "reason": auth_detail}))
        sys.exit(1)
    print(f"  {auth_detail}", file=sys.stderr)

    # Set checkpoint environment variable
    if args.checkpoints:
        os.environ["ENABLE_CHECKPOINTS"] = "true"

    # Run the agent
    print("=" * 60, file=sys.stderr)
    print("PRODUCT AGENT v8.0 - Autonomous Builder", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("", file=sys.stderr)

    # Parse enhance_features if provided
    enhance_features = None
    if args.enhance_features:
        enhance_features = [f.strip() for f in args.enhance_features.split(",")]

    # --enrich-url implies --enrich
    enrich = args.enrich or bool(args.enrich_url)
    if enrich:
        os.environ["ENABLE_PROMPT_ENRICHMENT"] = "true"

    # v12.1: Set progress mode for Shipwright integration
    if args.progress_mode == "friendly":
        os.environ["PROGRESS_MODE"] = "friendly"

    result = build_product(
        args.idea,
        args.project_dir,
        enable_checkpoints=args.checkpoints,
        force_stack=args.stack,
        resume=args.resume,
        resume_checkpoint=args.resume_from,
        legacy_mode=args.legacy or config.LEGACY_MODE,
        design_file=args.design_file,
        enhance_features=enhance_features,
        enrich=enrich,
        enrich_url=args.enrich_url,
        build_mode=args.mode,
        verbose=getattr(args, 'verbose', False),
        json_output=args.json_output,
    )

    # v12.1: JSON output mode — print structured result and exit
    if args.json_output:
        import json
        if isinstance(result, dict):
            print(json.dumps(result))
            sys.exit(0 if result.get("success") else 1)
        else:
            # Fallback: legacy mode returned a string, wrap it
            print(json.dumps({"success": result is not None, "output": result}))
            sys.exit(0 if result else 1)

    if result:
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("BUILD COMPLETE", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(result)  # Print to stdout for capture
        sys.exit(0)
    else:
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("BUILD FAILED", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("Check the output above for errors.", file=sys.stderr)
        print("You can resume from the last checkpoint with --resume", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
