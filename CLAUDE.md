# CLAUDE.md — Product Agent Golden Rules & Project Guide

This file tells Claude (and any human) how to work on this codebase.
Read this before making any changes.

---

## Golden Rules

1. **Read before you write.** Never modify a file without reading it first. Understand existing code before changing it.
2. **Test before you commit.** Always run `python3 -m pytest tests/ -x` and confirm all 1,627+ tests pass before committing.
3. **Commit after every meaningful change.** Don't batch everything into one giant commit at the end. Each logical change gets its own commit with a descriptive message.
4. **Comment the why, not just the what.** Every function gets a docstring. Every non-obvious line gets an inline `#` comment explaining *why* it exists, not just what it does.
5. **Keep comments current.** When you change code, update its comments. Stale comments are worse than no comments.
6. **Do only what was asked.** Never add features, refactoring, or "improvements" beyond the request. A bug fix doesn't need surrounding code cleaned up.
7. **Never commit secrets.** No `.env`, `credentials.json`, API keys, or tokens. The `.gitignore` covers these — don't override it.
8. **New files need tests.** When adding a new module, add corresponding tests in `tests/`.
9. **Don't break the build.** If tests fail after your change, fix them before moving on.
10. **Use the existing patterns.** Check how similar things are done elsewhere in the codebase before inventing new approaches.
11. **Only enhance, never remove.** Every change should make the agent better. Add, update, improve, and extend — but never delete capabilities or remove features. We only enhance and perfect the agent.

---

## Architecture Overview

Product Agent is an autonomous pipeline that builds full-stack apps from plain English descriptions.

### How It Works

```
User idea → Python orchestrator → 9 Claude SDK calls → Deployed app
```

The **Python orchestrator** (`orchestrator.py`) controls the pipeline. Each of 9 phases is its own Claude SDK call. Python validates between phases, enforces ordering, manages state, and handles retries.

### Phase Pipeline

```
Enrich → Analyze → Design ←→ Review → Build → Audit ─┐
                                                       ├→ Test → Deploy → Verify
                                                       ┘ (parallel)
```

1. **Enrich** — Research domain, expand idea into detailed spec (optional)
2. **Analyze** — Select optimal tech stack from 5 options
3. **Design** — Create data model, pages, components → DESIGN.md
4. **Review** — Validate design (loops back to Design if NEEDS_REVISION, max 3 times)
5. **Build** — Implement full application (max 5 attempts, errors injected into retries)
6. **Audit** — Verify build matches requirements → SPEC_AUDIT.md (runs parallel with Test)
7. **Test** — Generate and run tests → TEST_RESULTS.md (runs parallel with Audit)
8. **Deploy** — Deploy to production (Vercel/Railway/TestFlight)
9. **Verify** — Test deployed app → VERIFICATION.md

### Data Flow

Each phase produces **markdown artifacts** in the project directory (DESIGN.md, SPEC_AUDIT.md, etc.). Validators in `validators.py` parse these using **YAML front-matter** as the primary method and **regex as fallback**. When both fail, the phase fails explicitly — no silent pass-throughs.

### Stacks

| Stack ID | Tech | Deploys To |
|----------|------|------------|
| `nextjs-supabase` | Next.js + Supabase | Vercel |
| `nextjs-prisma` | Next.js + Prisma | Vercel |
| `rails` | Ruby on Rails | Railway |
| `expo-supabase` | Expo + Supabase | App Stores |
| `swift-swiftui` | Swift + SwiftUI | TestFlight / SPM |

Per-stack templates live in `agent/stacks/templates/{stack_id}/` — scaffold.md, patterns.md, builder.md, deploy.md, tests.md.

---

## Key Files Quick Reference

### Core Pipeline
| File | What It Does |
|------|-------------|
| `agent/orchestrator.py` | Main entry point. `build_product()` runs the 9-phase pipeline with validation, retries, and quality scoring. |
| `agent/validators.py` | Validates each phase's output. Parses YAML front-matter, extracts metrics, checks file existence. |
| `agent/cli_runner.py` | Runs Claude SDK calls. Each phase gets its own event loop to prevent cancel scope leaks. |
| `agent/quality.py` | Computes quality score (A/B/C/F) from verification, tests, spec coverage, efficiency, design. |
| `agent/state.py` | `AgentState` dataclass tracking phase, attempts, errors, timestamps. Serializes to JSON. |
| `agent/config.py` | Loads env vars (API keys, tokens). Provides `get_config()` dict. |

### Agent Prompts & Templates
| File | What It Does |
|------|-------------|
| `agent/agents/definitions.py` | All 10 agent prompt definitions. `get_agent_prompt()` injects per-stack templates. |
| `agent/stacks/templates/*/` | Per-stack templates: scaffold.md (structure), patterns.md (code patterns), builder.md (build steps). |
| `agent/stacks/selector.py` | Analyzes idea keywords, scores stacks, selects best fit. |
| `agent/stacks/criteria.py` | Stack definitions, compatibility checks, deployment type mapping. |

### Supporting Systems
| File | What It Does |
|------|-------------|
| `agent/phases/__init__.py` | Phase registry. `run_phase()` dispatches to phase modules, logs prompts/responses to `.agent_logs/`. |
| `agent/checkpoints.py` | Save/load/resume checkpoints. `cleanup()` deletes old ones. `archive()` zips for post-mortem. |
| `agent/history.py` | Build memory. Logs builds to JSONL, finds similar past builds, extracts failure lessons. |
| `agent/progress.py` | Real-time progress reporting. Phase-by-phase streaming output. |
| `agent/recovery.py` | Error pattern matching and recovery strategies. Injects fix suggestions into retry prompts. |
| `agent/sanitize.py` | Sanitizes user input before prompt injection. Strips injection markers, caps length. |
| `agent/hooks/safety.py` | Safety hooks. Blocks dangerous commands, protects system paths, auto-approves safe operations. |
| `agent/domains/__init__.py` | Domain classification (marketplace, saas, internal_tool, content_site, plugin_host, plugin_module). |
| `agent/mcp/servers.py` | MCP server configurations (GitHub, Supabase, Vercel). |

### Entry Points
| File | What It Does |
|------|-------------|
| `agent/main.py` | CLI entry point. Parses args, routes to v8+ orchestrator or legacy mode. |
| `agent/api.py` | Clean public API: `from agent.api import build`. |

---

## Coding Conventions

- **Python 3.10+** — Use `X | Y` union types, not `Union[X, Y]`. Use `list[str]`, not `List[str]`.
- **Type hints everywhere** — All function signatures get type annotations.
- **Black formatter** — 100 char line length. Run `black .` to format.
- **Ruff linter** — 100 char line length. Run `ruff check .` to lint.
- **pytest** — Tests in `tests/`. Async mode is `auto` (no need for `@pytest.mark.asyncio`).
- **Dataclasses** for data containers, **Enums** for state machines.
- **`pathlib.Path`** over `os.path` for all file operations.
- **No global mutable state** — pass config/state explicitly.

---

## Comment Style Guide

### What to comment

```python
# Module docstring at top of every file — explains purpose and version context
"""State management for Product Agent v7.0.

Tracks the agent's progress through phases and handles iteration limits.
"""

# Function docstrings — Args, Returns, and purpose
def find_similar_builds(self, idea: str, limit: int = 3) -> list[BuildRecord]:
    """Find builds with similar ideas using Jaccard word similarity."""

# Inline comments — explain WHY, not what
score += 0.3  # Boost same-stack matches so stack-specific lessons rank higher

# Explain magic numbers
if total > 69:  # 69 = grade C ceiling. Unverified builds can't score higher.
    total = 69

# Explain non-obvious patterns
for mw_path in middleware_paths:
    if (project_dir / mw_path).exists():
        break
else:
    # Python for/else: else runs when loop finishes WITHOUT breaking
    # i.e., no middleware file was found in any of the expected paths
    result.add_warning("Auth mentioned but no middleware.ts found")

# Explain defensive code
turns = call_result.num_turns if isinstance(call_result.num_turns, int) else 0
# Type-check because mocks and edge cases can return non-int values
```

### What NOT to comment

```python
# BAD: Restating what the code does
self.phase = new_phase  # Set the phase to new_phase

# BAD: Commented-out code (delete it, git has the history)
# old_score = compute_legacy_score(state)

# BAD: TODO without context
# TODO: fix this
```

---

## Git Workflow

1. **Commit after every meaningful change** — not just at the end of a task.
   - Finished adding comments to a file? Commit.
   - Created a new module? Commit.
   - Fixed a bug? Commit.

2. **Run tests before committing:**
   ```bash
   python3 -m pytest tests/ -x
   ```

3. **Commit message format:**
   ```
   Short imperative summary (50 chars or less)

   Optional body explaining WHY, not what. What is in the diff.

   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
   ```

4. **Never force push to main.**

5. **Stage specific files** — use `git add file1.py file2.py`, not `git add .` (avoids accidentally committing secrets or large files).

---

## Testing

```bash
# Run all tests
python3 -m pytest tests/ -x

# Run a specific test file
python3 -m pytest tests/test_validators.py -v

# Run tests matching a keyword
python3 -m pytest tests/ -k "test_quality" -v
```

Tests live in `tests/`. Each `agent/*.py` module has a corresponding `tests/test_*.py` file.
Current count: 1,627 tests across 22 test files.

---

## Quick Start for Development

```bash
cd /Users/natenelson/Projects/product-agent
pip install -e ".[dev]"
python3 -m pytest tests/ -x          # Verify everything works
product-agent "Build me a todo app"  # Run a test build
```
