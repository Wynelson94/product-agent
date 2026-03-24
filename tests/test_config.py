"""Tests for agent/config.py — configuration and environment variables."""

import os
import pytest
from unittest.mock import patch


class TestGetEnv:

    def test_returns_env_var_when_set(self):
        from agent.config import get_env
        with patch.dict(os.environ, {"TEST_VAR": "hello"}):
            assert get_env("TEST_VAR") == "hello"

    def test_returns_default_when_not_set(self):
        from agent.config import get_env
        with patch.dict(os.environ, {}, clear=True):
            assert get_env("NONEXISTENT_VAR", "fallback") == "fallback"

    def test_returns_none_when_not_set_no_default(self):
        from agent.config import get_env
        with patch.dict(os.environ, {}, clear=True):
            assert get_env("NONEXISTENT_VAR") is None


class TestRequireEnv:

    def test_returns_value_when_set(self):
        from agent.config import require_env
        with patch.dict(os.environ, {"REQUIRED_VAR": "value123"}):
            assert require_env("REQUIRED_VAR") == "value123"

    def test_raises_when_not_set(self):
        from agent.config import require_env
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="REQUIRED_VAR"):
                require_env("REQUIRED_VAR")

    def test_raises_when_empty_string(self):
        from agent.config import require_env
        with patch.dict(os.environ, {"REQUIRED_VAR": ""}):
            with pytest.raises(ValueError, match="REQUIRED_VAR"):
                require_env("REQUIRED_VAR")


class TestFeatureFlags:
    """Test that feature flags parse boolean env vars correctly."""

    def test_boolean_flag_true(self):
        from agent.config import get_env
        with patch.dict(os.environ, {"MY_FLAG": "true"}):
            assert get_env("MY_FLAG", "false").lower() == "true"

    def test_boolean_flag_false(self):
        from agent.config import get_env
        with patch.dict(os.environ, {"MY_FLAG": "false"}):
            assert get_env("MY_FLAG", "true").lower() != "true"

    def test_boolean_flag_case_insensitive(self):
        from agent.config import get_env
        with patch.dict(os.environ, {"MY_FLAG": "TRUE"}):
            assert get_env("MY_FLAG", "false").lower() == "true"

    def test_default_project_dir_is_path(self):
        from agent.config import DEFAULT_PROJECT_DIR
        from pathlib import Path
        assert isinstance(DEFAULT_PROJECT_DIR, Path)

    def test_max_turns_is_int(self):
        from agent.config import MAX_TURNS
        assert isinstance(MAX_TURNS, int)
        assert MAX_TURNS > 0

    def test_default_model_is_string(self):
        from agent.config import DEFAULT_MODEL
        assert isinstance(DEFAULT_MODEL, str)
        assert len(DEFAULT_MODEL) > 0


class TestIntegerConfigs:
    """Test that integer configs parse correctly and have sane defaults."""

    def test_max_design_revisions_default(self):
        from agent.config import MAX_DESIGN_REVISIONS
        assert isinstance(MAX_DESIGN_REVISIONS, int)
        assert MAX_DESIGN_REVISIONS >= 1

    def test_max_build_attempts_default(self):
        from agent.config import MAX_BUILD_ATTEMPTS
        assert isinstance(MAX_BUILD_ATTEMPTS, int)
        assert MAX_BUILD_ATTEMPTS >= 1

    def test_max_test_attempts_default(self):
        from agent.config import MAX_TEST_ATTEMPTS
        assert isinstance(MAX_TEST_ATTEMPTS, int)
        assert MAX_TEST_ATTEMPTS >= 1

    def test_phase_timeout_default(self):
        from agent.config import PHASE_TIMEOUT_S
        assert isinstance(PHASE_TIMEOUT_S, int)
        assert PHASE_TIMEOUT_S >= 60  # At least 1 minute

    def test_build_phase_timeout_default(self):
        from agent.config import BUILD_PHASE_TIMEOUT_S, PHASE_TIMEOUT_S
        assert isinstance(BUILD_PHASE_TIMEOUT_S, int)
        assert BUILD_PHASE_TIMEOUT_S >= PHASE_TIMEOUT_S  # Build should be >= default

    def test_max_total_turns_default(self):
        from agent.config import MAX_TOTAL_TURNS
        assert isinstance(MAX_TOTAL_TURNS, int)
        assert MAX_TOTAL_TURNS >= 100

    def test_max_verification_attempts_default(self):
        from agent.config import MAX_VERIFICATION_ATTEMPTS
        assert isinstance(MAX_VERIFICATION_ATTEMPTS, int)
        assert MAX_VERIFICATION_ATTEMPTS >= 1

    def test_max_audit_fix_attempts_default(self):
        from agent.config import MAX_AUDIT_FIX_ATTEMPTS
        assert isinstance(MAX_AUDIT_FIX_ATTEMPTS, int)
        assert MAX_AUDIT_FIX_ATTEMPTS >= 1


class TestV4Flags:
    """v4.0 feature flags default to true but are still used in legacy mode."""

    def test_stack_selection_default_true(self):
        from agent.config import ENABLE_STACK_SELECTION
        assert ENABLE_STACK_SELECTION is True

    def test_design_review_default_true(self):
        from agent.config import ENABLE_DESIGN_REVIEW
        assert ENABLE_DESIGN_REVIEW is True

    def test_test_generation_default_true(self):
        from agent.config import ENABLE_TEST_GENERATION
        assert ENABLE_TEST_GENERATION is True


class TestV5Flags:

    def test_verification_default_true(self):
        from agent.config import ENABLE_VERIFICATION
        assert ENABLE_VERIFICATION is True

    def test_pre_deploy_validation_default_true(self):
        from agent.config import ENABLE_PRE_DEPLOY_VALIDATION
        assert ENABLE_PRE_DEPLOY_VALIDATION is True

    def test_deployment_compatibility_check_default_true(self):
        from agent.config import ENABLE_DEPLOYMENT_COMPATIBILITY_CHECK
        assert ENABLE_DEPLOYMENT_COMPATIBILITY_CHECK is True


class TestV6Flags:

    def test_prompt_enrichment_default_false(self):
        # Opt-in: enrichment is disabled by default
        from agent.config import ENABLE_PROMPT_ENRICHMENT
        assert ENABLE_PROMPT_ENRICHMENT is False

    def test_spec_audit_default_true(self):
        from agent.config import ENABLE_SPEC_AUDIT
        assert ENABLE_SPEC_AUDIT is True

    def test_functional_tests_default_true(self):
        from agent.config import ENABLE_FUNCTIONAL_TESTS
        assert ENABLE_FUNCTIONAL_TESTS is True

    def test_pass_original_prompt_default_true(self):
        from agent.config import PASS_ORIGINAL_PROMPT_TO_BUILDER
        assert PASS_ORIGINAL_PROMPT_TO_BUILDER is True


class TestV9Flags:

    def test_checkpoints_default_false(self):
        from agent.config import ENABLE_CHECKPOINTS
        assert ENABLE_CHECKPOINTS is False

    def test_artifact_verification_default_true(self):
        from agent.config import ENABLE_ARTIFACT_VERIFICATION
        assert ENABLE_ARTIFACT_VERIFICATION is True

    def test_legacy_mode_default_false(self):
        from agent.config import LEGACY_MODE
        assert LEGACY_MODE is False
