---
project: product-agent
version: "8.0.0"
repo: https://github.com/Wynelson94/product-agent
last_updated: "2026-02-12"
last_session_focus: "v8.0 rewrite — phase-by-phase orchestration, build memory, quality scoring, 1239 tests"
---

# Product Agent — Session Context

Read this file first when resuming work. It contains everything needed to
understand the project state, goals, and what's been accomplished.

---

## Team

```yaml
nate:
  role: Project owner, product vision, non-developer building with Claude
  github: Wynelson94
  notes: Self-taught, uses Claude as technical co-founder

taylor:
  role: Business partner, builds the real NoCloud BS app
  app: NoCloud BS (macOS + iOS dual-platform)
  notes: Has a 29-agent build system for the real app. Nate builds plugins for it.
```

---

## What Is NoCloud BS

```yaml
identity: Dual-platform Apple app (macOS + iOS) with patented lossless compression
core_mission: Replace cloud storage with on-device compressed storage
key_fact: The compression engine is the HEART — everything else serves it

capabilities:
  - Reads entire environment, compresses everything losslessly
  - Data stays fully usable while compressed (invisible to user)
  - Files stay compressed AND usable after transfer (iMessage/AirDrop/email)
  - Comprehensive file viewer for ALL types (images, PDFs, video, audio, docs, code, 3D)

compression_algorithms:
  LZ4: ultra-fast decompress, for hot files
  LZFSE: hardware-accelerated on Apple Silicon
  zstd: balanced speed/ratio
  LZMA: best ratio, for cold storage

color_system:
  black: "#000000"      # Primary background (OLED true black)
  blackGold: "#1A1400"  # Cards, modals, nav bars
  gold: "#CFB53B"       # Primary accent
  goldLight: "#E8D48B"  # Gold text on dark
  goldDark: "#8B7A2B"   # Pressed states
  teal: "#008080"       # Secondary accent
  tealLight: "#40E0D0"  # Teal text on dark
  error: "#FF453A"
  success: "#30D158"
  warning: "#FFD60A"

golden_rules:
  - READ existing code FIRST before any changes
  - NEVER rename existing variables, functions, classes, modules, or files
  - NEVER delete working code — enhance, optimize, extend only
  - Follow existing code style
  - All changes must be additive and backwards-compatible
  - The compression engine is the core — never break it

quality_targets:
  crash_free: ">= 99.95%"
  cold_launch: "< 400ms"
  scroll: "120fps"
  compression_overhead: "< 16ms per frame"
  accessibility: "WCAG AAA (7:1)"
  force_unwraps: zero
  swiftlint_warnings: zero
  test_coverage: "90%+"

hard_requirements:
  - 100% offline-first (cloud sync additive only)
  - Dual-platform (macOS NavigationSplitView, iOS NavigationStack+TabBar)
  - @Observable only (NEVER ObservableObject/@Published)
  - All models Codable + Identifiable + Hashable
```

Full reference: `reference/nocloud/APP_CONTEXT.md`

---

## What Is Product Agent

```yaml
description: Autonomous AI agent that builds, tests, and deploys apps from plain English
version: "8.0.0"
runtime_dep: claude-code-sdk >= 0.1.0
test_count: 1239 (all passing)

architecture: |
  v8.0 — Phase-by-phase orchestration. Python controls the pipeline,
  Claude does the creative work. Each phase is its own SDK call with
  code-level validation between phases. Smart retry with error injection,
  parallel audit+test, build memory, quality scoring.

  v7.0 legacy mode still available via legacy_mode=True parameter.

stacks:
  - nextjs-supabase (default web)
  - nextjs-prisma (marketplaces)
  - rails (rapid prototyping)
  - expo-supabase (mobile)
  - swift-swiftui (native iOS, NoCloud plugins)

build_modes:
  standard: Full 9-phase pipeline (enrich → analyze → design → review → build → audit+test → deploy → verify)
  plugin: Builds Swift Package modules conforming to NCBSPlugin protocol
  host: Builds iOS host app with plugin infrastructure
  enhancement: Adds features to existing designs

subagents: 10 (enricher, analyzer, designer, reviewer, builder, auditor, tester, deployer, verifier, enhancer)

v8_modules:
  orchestrator: agent/orchestrator.py — BuildConfig, BuildResult, build_product() async pipeline
  phases: agent/phases/ — 9 phase modules (enrich, analyze, design, review, build, audit, test, deploy, verify)
  validators: agent/validators.py — Code-level output validation between phases
  progress: agent/progress.py — Real-time progress streaming (phase-by-phase)
  history: agent/history.py — Build memory (append-only JSONL, Jaccard similarity search)
  quality: agent/quality.py — 5-factor quality scoring (A/B/C/F grades)
  api: agent/api.py — Clean public API (build() async function)
  cli_runner: agent/cli_runner.py — SDK-based run_phase_call() + legacy run_claude()

plugin_architecture:
  protocol: NCBSPlugin
  context: PluginContext (compression, storage, network, userDefaults, permissions)
  manifest: PluginManifest.swift (exports pluginType for host discovery)
  distribution: Swift Package Manager (git tagged releases)
  min_tests_plugin: 8
  min_tests_host: 15
```

---

## What Was Done This Session (2026-02-11)

### 1. Saved NoCloud BS App Reference

```yaml
status: COMPLETE
commit: 8c3d0c7
files_changed: 6
tests_added: 32 (336 total, all passing)

what_was_created:
  - reference/nocloud/APP_CONTEXT.md — Full app context from Taylor's 29-agent prompt
  - Enriched agent/domains/plugin_host/patterns.md — Compression algorithms, file viewer, golden rules, security
  - Enriched agent/domains/plugin_module/patterns.md — Real app context, quality bar, offline enforcement
  - Updated agent/domains/__init__.py — NoCloud domain mappings (nocloud, compression_app, etc.)
  - Updated agent/stacks/criteria.py — NoCloud product types → swift-swiftui
  - Created tests/test_nocloud_domains.py — 32 tests for new mappings
```

### 2. Built & Shipped Quick Notes Test Plugin

```yaml
status: COMPLETE
repo: https://github.com/Wynelson94/NCBSQuickNotes (private)
tag: 1.0.0
location: projects/quick-notes/
zip: ~/Desktop/NCBSQuickNotes.zip (sent to Taylor)
build: zero errors, zero warnings
tests: 10/10 passing

plugin_id: com.nocloudbs.quick-notes
purpose: Validate NCBSPlugin architecture end-to-end before building complex plugins

services_exercised:
  storageService: Notes CRUD (save/load/delete)
  compressionService: compressedBodySize() method
  userDefaults: Sort order preference
  lifecycle: onActivate loads, onDeactivate saves
  mainView: NoteListView
  settingsView: QuickNotesSettingsView
  color_system: All views use ncbs* colors
  dual_platform: "#if os() for NavigationSplitView vs NavigationStack"
  offline_first: Zero network calls

awaiting: Taylor's feedback on integration with real host app
```

### 3. Fixed Xcode Toolchain

```yaml
issue: xcode-select was pointing to CommandLineTools instead of Xcode.app
fix: "sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
result: swift test now finds XCTest framework
```

## What Was Done This Session (2026-02-12)

### Product Agent v8.0 Rewrite

```yaml
status: COMPLETE
grade_before: B+ (634 tests, monolithic single-subprocess architecture)
grade_after: A (1239 tests, phase-by-phase orchestration, build memory, quality scoring)
tests_before: 634
tests_after: 1239 (605 new tests added)

core_change: |
  Replaced monolithic single-subprocess architecture with phase-by-phase
  orchestration using claude-code-sdk. Python now controls the pipeline,
  validates between phases, retries with error injection, and streams
  real-time progress. Each of the 9 phases is its own Claude SDK call.

new_files_created:
  agent/orchestrator.py: BuildConfig, BuildResult, build_product() async pipeline
  agent/phases/__init__.py: Phase registry, PhaseConfig, run_phase() dispatcher
  agent/phases/enrich.py: Enricher phase (prompt enhancement)
  agent/phases/analyze.py: Stack analysis phase
  agent/phases/design.py: Architecture design phase
  agent/phases/review.py: Design review phase (approve/revise loop)
  agent/phases/build.py: Build phase (most complex, smart retry)
  agent/phases/audit.py: Spec audit phase
  agent/phases/test.py: Test generation + execution phase
  agent/phases/deploy.py: Deployment phase
  agent/phases/verify.py: Post-deploy verification phase
  agent/validators.py: Code-level output validation between phases
  agent/progress.py: Real-time progress streaming (ProgressReporter)
  agent/history.py: Build memory (JSONL log, Jaccard similarity search)
  agent/quality.py: 5-factor quality scoring (tests, spec, efficiency, design, verification)
  agent/api.py: Clean public API — build() async function

files_modified:
  agent/cli_runner.py: Added SDK-based run_phase_call() alongside legacy run_claude()
  agent/main.py: v8.0 routing (legacy_mode=True → old path), reordered elif chain for plugin/host
  pyproject.toml: Version bumped 7.0.0 → 8.0.0

new_test_files:
  tests/test_validators.py: 93 tests (all 9 phase validators, dispatcher, extraction)
  tests/test_progress.py: 55 tests (PhaseResult, ProgressReporter, formatting)
  tests/test_history.py: 64 tests (BuildRecord, BuildHistory, similarity search)
  tests/test_quality.py: 77 tests (scoring factors, grade boundaries, report formatting)
  tests/test_phases.py: ~70 tests (phase registry, PhaseConfig, run_phase with mocked SDK)
  tests/test_orchestrator_v8.py: 114 tests (full pipeline, retry, quality gate, parallel phases)

key_features:
  - Phase-by-phase orchestration (9 phases, each its own SDK call)
  - Code-level validation between phases (file existence, content checks)
  - Smart retry with error injection (failed phase gets error context prepended)
  - Parallel audit + test execution (asyncio.gather)
  - Design → Review loop (max 3 revisions before proceeding)
  - Build memory (append-only JSONL, find similar past builds)
  - Quality scoring (A/B/C/F grades, 5 weighted factors)
  - Real-time progress streaming to stderr
  - Clean public API (agent.api.build())
  - Full backward compatibility (legacy_mode=True → v7.0 single-call path)
```

### Full Audit of Product Agent v7.0

```yaml
status: COMPLETE
grade_before: B (336 tests, critical gaps in orchestration)
grade_after: B+ (634 tests, pipeline hardened, all gaps addressed)
tests_before: 336
tests_after: 634 (298 new tests added)
files_modified: 4 (main.py, definitions.py, criteria.py, selector.py)
files_created: 6 (new test files)

audit_findings_fixed:
  critical:
    - Phase output validation added to orchestrator prompt (STACK_DECISION.md, DESIGN.md, source code checks)
    - Test blocking strengthened with BLOCKING/MUST NOT language in deployer pre-check
    - AUDIT phase added to enhancement mode (was skipping spec audit on enhanced builds)
    - ENRICHER output (PROMPT.md) wired to ANALYZER and DESIGNER prompts
    - Plugin DEPLOYER verified complete (SPM instructions already existed at lines 771-793)
    - Domain patterns injected into builder/designer via get_agent_prompt() product_type parameter
    - swift-swiftui stack strengthened (6 product types, 6 features, PRODUCT_TYPE_STACKS updated)

  escape_fixes:
    - Fixed Python 3.14 SyntaxWarnings in definitions.py (\\(id) and import\\.meta)

new_test_files:
  tests/test_orchestration.py: 34 tests (phase limits, agents for CLI, stack decision parsing, MCP config, prompt content, build modes)
  tests/test_stack_selection.py: 44 tests (keyword analysis, scoring, selection, criteria helpers, completeness)
  tests/test_checkpoints.py: 30 tests (save/load/resume, phase-specific, convenience functions)
  tests/test_swift_modes.py: 85 tests (state fields, config, criteria, selection, orchestrator prompts, agent prompts, domain patterns)
  tests/test_agent_prompts.py: 60 tests (registry, tools, all 10 agent prompts, template injection)
  tests/test_cli_runner.py: 19 tests (subprocess mocking, error handling, agents config, CLI check)
```

---

## Next Steps

```yaml
immediate:
  - End-to-end test: run `product-agent "Build a todo app"` to verify full v8.0 pipeline
  - Wait for Taylor's feedback on Quick Notes plugin integration
  - If it works: proceed to Terms & Conditions Reviewer plugin design

v8_follow_up:
  - Add GitHub Actions CI (.github/workflows/tests.yml) for 1239 tests
  - Wrap as Claude Code skill (.claude/skills/build/SKILL.md) or MCP server
  - LLM-powered stack pre-classification (replace keyword heuristic)
  - Run parallel builds to stress-test the phase orchestration

planned_plugin:
  name: Terms & Conditions Reviewer
  description: >
    In-app upgrade plugin that reviews Terms of Service popups using
    AI (Claude or ChatGPT — TBD). When a user downloads any app and
    the T&C pops up, this plugin generates a report showing risks,
    benefits, and key clauses. Does NOT tell user to accept or decline —
    just provides transparency.
  complexity: HIGH (needs AI integration, screen/text detection, report generation)
  approach: Design first, then build with Product Agent or directly with Claude Code
  ai_provider: TBD (Claude vs ChatGPT)

ongoing:
  - Keep reference/nocloud/APP_CONTEXT.md updated as Taylor shares more details
  - Update domain patterns as we learn from plugin integration testing
```

---

## Key Files to Read

```yaml
# Start here for full context
session_context: SESSION_CONTEXT.md          # This file
nocloud_reference: reference/nocloud/APP_CONTEXT.md  # Full NoCloud app details

# v8.0 architecture (NEW)
orchestrator_v8: agent/orchestrator.py       # BuildConfig, BuildResult, build_product() pipeline
phases: agent/phases/                        # 9 phase modules + registry (__init__.py)
validators: agent/validators.py              # Code-level output validation between phases
progress: agent/progress.py                  # Real-time progress streaming
history: agent/history.py                    # Build memory (JSONL log, similarity search)
quality: agent/quality.py                    # 5-factor quality scoring
api: agent/api.py                            # Clean public API — build() function
cli_runner: agent/cli_runner.py              # SDK-based run_phase_call() + legacy run_claude()

# Legacy architecture (still works via legacy_mode=True)
main: agent/main.py                          # CLI entry, v8/legacy routing, 4 build modes
subagents: agent/agents/definitions.py       # 10 subagent prompts (1873 lines)
stack_selector: agent/stacks/selector.py     # How stacks are chosen

# Swift/NoCloud specific
plugin_protocol: agent/stacks/templates/swift-swiftui/plugin-protocol.md
plugin_scaffold: agent/stacks/templates/swift-swiftui/scaffold-plugin.md
swift_patterns: agent/stacks/templates/swift-swiftui/patterns.md
host_domain: agent/domains/plugin_host/patterns.md
module_domain: agent/domains/plugin_module/patterns.md
domain_registry: agent/domains/__init__.py

# Quick Notes plugin (test artifact)
quick_notes: projects/quick-notes/           # Complete built plugin
quick_notes_repo: https://github.com/Wynelson94/NCBSQuickNotes

# Tests (1239 total across 17 files)
agent_tests: tests/                                # 1239 tests (17 files)
test_orchestrator_v8: tests/test_orchestrator_v8.py  # Full v8 pipeline (114 tests)
test_phases: tests/test_phases.py                    # Phase registry, run_phase (~70 tests)
test_validators: tests/test_validators.py            # Phase validators (93 tests)
test_progress: tests/test_progress.py                # Progress streaming (55 tests)
test_history: tests/test_history.py                  # Build memory (64 tests)
test_quality: tests/test_quality.py                  # Quality scoring (77 tests)
test_orchestration: tests/test_orchestration.py      # Legacy orchestration (34 tests)
test_stack_selection: tests/test_stack_selection.py   # Stack selection (44 tests)
test_checkpoints: tests/test_checkpoints.py          # Checkpoints (30 tests)
test_swift_modes: tests/test_swift_modes.py          # Swift modes (85 tests)
test_agent_prompts: tests/test_agent_prompts.py      # Agent prompts (60 tests)
test_cli_runner: tests/test_cli_runner.py            # CLI runner (19 tests)
```

---

## Environment Notes

```yaml
platform: macOS (Darwin 25.2.0, Apple Silicon)
swift: "6.2.3 (Apple)"
xcode: /Applications/Xcode.app (must be active via xcode-select)
python: "3.14.2"
git_remote: https://github.com/Wynelson94/product-agent.git
branch: main
projects_dir_gitignored: true  # projects/ is in .gitignore (generated output)
```
