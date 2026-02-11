"""Tests for pre-deployment validation (v5.0)."""

import os
import pytest

from agent.validation import (
    ValidationResult,
    validate_env_vars,
    validate_database_connectivity,
    validate_deployment_compatibility,
    validate_sqlite_not_on_serverless,
    run_pre_deployment_validation,
    format_validation_report,
)


class TestValidateEnvVars:
    """Tests for environment variable validation."""

    def test_returns_passed_for_set_var(self, monkeypatch):
        """Test that set environment variables pass."""
        monkeypatch.setenv("TEST_VAR_123", "value")
        results = validate_env_vars(["TEST_VAR_123"])
        assert len(results) == 1
        assert results[0].passed is True
        assert "is set" in results[0].message

    def test_returns_failed_for_missing_var(self):
        """Test that missing environment variables fail."""
        results = validate_env_vars(["DEFINITELY_NOT_SET_XYZ_ABC_123"])
        assert len(results) == 1
        assert results[0].passed is False
        assert "not set" in results[0].message
        assert results[0].fix_suggestion is not None

    def test_multiple_vars(self, monkeypatch):
        """Test validation of multiple variables."""
        monkeypatch.setenv("VAR_A", "a")
        # VAR_B not set
        results = validate_env_vars(["VAR_A", "VAR_B_NOT_SET"])
        assert len(results) == 2
        assert results[0].passed is True
        assert results[1].passed is False


class TestValidateDatabaseConnectivity:
    """Tests for database connectivity validation."""

    def test_no_database_url_fails(self, monkeypatch):
        """Test that missing DATABASE_URL fails."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        result = validate_database_connectivity()
        assert result.passed is False
        assert "DATABASE_URL" in result.message

    def test_supabase_url_passes(self, monkeypatch):
        """Test that Supabase URLs are recognized."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.supabase.co:5432/postgres")
        result = validate_database_connectivity()
        assert result.passed is True
        assert "supabase" in result.message.lower()

    def test_neon_url_passes(self):
        """Test that Neon URLs are recognized."""
        result = validate_database_connectivity(
            database_url="postgresql://user:pass@ep-cool-name.neon.tech/neondb"
        )
        assert result.passed is True
        assert "neon" in result.message.lower()

    def test_sqlite_url_warns(self):
        """Test that SQLite URLs pass but warn."""
        result = validate_database_connectivity(
            database_url="file:./dev.db",
            database_type="sqlite"
        )
        assert result.passed is True
        assert "sqlite" in result.message.lower()
        assert result.fix_suggestion is not None


class TestValidateDeploymentCompatibility:
    """Tests for stack/deployment compatibility validation."""

    def test_sqlite_vercel_is_incompatible(self):
        """Test that SQLite + Vercel is blocked."""
        result = validate_deployment_compatibility(
            stack_id="nextjs-prisma",
            deployment_target="vercel",
            database_type="sqlite"
        )
        assert result.passed is False
        assert "incompatible" in result.message.lower()

    def test_postgresql_vercel_is_compatible(self):
        """Test that PostgreSQL + Vercel is allowed."""
        result = validate_deployment_compatibility(
            stack_id="nextjs-supabase",
            deployment_target="vercel",
            database_type="postgresql"
        )
        assert result.passed is True

    def test_sqlite_railway_is_compatible(self):
        """Test that SQLite + Railway is allowed."""
        result = validate_deployment_compatibility(
            stack_id="rails",
            deployment_target="railway",
            database_type="sqlite"
        )
        assert result.passed is True


class TestValidateSqliteNotOnServerless:
    """Tests for the SQLite/serverless check."""

    def test_sqlite_on_vercel_fails(self):
        """Test that SQLite + Vercel is blocked."""
        result = validate_sqlite_not_on_serverless("sqlite", "vercel")
        assert result.passed is False
        assert "CRITICAL" in result.message

    def test_sqlite_on_netlify_fails(self):
        """Test that SQLite + Netlify is blocked."""
        result = validate_sqlite_not_on_serverless("sqlite", "netlify")
        assert result.passed is False

    def test_sqlite_on_railway_passes(self):
        """Test that SQLite + Railway is allowed."""
        result = validate_sqlite_not_on_serverless("sqlite", "railway")
        assert result.passed is True

    def test_postgresql_on_vercel_passes(self):
        """Test that PostgreSQL + Vercel is allowed."""
        result = validate_sqlite_not_on_serverless("postgresql", "vercel")
        assert result.passed is True

    def test_no_database_type_skips(self):
        """Test that no database type skips the check."""
        result = validate_sqlite_not_on_serverless(None, "vercel")
        assert result.passed is True
        assert "skipping" in result.message.lower()


class TestRunPreDeploymentValidation:
    """Tests for the combined validation function."""

    def test_compatible_config_passes(self, monkeypatch):
        """Test that a compatible configuration passes all checks."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        passed, results = run_pre_deployment_validation(
            stack_id="nextjs-supabase",
            deployment_target="vercel",
            database_type="postgresql",
            required_env_vars=["DATABASE_URL"],
        )
        assert passed is True
        assert all(r.passed for r in results)

    def test_sqlite_on_vercel_fails_validation(self):
        """Test that SQLite + Vercel fails validation."""
        passed, results = run_pre_deployment_validation(
            stack_id="nextjs-prisma",
            deployment_target="vercel",
            database_type="sqlite",
        )
        assert passed is False
        failed = [r for r in results if not r.passed]
        assert len(failed) > 0


class TestFormatValidationReport:
    """Tests for the validation report formatter."""

    def test_all_passed_shows_ready(self):
        """Test that all passed shows READY status."""
        results = [
            ValidationResult(True, "check1", "All good"),
            ValidationResult(True, "check2", "Also good"),
        ]
        report = format_validation_report(results)
        assert "READY" in report
        assert "check1" in report
        assert "check2" in report

    def test_failures_show_blocked(self):
        """Test that failures show BLOCKED status."""
        results = [
            ValidationResult(True, "check1", "Good"),
            ValidationResult(False, "check2", "Bad", "Fix it"),
        ]
        report = format_validation_report(results)
        assert "BLOCKED" in report
        assert "check2" in report
        assert "Fix it" in report

    def test_report_is_markdown(self):
        """Test that report is valid markdown."""
        results = [ValidationResult(True, "test", "message")]
        report = format_validation_report(results)
        assert report.startswith("#")
        assert "##" in report
