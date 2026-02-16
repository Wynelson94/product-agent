# Product Agent v10.0

An autonomous AI agent that builds, tests, and deploys web and native iOS applications from plain English descriptions.

## What It Does

```bash
product-agent "Build me a todo app with user authentication"
```

**Output:**
```
Product Agent v10.0 — Building: "Build me a todo app with user authentication"

[1/9] Enriching prompt...                    done   12s
[2/9] Analyzing stack... → nextjs-supabase   done    8s
[3/9] Designing architecture...              done   45s
[4/9] Reviewing design... APPROVED           done   15s
[5/9] Building application...                done 3m22s
[6/9] Auditing spec... 12/12 met             done   20s  (parallel)
[7/9] Running tests... 14/14 passed          done   35s  (parallel)
[8/9] Deploying to Vercel...                 done   45s
[9/9] Verifying deployment...                done   10s

BUILD COMPLETE  5m 42s
  URL: https://todo-app-abc123.vercel.app
  Tests: 14/14 passed
  Spec: 12/12 requirements met
  Quality: A (95%)
```

One prompt in, production app out. No human intervention required.

## What's New in v10.0

v10.0 is a post-mortem driven release. After the ClientPulse stress test (12-table multi-tenant SaaS) scored B- instead of A, we traced every preventable failure back to a gap in the agent's prompts, validators, or patterns — and fixed all 4.

### Post-Mortem Fixes (v10.0)
- **Dependency Audit** — Builder and auditor now cross-check DESIGN.md against package.json. Missing libraries (e.g., `@react-pdf/renderer`) are flagged as CRITICAL discrepancies instead of silently crashing at runtime.
- **Data Wiring Verification** — Auditor greps for `data={[]}` and mock data props. Builder prompt requires components to fetch real data from Supabase/API, not pass empty arrays.
- **RLS Circular Dependency Prevention** — Designer prompt warns against self-referencing RLS policies. Reviewer checklist includes circular dep checks. Stack patterns include BAD/GOOD examples with SECURITY DEFINER fix. Recovery system detects the pattern and suggests the fix.
- **Root Page Routing** — Scaffold template clarifies that route groups don't replace the root `page.tsx`. Verifier checks the homepage isn't the default Next.js template.
- **CRITICAL Override** — When the auditor finds CRITICAL discrepancies but reports `status: PASS`, the validator now overrides to FAIL. Quality scoring penalizes 5 pts per CRITICAL finding and caps at grade B (84).

### Crash Recovery (v9.1)
- **`--resume` now works in v8+ mode** — Loads the latest checkpoint, verifies artifacts on disk, and skips completed phases. A crash at phase 7 no longer requires re-running phases 1-6.
- **Atomic Checkpoint Writes** — Checkpoints use `tempfile` + `os.replace()` to prevent half-written state on crash.
- **Artifact Verification** — On resume, stored SHA-256 hashes are compared against files on disk. Mismatched artifacts trigger a re-run of that phase.

### Previous Versions
- **v9.0** — Reliability overhaul: honest quality scoring, YAML contracts, SDK logging, timeouts, input sanitization, per-stack templates, failure learning
- **v8.0** — Phase-by-phase orchestration, build memory, quality scoring, parallel audit+test, public API
- **v7.0** — Swift/SwiftUI stack, plugin build mode, NCBSPlugin protocol, XCTest integration
- **v6.0** — Spec audit, prompt enrichment, original prompt passthrough, content site domain
- **v5.0** — Deployment validation, verification, checkpoints, automated testing

## Quick Start

### 1. Install

```bash
cd product-agent
pip install -e .
```

### 2. Set Environment Variables

```bash
export ANTHROPIC_API_KEY=sk-ant-...  # Required
export GITHUB_TOKEN=ghp_...          # Optional - GitHub MCP
export SUPABASE_ACCESS_TOKEN=...     # Optional - Supabase MCP
export VERCEL_TOKEN=...              # Optional - Vercel MCP
```

### 3. Run

```bash
product-agent "Build me a simple blog"
```

## Available Stacks

The agent automatically selects the best stack for your product:

| Stack | Best For | Database | Deploys To |
|-------|----------|----------|------------|
| **nextjs-supabase** (default) | SaaS, internal tools, dashboards, content sites | PostgreSQL (Supabase) | Vercel |
| **nextjs-prisma** | Marketplaces, multi-tenant, complex data | PostgreSQL | Vercel |
| **rails** | Rapid prototyping, admin-heavy apps | PostgreSQL | Railway |
| **expo-supabase** | Mobile apps, consumer apps | PostgreSQL (Supabase) | App Stores |
| **swift-swiftui** | Native iOS apps, plugin modules | Local storage | TestFlight / SPM |

Force a specific stack:
```bash
product-agent --stack nextjs-prisma "Build a freelancer marketplace"
```

## How It Works

### Architecture

```
User → build_product() →
  ┌─────────────────────────────────────────────────────────────┐
  │                   PYTHON ORCHESTRATOR                        │
  │                  (agent/orchestrator.py)                     │
  │                                                             │
  │  run_phase(ENRICH)   → validate → checkpoint → progress     │
  │  run_phase(ANALYZE)  → validate → checkpoint → progress     │
  │  run_phase(DESIGN)  ←→ run_phase(REVIEW) loop              │
  │  run_phase(BUILD)    → validate → retry with error context  │
  │  run_phase(AUDIT)  ┐                                        │
  │  run_phase(TEST)   ┘→ parallel → validate → progress       │
  │  run_phase(DEPLOY)   → validate → checkpoint → progress     │
  │  run_phase(VERIFY)   → validate → checkpoint → progress     │
  └─────────────────────────────────────────────────────────────┘
→ BuildResult with URL, quality score, metrics
```

Each `run_phase()` is its own Claude SDK call with:
- Phase-specific prompt, tools, and turn limits
- Code-level output validation (file existence, content checks)
- Smart retry with error injection on failure
- Real-time progress streaming

### Pipeline Phases

| # | Phase | What It Does | Validates |
|---|-------|-------------|-----------|
| 1 | **Enrich** (optional) | Researches domain, expands idea into detailed spec | PROMPT.md exists, 100+ chars |
| 2 | **Analyze** | Selects optimal tech stack | STACK_DECISION.md with valid stack ID |
| 3 | **Design** | Creates data model, pages, components | DESIGN.md with required sections |
| 4 | **Review** | Validates design (loop, max 3 revisions) | REVIEW.md with APPROVED/NEEDS_REVISION |
| 5 | **Build** | Implements full application (max 5 attempts) | Source files exist, entry point present |
| 6 | **Audit** | Verifies build matches requirements | SPEC_AUDIT.md with pass/fail counts |
| 7 | **Test** | Generates and runs tests | TEST_RESULTS.md with pass/fail counts |
| 8 | **Deploy** | Deploys to production | Deployment URL extracted |
| 9 | **Verify** | Tests deployed app | VERIFICATION.md with status |

Audit and Test run in parallel. Design loops with Review until approved.

### Subagents

| Agent | Purpose | Max Turns |
|-------|---------|-----------|
| **enricher** | Researches domain, expands ideas into specs | 20 |
| **analyzer** | Selects stack, validates compatibility | 15 |
| **designer** | Creates DESIGN.md with architecture | 25 |
| **reviewer** | Validates design completeness | 15 |
| **builder** | Implements app with cross-referencing | 80 |
| **auditor** | Audits build against original requirements | 20 |
| **tester** | Generates and runs tests | 30 |
| **deployer** | Deploys with pre-validation | 25 |
| **verifier** | Tests deployed app | 15 |
| **enhancer** | Adds features to existing designs | 40 |

## Usage Examples

### Basic (Fully Autonomous)

```bash
product-agent "Build a task management app"
```

### With Prompt Enrichment

```bash
product-agent --enrich "Build a dental charity nonprofit website"
```

Research a reference site:
```bash
product-agent --enrich-url "https://example-nonprofit.org" \
  "Rebuild this nonprofit website"
```

### Programmatic API

```python
from agent.api import build, BuildConfig

result = await build(
    idea="Create a marketplace for vintage guitars",
    config=BuildConfig(
        stack="nextjs-prisma",
        enrich=True,
        require_passing_tests=True,
    ),
)

print(result.url)          # https://vintage-guitars.vercel.app
print(result.quality)      # A- (92%)
print(result.test_count)   # 14/14
print(result.duration_s)   # 342.5
```

### Build Modes

```bash
# Standard web app
product-agent "Build a project management tool"

# Swift plugin module
product-agent --stack swift-swiftui --mode plugin \
  "Photo gallery plugin with compressed local albums"

# iOS host app
product-agent --stack swift-swiftui --mode host \
  "NoCloud BS host app with plugin system"

# Enhancement mode (add features to existing design)
product-agent --design-file ./project/DESIGN.md \
  --enhance-features "board-views,dashboards" \
  "Enhance project management app"
```

### Other Options

```bash
# Custom project directory
product-agent --project-dir ./my-app "Build a todo app"

# Force a specific stack
product-agent --stack rails "Build an admin dashboard"

# With checkpoints (human approval between phases)
product-agent --checkpoints "Build an e-commerce store"

# Resume from checkpoint
product-agent --resume "Build an e-commerce store"

# Legacy mode (v7.0 single-subprocess architecture)
product-agent --legacy "Build a simple todo app"

# Verbose output
product-agent --verbose "Build a blog"
```

## Build Memory

Every build is logged to `.agent_history/builds.jsonl`:

```json
{
  "id": "20260212_143022",
  "idea": "Team todo app with real-time sync",
  "stack": "nextjs-supabase",
  "outcome": "success",
  "total_duration_s": 342,
  "test_count": 14,
  "tests_passed": 14,
  "quality_grade": "B+",
  "failure_reasons": [],
  "lessons": ["Always verify Supabase RLS policies with auth.uid()"]
}
```

Before starting a new build, the agent searches for similar past builds using Jaccard similarity and injects patterns from successful builds into the pipeline context. In v9.0, `failure_reasons` and `lessons` are recorded per build, and `get_relevant_lessons()` finds relevant past failures (boosted by stack match) to inject into builder prompts — preventing the same mistakes from repeating.

## Quality Scoring

After all phases complete, a 5-factor quality score is computed. v9.0 rebalanced weights to prioritize **product outcomes** over process metrics:

| Factor | Weight | What It Measures |
|--------|--------|-----------------|
| Functional Verification | 35 pts | Did deployed endpoints return expected results? |
| Test Pass Rate | 25 pts | Were tests generated and did they pass? |
| Spec Coverage | 20 pts | How many requirements were met in audit? |
| Build Efficiency | 10 pts | How many build attempts were needed? |
| Design Quality | 10 pts | How many design revisions were needed? |

**Hard caps**: `deployment_verified=False` caps grade at C. `tests_generated=False` caps grade at B-. `spec_audit_critical_count > 0` caps grade at B (v10.0).

Grades: **A** (95+), **A-** (90+), **B+** (85+), **B** (80+), **B-** (70+), **C** (60+), **F** (<60)

## Development

### File Structure

```
agent/
├── main.py                 # CLI entry point, v8/legacy routing
├── orchestrator.py         # BuildConfig, BuildResult, build_product()
├── api.py                  # Clean public API
├── cli_runner.py           # SDK-based run_phase_call() with timeouts
├── validators.py           # Code-level output validation + YAML front-matter
├── progress.py             # Real-time progress streaming
├── history.py              # Build memory with failure learning
├── quality.py              # Outcome-based quality scoring
├── sanitize.py             # v9.0 — Input sanitization
├── config.py               # Environment configuration
├── state.py                # Phase and state management
├── checkpoints.py          # Checkpoint system with cleanup/archive
├── recovery.py             # Error recovery
├── test_validation.py      # Test result parsing
├── phases/                 # Phase modules with SDK logging
│   ├── __init__.py         # Phase registry, run_phase() dispatcher
│   ├── enrich.py           # Enricher phase
│   ├── analyze.py          # Stack analysis phase
│   ├── design.py           # Design phase
│   ├── review.py           # Design review phase
│   ├── build.py            # Build phase
│   ├── audit.py            # Spec audit phase
│   ├── test.py             # Test phase
│   ├── deploy.py           # Deploy phase
│   └── verify.py           # Verify phase
├── agents/
│   └── definitions.py      # 10 subagent prompts + per-stack template injection
├── stacks/
│   ├── criteria.py         # Stack definitions and scoring
│   ├── selector.py         # Stack selection logic
│   └── templates/          # Stack-specific templates
│       ├── nextjs-supabase/
│       ├── nextjs-prisma/
│       ├── rails/
│       ├── expo-supabase/
│       └── swift-swiftui/
├── domains/
│   ├── __init__.py         # Domain registry
│   ├── marketplace/
│   ├── saas/
│   ├── internal_tool/
│   ├── content_site/
│   ├── plugin_host/
│   └── plugin_module/
├── hooks/
│   ├── safety.py           # Safety hooks
│   └── progress.py         # Progress reporting
└── mcp/
    └── servers.py          # MCP configurations
```

### Running Tests

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v
```

1,439 tests across 18 test files:

| Test File | Tests | Coverage |
|-----------|-------|---------|
| `test_orchestrator_v8.py` | 114 | Full v8 pipeline, retry, quality gate, parallel phases |
| `test_validators.py` | 93+ | All 9 phase validators, YAML front-matter, extraction |
| `test_swift_modes.py` | 100 | Swift state, criteria, prompts, domains |
| `test_quality.py` | 77+ | Outcome-based scoring, grade caps, report formatting |
| `test_safety.py` | 183 | Blocked commands, shell-aware splitting, path protection |
| `test_phases.py` | 142 | Phase registry, PhaseConfig, run_phase, SDK logging |
| `test_history.py` | 78 | BuildRecord, failure learning, similarity search |
| `test_agent_prompts.py` | 74 | Registry, tools, all 10 agents, template injection |
| `test_progress.py` | 55 | PhaseResult, ProgressReporter, formatting |
| `test_checkpoints.py` | 44 | Save/load/resume, cleanup, archive, phase cap |
| `test_stack_selection.py` | 44 | Keyword analysis, scoring, selection |
| `test_orchestration.py` | 34 | Legacy orchestration, build modes, prompt content |
| `test_sanitize.py` | 25 | Input sanitization, injection markers, edge cases |
| + 5 more | ~200+ | Recovery, validation, state v5/v6, CLI runner |

### Domain Patterns

| Domain | Product Types | Key Patterns |
|--------|--------------|--------------|
| **marketplace** | Marketplaces, two-sided platforms | Buyer/seller flows, listings, transactions |
| **saas** | SaaS, multi-tenant apps | Organizations, subscriptions, billing |
| **internal_tool** | Admin panels, dashboards | Data tables, CRUD, reporting |
| **content_site** | Nonprofits, portfolios, blogs | Static-first data, hero sections, FAQ accordion |
| **plugin_host** | iOS plugin host apps | Plugin registry, shared services, dynamic TabView |
| **plugin_module** | Swift Package plugins | NCBSPlugin protocol, MVVM, compressed storage |

## CLI Arguments

```
product-agent [OPTIONS] IDEA

Arguments:
  IDEA                      The product idea to build

Options:
  --project-dir DIR         Project directory (default: ./projects/new-product)
  --stack STACK             Force stack: nextjs-supabase, nextjs-prisma, rails, expo-supabase, swift-swiftui
  --mode MODE               Build mode: standard, host, plugin
  --checkpoints             Enable checkpoints for human approval
  --resume                  Resume from most recent checkpoint
  --resume-from ID          Resume from specific checkpoint ID
  --list-checkpoints        List available checkpoints and exit
  --legacy                  Use legacy v7.0 mode (single subprocess)
  --design-file PATH        Existing DESIGN.md for enhancement mode
  --enhance-features LIST   Comma-separated: board-views,dashboards,automations
  --enrich                  Enable prompt enrichment phase
  --enrich-url URL          Reference URL for enrichment research (implies --enrich)
  --verbose                 Show detailed progress
```

## Safety Features

The agent includes safety hooks that:
- **Block** dangerous commands (`rm -rf /`, fork bombs, disk writes) with shell-aware splitting that respects quoted strings
- **Protect** system directories and credentials
- **Auto-approve** safe operations (npm, git, file writes in project)
- **Validate** deployment compatibility (SQLite + Vercel = blocked)
- **Sanitize** user input before prompt injection (strips injection markers, caps length, removes control chars)
- **Limit** total tool turns per build (300) and per phase to prevent infinite loops

## Version History

| Version | Description |
|---------|-------------|
| v1.0 | 12,000+ lines of markdown instructions, 26 templates |
| v2.0 | Simplified to 770 lines, 4 templates, 3 checkpoints |
| v3.0 | Autonomous agent using Claude Code SDK |
| v4.0 | Stack selection, design review, iteration limits |
| v5.0 | Deployment validation, verification, checkpoints |
| v5.1 | Automated testing, tester agent, test templates |
| v6.0 | Spec audit, prompt passthrough, enricher agent, content site domain |
| v7.0 | Swift/SwiftUI stack, plugin build mode, NCBSPlugin protocol, XCTest |
| **v10.0** | **Post-mortem fixes: dependency audit, data wiring verification, RLS circular dep prevention, CRITICAL override, quality scoring penalty, 1439 tests** |
| v9.1 | Crash recovery: `--resume` in v8+ mode, atomic checkpoints, artifact verification |
| v9.0 | Reliability overhaul: honest quality scoring, YAML contracts, SDK logging, timeouts, input sanitization, per-stack templates, failure learning |
| v8.0 | Phase-by-phase orchestration, build memory, quality scoring, public API |

## Requirements

- Python 3.10+
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- Claude Pro subscription
- Node.js 18+ (for generated web apps)
- Swift 5.9+ / Xcode 15+ (for Swift/SwiftUI builds)
