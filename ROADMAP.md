# Product Agent — Roadmap

## Current State (v11.1)

Local CLI tool. 8 stacks, 10 agents, 1,627 tests. Runs on user's machine with their Claude Pro subscription.

---

## Phase 1: Harden (v12-v15)

**Goal:** Run 20-30 real builds across diverse prompts, post-mortem each one, fix what breaks.

- [ ] Stress test each of the 8 stacks with complex prompts
- [ ] Post-mortem every build — log failures, update templates, fix validators
- [ ] Build memory database grows with each build (failure patterns, recovery prompts)
- [ ] Address build timeout issues for complex apps (dynamic timeout based on table count?)
- [ ] Reviewer loop tuning — 3 revisions every time wastes tokens, tighten criteria
- [ ] Finish deep commenting pass on remaining 18 modules

**Success metric:** Consistent B+ or higher on complex SaaS builds. Simple apps score A.

---

## Phase 2: Open Source Release (v16)

**Goal:** Ship on GitHub as a free CLI tool with a clean install story.

- [ ] Clean README with GIF demo of a full build
- [ ] `pip install product-agent` (PyPI package)
- [ ] One-command setup: `product-agent init` (checks dependencies, sets env vars)
- [ ] Example gallery: 10+ built projects with screenshots and quality scores
- [ ] Documentation site (use Astro stack to dogfood it)
- [ ] MIT license, contributor guidelines, issue templates

---

## Phase 3: Premium Templates (v17 — First Revenue)

**Goal:** Free tool, paid template library. $9/month subscription.

**Business model:** The CLI is free and open source. Premium subscribers get:
- Advanced stack templates (production patterns, not starter patterns)
- Shared build memory (lessons from thousands of builds across all users)
- Priority template updates (new stacks, framework upgrades)
- Premium domain patterns (e-commerce, healthcare, fintech, etc.)

**Implementation:**
- License key validation in CLI (check on startup, cache locally)
- Premium templates encrypted or fetched from API on valid subscription
- Stripe billing via simple landing page
- Use product-agent itself to build the landing page (dogfooding)

**Why this model:** Users bring their own Claude subscription (no API costs for us). We sell the intelligence layer — the templates, patterns, and accumulated build memory that make outputs better.

---

## Phase 4: Hosted Platform (v20+ — Big Vision)

**Goal:** Full SaaS — users submit prompts via web UI, get deployed apps back.

**Architecture:**
```
User (browser) → Next.js frontend (Vercel)
  → Workflow DevKit (durable orchestration)
    → Anthropic API (direct, not Claude Code SDK)
    → Vercel Sandbox (Firecracker microVMs for npm install, build, etc.)
    → Vercel API (create project, deploy to user's Vercel account)
  → Dashboard (build history, quality scores, project management)
```

**Key changes from CLI version:**
- Rewrite orchestration in TypeScript (same 9-phase logic, different execution layer)
- Anthropic API directly instead of Claude Code SDK (programmatic control, cost tracking)
- Vercel Sandbox for safe code execution (no filesystem access on shared infra)
- OAuth with Vercel for deploying to user's account
- Per-build or subscription pricing ($5-20/build or $29-99/month)

**Why TypeScript:** The apps being built ARE TypeScript (Next.js). Agent can dogfood its own stack. Vercel deployment is native. AI SDK integration is direct.

**Cost model:** ~$2-5 per build in Claude API tokens. Price at $5-20/build for margin. Subscription tiers for volume users.

---

## Revenue Projections (Rough)

| Phase | Model | Price | Target |
|-------|-------|-------|--------|
| Phase 3 | Premium templates | $9/mo | 100 subscribers = $900/mo |
| Phase 4 | Hosted builds | $29-99/mo | 500 users = $15K-50K/mo |
| Phase 4+ | Enterprise | Custom | Teams, SSO, private templates |

---

## Decision Log

- **Why Python now:** Claude Code SDK support, fast iteration for post-mortem cycles, bottleneck is Claude not Python
- **Why TypeScript later:** Hosted platform needs Vercel-native stack, AI SDK integration, same language as output
- **Why not Java/C++:** No SDK support, wrong tool for orchestration, slower iteration
- **Why open source first:** Build community, get real usage data, prove the tool works before charging for hosted version
