# Product Agent v11.1

An autonomous AI agent that builds, tests, and deploys web and native iOS applications from plain English descriptions.

## What It Does

```bash
product-agent "Build me a todo app with user authentication"
```

**Output:**
```
Product Agent v11.1 — Building: "Build me a todo app with user authentication"

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

## What's New in v11.0

### New Tech Stacks (v11.0)
Three new stacks, expanding from 5 to 8 options:
- **Django + HTMX** — Python web framework with server-rendered interactivity. Best for admin panels, data apps, and Python-native teams. Deploys to Railway.
- **SvelteKit** — Lightweight modern JS framework with Svelte 5 runes. Best for fast SaaS, dashboards, and rapid prototypes. Deploys to Vercel.
- **Astro** — Content-first framework with islands architecture. Best for blogs, docs, landing pages, and marketing sites. Deploys to Vercel.

### Pipeline Features (v11.1)
- **AI App Domain** — New domain pattern for AI-powered apps with AI SDK v6 patterns (streamText, useChat, structured output, chat history schema). The agent now knows how to build chatbots, AI assistants, and AI tools.
- **CI/CD Generation** — Deploy templates now include GitHub Actions workflows for automated testing on PRs. Generated apps ship with CI out of the box.
- **Observability** — Next.js deploy templates now include Vercel Analytics and Speed Insights setup. Built apps get production monitoring from day one.

### Enhancement Mode (v10.2)
The enhancer agent (previously defined but never connected) is now fully wired into the pipeline. Enhancement mode runs: setup → ENHANCE → Build → Audit → Test → Deploy → Verify.

### Template Modernization (v10.3)
- Next.js templates updated for v16: `--yes`/`--turbopack` flags, `proxy.ts` notes, async request APIs, Cache Components (`'use cache'`)
- Swift templates clarify `@Observable` vs `@Published` to prevent silent bugs
- Expo templates add explicit `expo-router` installation

### Previous Versions
- **v10.0** — Post-mortem fixes: dependency audit, data wiring verification, RLS circular dep prevention, CRITICAL override
- **v9.1** — Crash recovery: `--resume` in v8+ mode, atomic checkpoints, artifact verification
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
| **django-htmx** | Admin panels, data apps, Python backends | PostgreSQL | Railway |
| **sveltekit** | Fast SaaS, dashboards, interactive apps | Any | Vercel |
| **astro** | Blogs, docs, landing pages, portfolios | None (static) | Vercel |
| **expo-supabase** | Mobile apps, consumer apps | PostgreSQL (Supabase) | App Stores |
| **swift-swiftui** | Native iOS apps, plugin modules | Local storage | TestFlight / SPM |

Force a specific stack:
```bash
product-agent --stack django-htmx "Build a data management admin panel"
product-agent --stack astro "Build a documentation site"
product-agent --stack sveltekit "Build a fast dashboard app"
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

Enhancement mode replaces Analyze + Design/Review with a single ENHANCE phase that modifies an existing design.

### Pipeline Phases

| # | Phase | What It Does | Validates |
|---|-------|-------------|-----------|
| 1 | **Enrich** (optional) | Researches domain, expands idea into detailed spec | PROMPT.md exists, 100+ chars |
| 2 | **Analyze** | Selects optimal tech stack | STACK_DECISION.md with valid stack ID |
| 3 | **Design** | Creates data model, pages, components | DESIGN.md with required sections |
| 4 | **Review** | Validates design (loop, max 3 revisions) | REVIEW.md with APPROVED/NEEDS_REVISION |
| — | **Enhance** (enhancement mode) | Modifies existing design with new features | DESIGN.md updated with (NEW) markers |
| 5 | **Build** | Implements full application (max 5 attempts) | Source files exist, entry point present |
| 6 | **Audit** | Verifies build matches requirements | SPEC_AUDIT.md with pass/fail counts |
| 7 | **Test** | Generates and runs tests | TEST_RESULTS.md with pass/fail counts |
| 8 | **Deploy** | Deploys to production + sets up CI/CD | Deployment URL extracted |
| 9 | **Verify** | Tests deployed app | VERIFICATION.md with status |

Audit and Test run in parallel. Design loops with Review until approved.

### Subagents

| Agent | Purpose | Max Turns |
|-------|---------|-----------|
| **enricher** | Researches domain, expands ideas into specs | 20 |
| **analyzer** | Selects stack, validates compatibility | 15 |
| **designer** | Creates DESIGN.md with architecture | 25 |
| **reviewer** | Validates design completeness | 15 |
| **enhancer** | Adds features to existing designs | 40 |
| **builder** | Implements app with cross-referencing | 80 |
| **auditor** | Audits build against original requirements | 20 |
| **tester** | Generates and runs tests | 30 |
| **deployer** | Deploys with pre-validation + observability setup | 25 |
| **verifier** | Tests deployed app | 15 |

## Usage Examples

### Basic (Fully Autonomous)

```bash
product-agent "Build a task management app"
```

### AI-Powered Apps

```bash
product-agent "Build a chatbot for customer support with conversation history"
product-agent "Build an AI-powered writing assistant"
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

### Enhancement Mode

```bash
product-agent --design-file ./project/DESIGN.md \
  --enhance-features "board-views,dashboards" \
  "Enhance project management app"
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

Before starting a new build, the agent searches for similar past builds using Jaccard similarity and injects patterns from successful builds into the pipeline context. Failure reasons and lessons are recorded per build and injected into builder prompts to prevent repeating mistakes.

## Quality Scoring

After all phases complete, a 5-factor quality score is computed:

| Factor | Weight | What It Measures |
|--------|--------|-----------------|
| Functional Verification | 35 pts | Did deployed endpoints return expected results? |
| Test Pass Rate | 25 pts | Were tests generated and did they pass? |
| Spec Coverage | 20 pts | How many requirements were met in audit? |
| Build Efficiency | 10 pts | How many build attempts were needed? |
| Design Quality | 10 pts | How many design revisions were needed? |

**Hard caps**: `deployment_verified=False` caps grade at C. `tests_generated=False` caps grade at B-. `spec_audit_critical_count > 0` caps grade at B.

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
├── sanitize.py             # Input sanitization
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
│   ├── enhance.py          # Enhancement phase (v10.2)
│   ├── build.py            # Build phase
│   ├── audit.py            # Spec audit phase
│   ├── test.py             # Test phase
│   ├── deploy.py           # Deploy phase
│   └── verify.py           # Verify phase
├── agents/
│   └── definitions.py      # 10 subagent prompts + per-stack template injection
├── stacks/
│   ├── criteria.py         # 8 stack definitions and scoring
│   ├── selector.py         # Stack selection logic
│   └── templates/          # Stack-specific templates
│       ├── nextjs-supabase/
│       ├── nextjs-prisma/
│       ├── rails/
│       ├── django-htmx/    # v11.0
│       ├── sveltekit/      # v11.0
│       ├── astro/          # v11.0
│       ├── expo-supabase/
│       └── swift-swiftui/
├── domains/
│   ├── __init__.py         # Domain registry
│   ├── marketplace/
│   ├── saas/
│   ├── internal_tool/
│   ├── content_site/
│   ├── plugin_host/
│   ├── plugin_module/
│   └── ai_app/             # v11.0
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

1,627 tests across 22 test files:

| Test File | Tests | Coverage |
|-----------|-------|---------|
| `test_orchestrator_v8.py` | 114 | Full v8 pipeline, retry, quality gate, parallel phases |
| `test_safety.py` | 183 | Blocked commands, shell-aware splitting, path protection |
| `test_phases.py` | 142 | Phase registry, PhaseConfig, run_phase, SDK logging |
| `test_swift_modes.py` | 100 | Swift state, criteria, prompts, domains |
| `test_validators.py` | 93+ | All phase validators, YAML front-matter, extraction |
| `test_new_stacks.py` | 80 | Django, SvelteKit, Astro definitions, selection, templates |
| `test_quality.py` | 77+ | Outcome-based scoring, grade caps, report formatting |
| `test_history.py` | 78 | BuildRecord, failure learning, similarity search |
| `test_agent_prompts.py` | 74 | Registry, tools, all 10 agents, template injection |
| `test_progress.py` | 55 | PhaseResult, ProgressReporter, formatting |
| `test_checkpoints.py` | 44 | Save/load/resume, cleanup, archive, phase cap |
| `test_stack_selection.py` | 44 | Keyword analysis, scoring, selection |
| `test_enhancement.py` | 35 | Enhancement phase, validator, orchestrator, serialization |
| `test_config.py` | 33 | Env var loading, feature flags, defaults |
| `test_orchestration.py` | 34 | Legacy orchestration, build modes, prompt content |
| `test_sanitize.py` | 25 | Input sanitization, injection markers, edge cases |
| `test_pipeline_features.py` | 21 | AI domain, CI/CD, observability |
| + 5 more | ~200+ | Recovery, validation, state v5/v6, CLI runner |

### Domain Patterns

| Domain | Product Types | Key Patterns |
|--------|--------------|--------------|
| **marketplace** | Marketplaces, two-sided platforms | Buyer/seller flows, listings, transactions |
| **saas** | SaaS, multi-tenant apps | Organizations, subscriptions, billing |
| **internal_tool** | Admin panels, dashboards | Data tables, CRUD, reporting |
| **content_site** | Nonprofits, portfolios, blogs | Static-first data, hero sections, FAQ accordion |
| **ai_app** | Chatbots, AI assistants, AI tools | AI SDK v6, streamText, useChat, chat history |
| **plugin_host** | iOS plugin host apps | Plugin registry, shared services, dynamic TabView |
| **plugin_module** | Swift Package plugins | NCBSPlugin protocol, MVVM, compressed storage |

## CLI Arguments

```
product-agent [OPTIONS] IDEA

Arguments:
  IDEA                      The product idea to build

Options:
  --project-dir DIR         Project directory (default: ./projects/new-product)
  --stack STACK             Force stack: nextjs-supabase, nextjs-prisma, rails, django-htmx, sveltekit, astro, expo-supabase, swift-swiftui
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
| **v11.1** | **AI app domain, CI/CD generation, Vercel Analytics observability** |
| **v11.0** | **3 new stacks: Django+HTMX, SvelteKit, Astro. 8 stacks total** |
| v10.3 | Template modernization: Next.js 16 patterns, async APIs, Cache Components |
| v10.2 | Enhancement mode fully wired into pipeline |
| v10.1 | Audit fixes: version, template bugs, test coverage |
| v10.0 | Post-mortem fixes: dependency audit, data wiring, RLS circular deps, CRITICAL override |
| v9.1 | Crash recovery: `--resume`, atomic checkpoints, artifact verification |
| v9.0 | Reliability overhaul: quality scoring, YAML contracts, SDK logging, timeouts |
| v8.0 | Phase-by-phase orchestration, build memory, quality scoring, public API |
| v7.0 | Swift/SwiftUI stack, plugin build mode, NCBSPlugin protocol, XCTest |
| v6.0 | Spec audit, prompt enrichment, content site domain |
| v5.0 | Deployment validation, verification, checkpoints, automated testing |

## Requirements

- Python 3.10+
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- Claude Pro subscription
- Node.js 20+ (for generated web apps)
- Swift 5.9+ / Xcode 15+ (for Swift/SwiftUI builds)
- Ruby 3.1+ / Rails 7+ (for Rails builds)
- Python 3.10+ (for Django builds)
