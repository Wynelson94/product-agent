"""Configuration and environment variables."""

import os
from pathlib import Path


def get_env(key: str, default: str | None = None) -> str | None:
    """Get environment variable with optional default."""
    return os.environ.get(key, default)


def require_env(key: str) -> str:
    """Get required environment variable, raise if missing."""
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value


# API Keys
ANTHROPIC_API_KEY = get_env("ANTHROPIC_API_KEY")
GITHUB_TOKEN = get_env("GITHUB_TOKEN")
SUPABASE_ACCESS_TOKEN = get_env("SUPABASE_ACCESS_TOKEN")
VERCEL_TOKEN = get_env("VERCEL_TOKEN")

# Defaults
DEFAULT_PROJECT_DIR = Path("./projects/new")
DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_TURNS = 200

# Feature flags
ENABLE_CHECKPOINTS = get_env("ENABLE_CHECKPOINTS", "false").lower() == "true"
AUDIT_LOG_PATH = get_env("AUDIT_LOG", "./agent_audit.jsonl")

# v4.0 Feature flags
ENABLE_STACK_SELECTION = get_env("ENABLE_STACK_SELECTION", "true").lower() == "true"
ENABLE_DESIGN_REVIEW = get_env("ENABLE_DESIGN_REVIEW", "true").lower() == "true"
ENABLE_TEST_GENERATION = get_env("ENABLE_TEST_GENERATION", "true").lower() == "true"

# Iteration limits
MAX_DESIGN_REVISIONS = int(get_env("MAX_DESIGN_REVISIONS", "2"))
MAX_BUILD_ATTEMPTS = int(get_env("MAX_BUILD_ATTEMPTS", "5"))
MAX_TEST_ATTEMPTS = int(get_env("MAX_TEST_ATTEMPTS", "3"))

# Test configuration
REQUIRE_PASSING_TESTS = get_env("REQUIRE_PASSING_TESTS", "true").lower() == "true"

# Legacy mode (disables all v4.0 features)
LEGACY_MODE = get_env("LEGACY_MODE", "false").lower() == "true"

# v5.0 Feature flags
ENABLE_VERIFICATION = get_env("ENABLE_VERIFICATION", "true").lower() == "true"
ENABLE_PRE_DEPLOY_VALIDATION = get_env("ENABLE_PRE_DEPLOY_VALIDATION", "true").lower() == "true"
MAX_VERIFICATION_ATTEMPTS = int(get_env("MAX_VERIFICATION_ATTEMPTS", "2"))
ENABLE_DEPLOYMENT_COMPATIBILITY_CHECK = get_env("ENABLE_DEPLOYMENT_COMPATIBILITY_CHECK", "true").lower() == "true"

# v6.0 Feature flags
ENABLE_PROMPT_ENRICHMENT = get_env("ENABLE_PROMPT_ENRICHMENT", "false").lower() == "true"  # opt-in
ENABLE_SPEC_AUDIT = get_env("ENABLE_SPEC_AUDIT", "true").lower() == "true"  # on by default
ENABLE_FUNCTIONAL_TESTS = get_env("ENABLE_FUNCTIONAL_TESTS", "true").lower() == "true"
PASS_ORIGINAL_PROMPT_TO_BUILDER = get_env("PASS_ORIGINAL_PROMPT_TO_BUILDER", "true").lower() == "true"
MAX_AUDIT_FIX_ATTEMPTS = int(get_env("MAX_AUDIT_FIX_ATTEMPTS", "1"))

# v7.0: Swift/SwiftUI configuration
APPLE_TEAM_ID = get_env("APPLE_TEAM_ID")
APPLE_DEVELOPER_EMAIL = get_env("APPLE_DEVELOPER_EMAIL")
SWIFT_MIN_TESTS_PLUGIN = int(get_env("SWIFT_MIN_TESTS_PLUGIN", "8"))
SWIFT_MIN_TESTS_HOST = int(get_env("SWIFT_MIN_TESTS_HOST", "15"))

# v9.0: Phase timeouts (seconds)
PHASE_TIMEOUT_S = int(get_env("PHASE_TIMEOUT_S", "600"))  # 10 min default
BUILD_PHASE_TIMEOUT_S = int(get_env("BUILD_PHASE_TIMEOUT_S", "900"))  # 15 min for build
MAX_TOTAL_TURNS = int(get_env("MAX_TOTAL_TURNS", "300"))  # Total turns across entire build
