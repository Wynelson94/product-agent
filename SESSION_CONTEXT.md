---
project: product-agent
version: "7.0.0"
repo: https://github.com/Wynelson94/product-agent
last_updated: "2026-02-12"
last_session_focus: "Full audit + pipeline fixes + 298 new tests"
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
version: "7.0.0"
runtime_dep: claude-code-sdk >= 0.1.0
test_count: 634 (all passing)

stacks:
  - nextjs-supabase (default web)
  - nextjs-prisma (marketplaces)
  - rails (rapid prototyping)
  - expo-supabase (mobile)
  - swift-swiftui (native iOS, NoCloud plugins) # v7.0

build_modes:
  standard: Full 8-phase pipeline (analyze → design → review → build → audit → test → deploy → verify)
  plugin: Builds Swift Package modules conforming to NCBSPlugin protocol
  host: Builds iOS host app with plugin infrastructure
  enhancement: Adds features to existing designs

subagents: 10 (enricher, analyzer, designer, reviewer, builder, auditor, tester, deployer, verifier, enhancer)

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
  - Wait for Taylor's feedback on Quick Notes plugin integration
  - If it works: proceed to Terms & Conditions Reviewer plugin design

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
  - Product Agent v7.1 improvements based on plugin build experience
  - Consider adding GitHub Actions CI (.github/workflows/tests.yml)
```

---

## Key Files to Read

```yaml
# Start here for full context
session_context: SESSION_CONTEXT.md          # This file
nocloud_reference: reference/nocloud/APP_CONTEXT.md  # Full NoCloud app details

# Agent architecture
orchestrator: agent/main.py                  # 4 build modes, 8 phases
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

# Tests (634 total across 11 files)
agent_tests: tests/                          # 634 tests (11 files)
test_orchestration: tests/test_orchestration.py    # Phase limits, build modes, prompt content
test_stack_selection: tests/test_stack_selection.py  # Keyword analysis, scoring, selection
test_checkpoints: tests/test_checkpoints.py        # Save/load/resume, phase-specific
test_swift_modes: tests/test_swift_modes.py        # Swift state, criteria, prompts, domains
test_agent_prompts: tests/test_agent_prompts.py    # Registry, tools, all 10 agent prompts
test_cli_runner: tests/test_cli_runner.py          # Subprocess mocking, error handling
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
