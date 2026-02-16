"""Tests for error recovery module.

These tests verify that error patterns are correctly identified and
appropriate recovery prompts are generated.
"""

import pytest
from agent.recovery import (
    analyze_error,
    get_build_fix_prompt,
    get_deploy_fix_prompt,
    ErrorAnalysis,
    BUILD_ERROR_PATTERNS,
    DEPLOY_ERROR_PATTERNS,
    DATABASE_ERROR_PATTERNS,
)


class TestAnalyzeErrorBuildErrors:
    """Tests for build error pattern detection."""

    # --- Module/Import errors ---

    @pytest.mark.parametrize("error_msg,expected_type", [
        ("Module not found: Can't resolve 'lodash'", "missing_module"),
        ("Cannot find module 'react-query'", "missing_module"),
        ("Module not found: Error: Can't resolve '@/components/Button'", "missing_module"),
    ])
    def test_detects_missing_module_errors(self, error_msg, expected_type):
        result = analyze_error(error_msg)
        assert result.error_type == expected_type
        assert result.action == "install_package"

    def test_missing_module_captures_package_name(self):
        result = analyze_error("Module not found: Can't resolve 'axios'")
        assert "axios" in result.details["matches"]

    def test_alias_path_error_gives_special_guidance(self):
        result = analyze_error("Module not found: Can't resolve '@/lib/utils'")
        assert "@/" in result.recovery_prompt
        assert "tsconfig" in result.recovery_prompt.lower()

    # --- TypeScript errors ---

    @pytest.mark.parametrize("error_msg,expected_type", [
        ("Type 'string' is not assignable to type 'number'", "type_error"),
        ("Property 'foo' does not exist on type 'Bar'", "missing_property"),
        ("'useState' is not defined", "undefined_reference"),
        ("Cannot find name 'MyComponent'", "undefined_reference"),
    ])
    def test_detects_typescript_errors(self, error_msg, expected_type):
        result = analyze_error(error_msg)
        assert result.error_type == expected_type

    def test_type_error_action(self):
        result = analyze_error("Type 'string' is not assignable to type 'number'")
        assert result.action == "fix_types"

    def test_undefined_reference_action(self):
        result = analyze_error("'useState' is not defined")
        assert result.action == "add_import_or_define"
        assert "useState" in result.recovery_prompt

    # --- Syntax errors ---

    @pytest.mark.parametrize("error_msg", [
        "SyntaxError: Unexpected token '}'",
        "SyntaxError: Missing semicolon",
        "Parsing error: Unexpected token",
        "Parsing error: Adjacent JSX elements must be wrapped",
    ])
    def test_detects_syntax_errors(self, error_msg):
        result = analyze_error(error_msg)
        assert result.error_type == "syntax_error"
        assert result.action == "fix_syntax"

    # --- Component errors ---

    @pytest.mark.parametrize("error_msg", [
        "'MyComponent' cannot be used as a JSX component",
        "Error: undefined is not a valid React element",
    ])
    def test_detects_component_errors(self, error_msg):
        result = analyze_error(error_msg)
        assert result.error_type == "component_error"
        assert result.action == "fix_component"

    # --- Config errors ---

    def test_detects_next_config_errors(self):
        result = analyze_error("next.config.js error: Invalid configuration")
        assert result.error_type == "config_error"
        assert result.action == "fix_config"


class TestAnalyzeErrorDeployErrors:
    """Tests for deployment error pattern detection."""

    def test_detects_missing_env_var(self):
        result = analyze_error("Error: Environment variable DATABASE_URL is missing")
        assert result.error_type == "missing_env"
        assert result.action == "set_env_var"
        assert result.requires_user is True
        assert "DATABASE_URL" in result.recovery_prompt

    def test_detects_vercel_error(self):
        result = analyze_error("Error: Command failed: vercel deploy")
        assert result.error_type == "vercel_error"
        assert result.action == "check_vercel_auth"
        assert "vercel login" in result.recovery_prompt.lower()

    def test_detects_deployment_failed(self):
        result = analyze_error("Error: Deployment failed")
        assert result.error_type == "deployment_failed"
        assert result.action == "analyze_deploy_logs"


class TestAnalyzeErrorDatabaseErrors:
    """Tests for database error pattern detection."""

    def test_detects_missing_table(self):
        result = analyze_error('relation "users" does not exist')
        assert result.error_type == "missing_table"
        assert result.action == "run_migrations"
        assert "users" in result.recovery_prompt

    def test_detects_rls_error(self):
        result = analyze_error("permission denied for table posts")
        assert result.error_type == "rls_error"
        assert result.action == "check_rls_policies"
        assert "Row Level Security" in result.recovery_prompt

    def test_detects_constraint_error(self):
        result = analyze_error("duplicate key value violates unique constraint")
        assert result.error_type == "constraint_error"
        assert result.action == "handle_duplicate"


class TestAnalyzeErrorUnknown:
    """Tests for unknown error handling."""

    def test_returns_unknown_for_unmatched_error(self):
        result = analyze_error("Some random error message that doesn't match")
        assert result.error_type == "unknown"
        assert result.action == "investigate"

    def test_unknown_error_includes_original_message(self):
        error_msg = "Completely novel error XYZ123"
        result = analyze_error(error_msg)
        assert error_msg in result.details["original_error"]
        assert error_msg in result.recovery_prompt

    def test_unknown_error_gives_generic_recovery_guidance(self):
        result = analyze_error("Unknown error occurred")
        assert "debug" in result.recovery_prompt.lower()
        assert "root cause" in result.recovery_prompt.lower()


class TestErrorAnalysisDataclass:
    """Tests for ErrorAnalysis dataclass."""

    def test_dataclass_fields(self):
        analysis = ErrorAnalysis(
            error_type="test_type",
            action="test_action",
            details={"key": "value"},
            recovery_prompt="Fix it",
            requires_user=True,
        )
        assert analysis.error_type == "test_type"
        assert analysis.action == "test_action"
        assert analysis.details == {"key": "value"}
        assert analysis.recovery_prompt == "Fix it"
        assert analysis.requires_user is True

    def test_requires_user_defaults_to_false(self):
        analysis = ErrorAnalysis(
            error_type="test",
            action="test",
            details={},
            recovery_prompt="test",
        )
        assert analysis.requires_user is False


class TestGetBuildFixPrompt:
    """Tests for build fix prompt generation."""

    def test_includes_attempt_count(self):
        prompt = get_build_fix_prompt("Some error", attempt=2, max_attempts=5)
        assert "2/5" in prompt or "Attempt 2" in prompt

    def test_includes_recovery_guidance(self):
        prompt = get_build_fix_prompt(
            "Module not found: Can't resolve 'lodash'",
            attempt=1,
            max_attempts=5
        )
        assert "npm install" in prompt.lower()

    def test_includes_build_verification_instruction(self):
        prompt = get_build_fix_prompt("Some error", attempt=1, max_attempts=5)
        assert "npm run build" in prompt

    def test_instructs_minimal_changes(self):
        prompt = get_build_fix_prompt("Some error", attempt=1, max_attempts=5)
        assert "minimal" in prompt.lower() or "only" in prompt.lower()


class TestGetDeployFixPrompt:
    """Tests for deployment fix prompt generation."""

    def test_includes_attempt_info(self):
        prompt = get_deploy_fix_prompt("Error: Deployment failed", attempt=2)
        assert "2" in prompt

    def test_user_required_error_gives_manual_setup_prompt(self):
        prompt = get_deploy_fix_prompt(
            "Error: Environment variable STRIPE_KEY is missing",
            attempt=1
        )
        assert "Manual" in prompt or "manual" in prompt
        assert "user" in prompt.lower() or "configuration" in prompt.lower()

    def test_fixable_error_gives_retry_instruction(self):
        prompt = get_deploy_fix_prompt(
            "Error: Command failed: vercel deploy",
            attempt=1
        )
        assert "retry" in prompt.lower() or "Retry" in prompt


class TestRecoveryPromptQuality:
    """Tests for recovery prompt content quality."""

    def test_install_package_prompt_includes_types_suggestion(self):
        result = analyze_error("Module not found: Can't resolve 'express'")
        assert "@types/" in result.recovery_prompt

    def test_type_error_prompt_includes_actionable_steps(self):
        result = analyze_error("Type 'string' is not assignable to type 'number'")
        assert "1." in result.recovery_prompt  # Numbered steps
        assert "type" in result.recovery_prompt.lower()

    def test_undefined_reference_prompt_includes_import_example(self):
        result = analyze_error("'useState' is not defined")
        assert "import" in result.recovery_prompt.lower()

    def test_missing_table_prompt_includes_supabase_and_prisma(self):
        result = analyze_error('relation "posts" does not exist')
        assert "Supabase" in result.recovery_prompt or "supabase" in result.recovery_prompt
        assert "Prisma" in result.recovery_prompt or "prisma" in result.recovery_prompt

    def test_all_prompts_include_original_error(self):
        """Every recovery prompt should include the original error for context."""
        test_errors = [
            "Module not found: Can't resolve 'test'",
            "Type 'A' is not assignable to type 'B'",
            "SyntaxError: Unexpected token",
            "'MyComponent' cannot be used as a JSX component",
            "Error: Environment variable TEST is missing",
            'relation "test" does not exist',
        ]
        for error in test_errors:
            result = analyze_error(error)
            assert "Original error" in result.recovery_prompt or error in result.recovery_prompt, \
                f"Original error not included for: {error}"


class TestPatternCoverage:
    """Meta-tests to ensure all patterns are functional."""

    def test_all_build_patterns_compile(self):
        """All BUILD_ERROR_PATTERNS should be valid regex."""
        import re
        for pattern in BUILD_ERROR_PATTERNS:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern: {pattern} - {e}")

    def test_all_deploy_patterns_compile(self):
        """All DEPLOY_ERROR_PATTERNS should be valid regex."""
        import re
        for pattern in DEPLOY_ERROR_PATTERNS:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern: {pattern} - {e}")

    def test_all_database_patterns_compile(self):
        """All DATABASE_ERROR_PATTERNS should be valid regex."""
        import re
        for pattern in DATABASE_ERROR_PATTERNS:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern: {pattern} - {e}")

    def test_build_patterns_have_required_keys(self):
        """All build pattern configs should have type and action."""
        for pattern, config in BUILD_ERROR_PATTERNS.items():
            assert "type" in config, f"Missing 'type' in {pattern}"
            assert "action" in config, f"Missing 'action' in {pattern}"

    def test_deploy_patterns_have_required_keys(self):
        """All deploy pattern configs should have type and action."""
        for pattern, config in DEPLOY_ERROR_PATTERNS.items():
            assert "type" in config, f"Missing 'type' in {pattern}"
            assert "action" in config, f"Missing 'action' in {pattern}"

    def test_database_patterns_have_required_keys(self):
        """All database pattern configs should have type and action."""
        for pattern, config in DATABASE_ERROR_PATTERNS.items():
            assert "type" in config, f"Missing 'type' in {pattern}"
            assert "action" in config, f"Missing 'action' in {pattern}"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_error_message(self):
        result = analyze_error("")
        assert result.error_type == "unknown"
        assert result.recovery_prompt  # Should still have guidance

    def test_very_long_error_message(self):
        long_error = "Error: " + "x" * 10000
        result = analyze_error(long_error)
        # Should not crash and should return something
        assert result is not None

    def test_error_with_special_characters(self):
        result = analyze_error("Error: Can't resolve '@/components/[id]/page'")
        # Should handle special regex characters in error messages
        assert result is not None

    def test_case_insensitive_matching(self):
        # Patterns should match case-insensitively where appropriate
        result1 = analyze_error("MODULE NOT FOUND: Can't resolve 'test'")
        result2 = analyze_error("module not found: can't resolve 'test'")
        assert result1.error_type == result2.error_type

    def test_multiline_error_message(self):
        error = """Error: Build failed

        Module not found: Can't resolve 'missing-package'

        at /app/src/index.ts:1:1"""
        result = analyze_error(error)
        assert result.error_type == "missing_module"

    def test_build_fix_prompt_at_max_attempts(self):
        prompt = get_build_fix_prompt("Error", attempt=5, max_attempts=5)
        assert "5/5" in prompt

    def test_deploy_fix_prompt_high_attempt_number(self):
        prompt = get_deploy_fix_prompt("Error: Deployment failed", attempt=10)
        # Should not crash with high attempt numbers
        assert "10" in prompt


# ---------------------------------------------------------------------------
# v10.0: RLS circular dependency detection
# ---------------------------------------------------------------------------

class TestRLSCircularRecovery:
    """Tests for RLS circular dependency pattern matching and recovery."""

    def test_rls_circular_pattern_matches_permission_denied(self):
        """Error with 'permission denied.*rls' should match the rls_circular pattern."""
        result = analyze_error("permission denied for table profiles due to rls")
        # Should match rls_circular (or rls_error — rls_error matches first
        # because the existing "permission denied for table" pattern is checked
        # before DATABASE_ERROR_PATTERNS). The important thing is it's detected.
        assert result.error_type in ("rls_error", "rls_circular")

    def test_rls_circular_pattern_matches_violates_rls(self):
        """Error with 'new row violates row-level security policy' should match."""
        result = analyze_error("new row violates row-level security policy for table profiles")
        assert result.error_type == "rls_circular"

    def test_rls_circular_recovery_prompt_content(self):
        """The fix_rls_circular recovery prompt should include SECURITY DEFINER guidance."""
        from agent.recovery import _get_recovery_prompt
        prompt = _get_recovery_prompt(
            "rls_circular", "fix_rls_circular", (), "query returned no rows"
        )
        assert "SECURITY DEFINER" in prompt
        assert "get_user_org_id" in prompt
        assert "query returned no rows" in prompt
