# Product Agent v8.0

An autonomous AI agent that builds, tests, and deploys web and native iOS applications from plain English descriptions.

## What It Does

```bash
product-agent "Build me a todo app with user authentication"
```

**Output:**
```
Product Agent v8.0 — Building: "Build me a todo app with user authentication"

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

## What's New in v8.0

The core architectural change: **Python controls the pipeline, Claude does the creative work.**

- **Phase-by-Phase Orchestration** — Each of 9 phases is its own Claude SDK call. Python validates between phases, enforces ordering, and manages state. No more hoping a single 200-turn subprocess gets everything right.
- **Smart Retry with Error Injection** — When a phase fails, the error context is injected into the retry prompt. The agent learns from its mistakes instead of repeating them.
- **Parallel Audit + Test** — Spec audit and test execution run concurrently via `asyncio.gather`, saving 20-60 seconds per build.
- **Build Memory** — Every build is logged to `.agent_history/builds.jsonl`. Before starting a new build, the agent finds similar past builds and learns from their patterns and mistakes.
- **Quality Scoring** — 5-factor weighted scoring (tests, spec coverage, build efficiency, design quality, verification) produces A/B/C/F grades with detailed breakdowns.
- **Real-Time Progress** — Phase-by-phase streaming output so you always know what's happening.
- **Code-Level Validation** — Python checks that each phase produced its required artifacts before proceeding. No more "the LLM says it created the file."
- **claude-code-sdk** — Uses the Python SDK instead of subprocess calls. Async, streaming, structured errors.
- **Clean Public API** — `from agent.api import build` for programmatic use.

### Previous Versions
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

### Architecture (v8.0)

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

### Programmatic API (v8.0)

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

## Build Memory (v8.0)

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
  "quality_grade": "A"
}
```

Before starting a new build, the agent searches for similar past builds using Jaccard similarity and injects patterns from successful builds into the pipeline context.

## Quality Scoring (v8.0)

After all phases complete, a 5-factor quality score is computed:

| Factor | Weight | What It Measures |
|--------|--------|-----------------|
| Tests | 30 pts | Were tests generated and did they pass? |
| Spec Coverage | 20 pts | How many requirements were met in audit? |
| Build Efficiency | 20 pts | How many build attempts were needed? |
| Design Quality | 15 pts | How many design revisions were needed? |
| Verification | 15 pts | Was the deployment verified working? |

Grades: **A** (95+), **A-** (90+), **B+** (85+), **B** (80+), **B-** (70+), **C** (60+), **F** (<60)

## Development

### File Structure

```
agent/
├── main.py                 # CLI entry point, v8/legacy routing
├── orchestrator.py         # v8.0 — BuildConfig, BuildResult, build_product()
├── api.py                  # v8.0 — Clean public API
├── cli_runner.py           # SDK-based run_phase_call() + legacy run_claude()
├── validators.py           # v8.0 — Code-level output validation
├── progress.py             # v8.0 — Real-time progress streaming
├── history.py              # v8.0 — Build memory (JSONL log)
├── quality.py              # v8.0 — Quality scoring
├── config.py               # Environment configuration
├── state.py                # Phase and state management
├── checkpoints.py          # Checkpoint system
├── recovery.py             # Error recovery
├── test_validation.py      # Test result parsing
├── phases/                 # v8.0 — Phase modules
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
│   └── definitions.py      # 10 subagent prompt definitions
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

1,239 tests across 17 test files:

| Test File | Tests | Coverage |
|-----------|-------|---------|
| `test_orchestrator_v8.py` | 114 | Full v8 pipeline, retry, quality gate, parallel phases |
| `test_validators.py` | 93 | All 9 phase validators, extraction helpers |
| `test_swift_modes.py` | 85 | Swift state, criteria, prompts, domains |
| `test_quality.py` | 77 | Scoring factors, grade boundaries, report formatting |
| `test_phases.py` | ~70 | Phase registry, PhaseConfig, run_phase with mocked SDK |
| `test_history.py` | 64 | BuildRecord, BuildHistory, similarity search |
| `test_agent_prompts.py` | 60 | Registry, tools, all 10 agent prompts |
| `test_progress.py` | 55 | PhaseResult, ProgressReporter, formatting |
| `test_stack_selection.py` | 44 | Keyword analysis, scoring, selection |
| `test_orchestration.py` | 34 | Legacy orchestration, build modes, prompt content |
| `test_checkpoints.py` | 30 | Save/load/resume, phase-specific |
| `test_cli_runner.py` | 19 | Subprocess mocking, error handling |
| + 5 more | ~494 | Recovery, safety, validation, state v5/v6 |

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
- **Block** dangerous commands (`rm -rf /`, fork bombs, disk writes)
- **Protect** system directories and credentials
- **Auto-approve** safe operations (npm, git, file writes in project)
- **Validate** deployment compatibility (SQLite + Vercel = blocked)

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
| **v8.0** | **Phase-by-phase orchestration, build memory, quality scoring, 1239 tests, public API** |

## Requirements

- Python 3.10+
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- Claude Pro subscription
- Node.js 18+ (for generated web apps)
- Swift 5.9+ / Xcode 15+ (for Swift/SwiftUI builds)
