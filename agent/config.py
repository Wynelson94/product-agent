"""Configuration and environment variables for Product Agent v11.1.

All settings are loaded from environment variables at import time.
Defaults are tuned for typical builds. Override via env vars or .env files.

Why import-time loading: The config module is imported once at startup, so all
values are computed once. This avoids repeated os.environ lookups during builds.
The tradeoff is that env vars can't be changed mid-process — restart required.
"""

import os
from pathlib import Path


def get_env(key: str, default: str | None = None) -> str | None:
    """Get environment variable with optional default.

    Returns None if the key is not set and no default is provided.
    Used for optional settings (tokens, feature flags with defaults).
    """
    return os.environ.get(key, default)


def require_env(key: str) -> str:
    """Get required environment variable, raise if missing.

    Used at call sites that need a value to proceed (e.g., ANTHROPIC_API_KEY
    validation before starting a build). Not used at module scope to avoid
    crashing on import when the key isn't needed yet.
    """
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value


# API Keys — all optional at import time. ANTHROPIC_API_KEY is validated
# at build start in orchestrator.py, not here, so importing config.py
# doesn't crash when the key isn't set (e.g., during testing).
ANTHROPIC_API_KEY = get_env("ANTHROPIC_API_KEY")
GITHUB_TOKEN = get_env("GITHUB_TOKEN")          # For GitHub MCP server
SUPABASE_ACCESS_TOKEN = get_env("SUPABASE_ACCESS_TOKEN")  # For Supabase MCP server
VERCEL_TOKEN = get_env("VERCEL_TOKEN")           # For Vercel MCP server

# Defaults
DEFAULT_PROJECT_DIR = Path("./projects/new")  # Relative to CWD — set --project-dir for explicit control
# Model name is pinned to a specific dated snapshot for reproducibility.
# Override with ANTHROPIC_MODEL env var if this model is deprecated.
DEFAULT_MODEL = get_env("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
MAX_TURNS = 200  # Per-phase turn limit (global limit is MAX_TOTAL_TURNS below)

# Feature flags — boolean env vars parsed as lowercase string comparison.
# Pattern: get_env("KEY", "default").lower() == "true"
# Accepts: "true", "True", "TRUE". Does NOT accept: "1", "yes", "on".
ENABLE_CHECKPOINTS = get_env("ENABLE_CHECKPOINTS", "false").lower() == "true"
AUDIT_LOG_PATH = get_env("AUDIT_LOG", "./agent_audit.jsonl")

# v4.0 Feature flags — default true since v8.0, but still checked in main.py
# legacy mode. Kept for backwards compatibility with --legacy flag.
ENABLE_STACK_SELECTION = get_env("ENABLE_STACK_SELECTION", "true").lower() == "true"
ENABLE_DESIGN_REVIEW = get_env("ENABLE_DESIGN_REVIEW", "true").lower() == "true"
ENABLE_TEST_GENERATION = get_env("ENABLE_TEST_GENERATION", "true").lower() == "true"

# Iteration limits — controls how many retries each phase gets.
# Higher = more chances to recover, but more API cost and wall-clock time.
MAX_DESIGN_REVISIONS = int(get_env("MAX_DESIGN_REVISIONS", "2"))   # Design↔Review loop max
MAX_BUILD_ATTEMPTS = int(get_env("MAX_BUILD_ATTEMPTS", "5"))       # Builder retries with error injection
MAX_TEST_ATTEMPTS = int(get_env("MAX_TEST_ATTEMPTS", "3"))         # Test generation retries

# Test configuration — quality gate control
REQUIRE_PASSING_TESTS = get_env("REQUIRE_PASSING_TESTS", "true").lower() == "true"

# Legacy mode (v7.0 single-subprocess architecture — no phase orchestration)
LEGACY_MODE = get_env("LEGACY_MODE", "false").lower() == "true"

# v5.0 Feature flags
ENABLE_VERIFICATION = get_env("ENABLE_VERIFICATION", "true").lower() == "true"
ENABLE_PRE_DEPLOY_VALIDATION = get_env("ENABLE_PRE_DEPLOY_VALIDATION", "true").lower() == "true"
MAX_VERIFICATION_ATTEMPTS = int(get_env("MAX_VERIFICATION_ATTEMPTS", "2"))
ENABLE_DEPLOYMENT_COMPATIBILITY_CHECK = get_env("ENABLE_DEPLOYMENT_COMPATIBILITY_CHECK", "true").lower() == "true"

# v6.0 Feature flags
ENABLE_PROMPT_ENRICHMENT = get_env("ENABLE_PROMPT_ENRICHMENT", "false").lower() == "true"  # Opt-in: adds ~12s of research
ENABLE_SPEC_AUDIT = get_env("ENABLE_SPEC_AUDIT", "true").lower() == "true"
ENABLE_FUNCTIONAL_TESTS = get_env("ENABLE_FUNCTIONAL_TESTS", "true").lower() == "true"
PASS_ORIGINAL_PROMPT_TO_BUILDER = get_env("PASS_ORIGINAL_PROMPT_TO_BUILDER", "true").lower() == "true"
MAX_AUDIT_FIX_ATTEMPTS = int(get_env("MAX_AUDIT_FIX_ATTEMPTS", "1"))  # 1 = one fix attempt after audit findings

# v7.0: Swift/SwiftUI configuration — only needed for --stack swift-swiftui
APPLE_TEAM_ID = get_env("APPLE_TEAM_ID")
APPLE_DEVELOPER_EMAIL = get_env("APPLE_DEVELOPER_EMAIL")
SWIFT_MIN_TESTS_PLUGIN = int(get_env("SWIFT_MIN_TESTS_PLUGIN", "8"))   # Minimum tests for plugin builds
SWIFT_MIN_TESTS_HOST = int(get_env("SWIFT_MIN_TESTS_HOST", "15"))      # Minimum tests for host builds

# v9.0: Phase timeouts — prevents runaway SDK calls from hanging indefinitely.
# Build phase gets extra time because it does the most work (scaffolding + coding).
PHASE_TIMEOUT_S = int(get_env("PHASE_TIMEOUT_S", "600"))          # 10 min default for most phases
BUILD_PHASE_TIMEOUT_S = int(get_env("BUILD_PHASE_TIMEOUT_S", "900"))  # 15 min base for build phase
MAX_TOTAL_TURNS = int(get_env("MAX_TOTAL_TURNS", "300"))          # Global turn cap across ALL phases

# v12.0: Dynamic build timeout — extra seconds per table over 8.
# Complex apps (10+ tables) need more build time. The orchestrator calculates:
# effective_timeout = BUILD_PHASE_TIMEOUT_S + max(0, table_count - 8) * BUILD_TIMEOUT_PER_TABLE_S
# Example: 12 tables → 900 + 4*120 = 1380s (23 min)
BUILD_TIMEOUT_PER_TABLE_S = int(get_env("BUILD_TIMEOUT_PER_TABLE_S", "120"))

# v9.1: Crash recovery — verify artifact SHA-256 hashes on --resume
ENABLE_ARTIFACT_VERIFICATION = get_env("ENABLE_ARTIFACT_VERIFICATION", "true").lower() == "true"

# v12.4: Strict artifact verification — abort build if artifacts were modified
# since checkpoint. Enterprise hardening: prevents resuming from tampered state.
STRICT_ARTIFACT_VERIFICATION = get_env("STRICT_ARTIFACT_VERIFICATION", "false").lower() == "true"
