# Product Agent v7.0

An autonomous AI agent that builds, tests, and deploys web and native iOS applications from plain English descriptions.

## What It Does

```bash
python -m agent.main "Build me a todo app with user authentication"
```

**Output:**
```
Your app is live at https://todo-app-abc123.vercel.app - Tests: PASSED - Verification: PASSED
```

The agent autonomously:
1. **Enriches** your idea with research (optional, v6.0)
2. **Analyzes** your idea and selects the optimal tech stack
3. **Designs** the data model, pages, and components
4. **Reviews** the design for completeness
5. **Builds** a complete application, cross-referencing the original prompt
6. **Audits** the build against the original requirements (v6.0)
7. **Tests** the application with generated tests
8. **Deploys** to production
9. **Verifies** the deployment works correctly

No human intervention required.

## What's New in v7.0

- **Swift/SwiftUI Stack** — New `swift-swiftui` stack for native iOS development. Build complete iOS apps and modular Swift Package plugins.
- **Plugin Build Mode** — New `--mode` flag (`host` or `plugin`) for building the NoCloud BS plugin host app or individual Swift Package modules.
- **NCBSPlugin Protocol** — Standard interface that all generated plugins conform to, with shared services (compression, storage, network) via PluginContext.
- **XCTest Integration** — Automated test generation for Swift with minimum 8 tests (plugins) or 15 tests (host app).
- **TestFlight Deployment** — Host apps can be archived and uploaded to TestFlight. Plugins are distributed as tagged Swift Packages.

### Previous: v6.0
- Spec Audit, Original Prompt Passthrough, Prompt Enrichment, Upgraded Testing, Content Site Domain.

## Quick Start

### 1. Install

```bash
cd /Users/natenelson/Projects/product-agent
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
python -m agent.main "Build me a simple blog"
```

## Available Stacks

The agent automatically selects the best stack for your product:

| Stack | Best For | Database | Deploys To |
|-------|----------|----------|------------|
| **nextjs-supabase** (default) | SaaS, internal tools, dashboards, content sites | PostgreSQL (Supabase) | Vercel |
| **nextjs-prisma** | Marketplaces, multi-tenant, complex data | PostgreSQL | Vercel |
| **rails** | Rapid prototyping, admin-heavy apps | PostgreSQL | Railway |
| **expo-supabase** | Mobile apps, consumer apps | PostgreSQL (Supabase) | App Stores |
| **swift-swiftui** (v7.0) | Native iOS apps, plugin modules | Local storage | TestFlight / SPM |

Force a specific stack:
```bash
python -m agent.main --stack nextjs-prisma "Build a freelancer marketplace"
```

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                                │
│                    (Main Product Agent v7.0)                        │
└─────────────────────────────────────────────────────────────────────┘
                                │
    ┌────────┬────────┬────────┬┴───────┬────────┬────────┬────────┬────────┬────────┐
    ▼        ▼        ▼        ▼        ▼        ▼        ▼        ▼        ▼        ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│ENRICHER││ANALYZER││DESIGNER││REVIEWER││BUILDER ││AUDITOR ││ TESTER ││DEPLOYER││VERIFIER││ENHANCER│
│ (v6.0) ││        ││        ││        ││        ││ (v6.0) ││ (v5.1) ││        ││ (v5.0) ││        │
└────────┘└────────┘└────────┘└────────┘└────────┘└────────┘└────────┘└────────┘└────────┘└────────┘
    │         │         │         │         │         │         │         │         │
    ▼         ▼         ▼         ▼         ▼         ▼         ▼         ▼         ▼
 PROMPT.md  STACK    DESIGN    REVIEW   App Code   SPEC     TEST      Vercel   VERIFY
 (opt-in)  DECISION   .md       .md   + ORIGINAL  AUDIT   RESULTS.md   URL      .md
             .md                       PROMPT.md    .md
```

### Workflow (8 Phases)

1. **Enrich** (optional) → Researches domain and expands idea into detailed spec
2. **Analysis** → Selects stack, validates deployment compatibility
3. **Design** → Creates architecture (with review loop, max 2 revisions)
4. **Build** → Implements app, cross-references original prompt (max 5 attempts)
5. **Audit** → Verifies build matches original requirements (max 1 fix attempt)
6. **Test** → Generates and runs tests including content verification (max 3 attempts)
7. **Deploy** → Deploys to production (with pre-validation)
8. **Verify** → Tests deployed app functionality

### Subagents

| Agent | Purpose | When Used |
|-------|---------|-----------|
| **enricher** | Researches domain, expands rough ideas into detailed specs | First (if `--enrich`, v6.0) |
| **analyzer** | Selects stack, validates deployment compatibility | First (or after enricher) |
| **designer** | Creates DESIGN.md with data model, pages, components | After analysis |
| **reviewer** | Validates design completeness | After design |
| **builder** | Implements app, cross-references ORIGINAL_PROMPT.md | After approval |
| **auditor** | Verifies build matches original prompt, produces SPEC_AUDIT.md | After build (v6.0) |
| **tester** | Generates and runs tests (route, content, nav, form) | After audit |
| **deployer** | Deploys with pre-validation | After tests pass |
| **verifier** | Tests deployed app | After deployment |
| **enhancer** | Adds features to existing designs | Enhancement mode |

## Usage Examples

### Basic (Fully Autonomous)

```bash
python -m agent.main "Build a task management app"
```

### With Prompt Enrichment (v6.0)

Research a reference site and build from it:
```bash
python -m agent.main --enrich-url "https://example-nonprofit.org" \
  "Rebuild this nonprofit website"
```

Or just enrich from web research:
```bash
python -m agent.main --enrich "Build a dental charity nonprofit website"
```

### Custom Project Directory

```bash
python -m agent.main --project-dir ./my-app "Build a todo app"
```

### Force a Specific Stack

```bash
python -m agent.main --stack rails "Build an admin dashboard"
```

### With Checkpoints (Human Approval)

```bash
python -m agent.main --checkpoints "Build an e-commerce store"
```

### Resume from Checkpoint

```bash
python -m agent.main --resume "Build an e-commerce store"
```

### Enhancement Mode (Add Features to Existing Design)

```bash
python -m agent.main \
  --design-file ./existing-project/DESIGN.md \
  --enhance-features "board-views,dashboards,automations" \
  "Enhance project management app"
```

### Build a Swift Plugin Module (v7.0)

```bash
python -m agent.main --stack swift-swiftui --mode plugin \
  --project-dir ./projects/photo-gallery \
  "Photo gallery plugin with compressed local albums"
```

### Build the Host App (v7.0)

```bash
python -m agent.main --stack swift-swiftui --mode host \
  --project-dir ./projects/nocloudbs-host \
  "NoCloud BS host app with plugin system and storage dashboard"
```

### Legacy Mode (v3.0 - Fixed Stack)

```bash
python -m agent.main --legacy "Build a simple todo app"
```

## Generated Project Structure

After running, you get:

```
projects/new-product/
├── ORIGINAL_PROMPT.md     # Original idea for cross-reference (v6.0)
├── STACK_DECISION.md      # Stack analysis and selection
├── DESIGN.md              # Architecture decisions
├── REVIEW.md              # Design review status
├── SPEC_AUDIT.md          # Build vs prompt audit results (v6.0)
├── TEST_RESULTS.md        # Test execution results
├── VERIFICATION.md        # Deployment verification
├── .agent_checkpoints/    # Checkpoint files for resume
├── src/
│   ├── app/               # Next.js pages
│   ├── components/        # React components
│   │   ├── ui/            # Reusable UI components
│   │   ├── layout/        # Layout components
│   │   └── features/      # Feature components
│   ├── lib/               # Utilities and data
│   │   ├── supabase/      # Supabase clients (or prisma.ts)
│   │   ├── *-data.ts      # Static data files (content sites)
│   │   ├── utils.ts       # Helper functions
│   │   └── validation.ts  # Zod schemas
│   ├── actions/           # Server actions
│   ├── types/             # TypeScript types
│   └── test/              # Test setup
├── vitest.config.ts       # Test configuration
├── package.json
├── prisma/                # (if using nextjs-prisma)
│   └── schema.prisma
└── .env.local.example
```

## Configuration

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | Claude API access |
| `GITHUB_TOKEN` | No | GitHub MCP integration |
| `SUPABASE_ACCESS_TOKEN` | No | Supabase MCP integration |
| `VERCEL_TOKEN` | No | Vercel MCP integration |

### Feature Flags

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENABLE_CHECKPOINTS` | false | Manual approval at each phase |
| `ENABLE_STACK_SELECTION` | true | Automatic stack selection |
| `ENABLE_DESIGN_REVIEW` | true | Design review loop |
| `ENABLE_TEST_GENERATION` | true | Generate and run tests |
| `ENABLE_VERIFICATION` | true | Post-deployment verification |
| `REQUIRE_PASSING_TESTS` | true | Block deployment if tests fail |
| `ENABLE_SPEC_AUDIT` | **true** | Spec audit after build (v6.0) |
| `ENABLE_FUNCTIONAL_TESTS` | **true** | Enhanced test categories (v6.0) |
| `PASS_ORIGINAL_PROMPT_TO_BUILDER` | **true** | Write ORIGINAL_PROMPT.md for builder (v6.0) |
| `ENABLE_PROMPT_ENRICHMENT` | **false** | Prompt enrichment phase (v6.0, opt-in) |
| `LEGACY_MODE` | false | Disable v4.0+ features |

### Iteration Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| `MAX_DESIGN_REVISIONS` | 2 | Maximum design revision cycles |
| `MAX_BUILD_ATTEMPTS` | 5 | Maximum build retry attempts |
| `MAX_TEST_ATTEMPTS` | 3 | Maximum test retry attempts |
| `MAX_VERIFICATION_ATTEMPTS` | 2 | Maximum verification retries |
| `MAX_AUDIT_FIX_ATTEMPTS` | **1** | Maximum audit fix attempts (v6.0) |

## CLI Arguments

```
python -m agent.main [OPTIONS] IDEA

Arguments:
  IDEA                      The product idea to build

Options:
  --project-dir DIR         Project directory (default: ./projects/new-product)
  --stack STACK             Force stack: nextjs-supabase, nextjs-prisma, rails, expo-supabase, swift-swiftui
  --mode MODE               Build mode: standard, host, plugin (v7.0)
  --checkpoints             Enable checkpoints for human approval
  --resume                  Resume from most recent checkpoint
  --resume-from ID          Resume from specific checkpoint ID
  --list-checkpoints        List available checkpoints and exit
  --legacy                  Use legacy v3.0 mode (fixed stack)
  --design-file PATH        Existing DESIGN.md for enhancement mode
  --enhance-features LIST   Comma-separated: board-views,dashboards,automations
  --enrich                  Enable prompt enrichment phase (v6.0)
  --enrich-url URL          Reference URL for enrichment research (v6.0, implies --enrich)
  --verbose                 Show detailed progress
```

## Domain Patterns

The agent includes domain-specific patterns for different product types:

| Domain | Product Types | Key Patterns |
|--------|--------------|--------------|
| **marketplace** | Marketplaces, two-sided platforms | Buyer/seller flows, listings, transactions |
| **saas** | SaaS, multi-tenant apps | Organizations, subscriptions, billing |
| **internal_tool** | Admin panels, dashboards | Data tables, CRUD, reporting |
| **content_site** (v6.0) | Nonprofits, portfolios, marketing sites, blogs, event sites | Static-first data, hero sections, image placeholders, FAQ accordion |
| **plugin_host** (v7.0) | iOS plugin host apps | Plugin registry, shared services, dynamic TabView |
| **plugin_module** (v7.0) | Swift Package plugins | NCBSPlugin protocol, MVVM, compressed storage |

## Safety Features

The agent includes safety hooks that:
- **Block** dangerous commands (`rm -rf /`, fork bombs, disk writes)
- **Protect** system directories and credentials
- **Auto-approve** safe operations (npm, git, file writes in project)
- **Validate** deployment compatibility (SQLite + Vercel = blocked)

## Development

### File Structure

```
agent/
├── main.py                 # Orchestrator (v7.0)
├── config.py               # Environment configuration
├── state.py                # Phase and state management
├── checkpoints.py          # Checkpoint system
├── recovery.py             # Error recovery
├── test_validation.py      # Test result parsing
├── cli_runner.py           # Claude Code CLI runner
├── agents/
│   └── definitions.py      # 10 subagent definitions
├── stacks/
│   ├── criteria.py         # Stack definitions
│   ├── selector.py         # Stack selection logic
│   └── templates/          # Stack-specific templates
│       ├── nextjs-supabase/
│       ├── nextjs-prisma/
│       ├── rails/
│       ├── expo-supabase/
│       └── swift-swiftui/  # v7.0
├── domains/
│   ├── __init__.py         # Domain registry
│   ├── marketplace/
│   ├── saas/
│   ├── internal_tool/
│   ├── content_site/       # v6.0
│   │   └── patterns.md
│   ├── plugin_host/        # v7.0
│   │   └── patterns.md
│   └── plugin_module/      # v7.0
│       └── patterns.md
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

304 tests across 5 test files:
- `test_recovery.py` — Error analysis and recovery prompts
- `test_safety.py` — Safety hook patterns
- `test_validation.py` — Test result parsing
- `test_state_v5.py` — v5.0 state features
- `test_state_v6.py` — v6.0 phases, fields, serialization, config, domains, agents

### Stack Templates

Each stack has templates in `agent/stacks/templates/{stack}/`:
- `scaffold.md` - Initial setup commands
- `patterns.md` - Code patterns to follow
- `deploy.md` - Deployment instructions
- `tests.md` - Test generation patterns

## Version History

| Version | Description |
|---------|-------------|
| v1.0 | 12,000+ lines of markdown instructions, 26 templates |
| v2.0 | Simplified to 770 lines, 4 templates, 3 checkpoints |
| v3.0 | Autonomous agent using Claude Code SDK |
| v4.0 | Stack selection, design review, iteration limits |
| v5.0 | Deployment validation, verification, checkpoints |
| v5.1 | Automated testing, tester agent, test templates |
| v6.0 | Spec audit, prompt passthrough, enricher agent, content site domain, upgraded testing |
| **v7.0** | **Swift/SwiftUI stack, plugin build mode (host/plugin), NCBSPlugin protocol, XCTest integration, TestFlight deployment** |

## Example Projects

The `projects/` directory contains example builds:
- `global-dental-relief/` - Nonprofit website (13 pages, 46 tests)
- `lacey-real-estate/` - Real estate marketing site
- `project-manager/` - Project management tool
- `test-todo/` - Simple todo app
- `knowledgehub-hr/` - HR knowledge management

## Requirements

- Python 3.10+
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- Claude Pro subscription
- Node.js 18+ (for generated web apps)
- Swift 5.9+ / Xcode 15+ (for Swift/SwiftUI builds, v7.0)
