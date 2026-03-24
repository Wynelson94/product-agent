"""Level 1: Validator stress tests — no SDK calls, instant execution.

Tests every extraction path in validators.py with controlled inputs.
Each test feeds a specific artifact format and verifies the validator
extracts the correct data. Covers YAML front-matter, regex fallbacks,
keyword matching, and edge cases.
"""

import pytest
from pathlib import Path

from agent.state import Phase
from agent.validators import validate_phase_output, validate_build_routes

from .conftest import load_fixture, populate_project


# =====================================================================
# Analysis Validator
# =====================================================================


class TestAnalysisValidator:
    """Validates _validate_analysis extracts stack_id correctly."""

    def test_yaml_frontmatter_prisma(self, tmp_path):
        """YAML front-matter with stack_id should extract cleanly."""
        (tmp_path / "STACK_DECISION.md").write_text(
            "---\nstack_id: nextjs-prisma\n---\n# Stack Decision\n"
        )
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert result.passed
        assert result.extracted["stack_id"] == "nextjs-prisma"

    def test_yaml_frontmatter_supabase(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text(
            "---\nstack_id: nextjs-supabase\n---\n# Stack Decision\n"
        )
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert result.passed
        assert result.extracted["stack_id"] == "nextjs-supabase"

    def test_yaml_frontmatter_django(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text(
            "---\nstack_id: django-htmx\n---\n# Stack Decision\n"
        )
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert result.passed
        assert result.extracted["stack_id"] == "django-htmx"

    def test_yaml_frontmatter_sveltekit(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text(
            "---\nstack_id: sveltekit\n---\n# Stack Decision\n"
        )
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert result.passed
        assert result.extracted["stack_id"] == "sveltekit"

    def test_yaml_frontmatter_astro(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text(
            "---\nstack_id: astro\n---\n# Stack Decision\n"
        )
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert result.passed
        assert result.extracted["stack_id"] == "astro"

    def test_regex_fallback_bold_format(self, tmp_path):
        """Fallback: **Stack ID**: `nextjs-prisma` format."""
        (tmp_path / "STACK_DECISION.md").write_text(
            "# Stack Decision\n\n**Stack ID**: `nextjs-prisma`\n"
        )
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert result.passed
        assert result.extracted["stack_id"] == "nextjs-prisma"

    def test_substring_fallback(self, tmp_path):
        """Fallback: stack name mentioned anywhere in text."""
        (tmp_path / "STACK_DECISION.md").write_text(
            "# Decision\nWe chose the rails stack for this project.\n"
        )
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert result.passed
        assert result.extracted["stack_id"] == "rails"

    def test_missing_file_fails(self, tmp_path):
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert not result.passed

    def test_no_stack_id_fails(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text("# Empty decision\nNo stack chosen.\n")
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert not result.passed

    def test_real_fixture_prisma(self, tmp_path):
        """Test with actual stress test output."""
        content = load_fixture("analysis/stack_decision_prisma.md")
        (tmp_path / "STACK_DECISION.md").write_text(content)
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert result.passed
        assert result.extracted["stack_id"] == "nextjs-prisma"

    def test_real_fixture_supabase(self, tmp_path):
        content = load_fixture("analysis/stack_decision_supabase.md")
        (tmp_path / "STACK_DECISION.md").write_text(content)
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert result.passed
        assert result.extracted["stack_id"] == "nextjs-supabase"


# =====================================================================
# Design Validator
# =====================================================================


class TestDesignValidator:
    """Validates _validate_design checks DESIGN.md structure."""

    def test_valid_design_passes(self, tmp_path):
        content = "# Design\n" + "x " * 200 + "\n## Data Model\n## Routes\n## Auth\n"
        (tmp_path / "DESIGN.md").write_text(content)
        result = validate_phase_output(Phase.DESIGN, tmp_path)
        assert result.passed

    def test_short_design_fails(self, tmp_path):
        (tmp_path / "DESIGN.md").write_text("# Design\nToo short.")
        result = validate_phase_output(Phase.DESIGN, tmp_path)
        assert not result.passed

    def test_missing_design_fails(self, tmp_path):
        result = validate_phase_output(Phase.DESIGN, tmp_path)
        assert not result.passed

    def test_real_fixture_proserv(self, tmp_path):
        """Test with actual stress test design output (997 lines)."""
        content = load_fixture("design/design_proserv.md")
        (tmp_path / "DESIGN.md").write_text(content)
        result = validate_phase_output(Phase.DESIGN, tmp_path)
        assert result.passed


# =====================================================================
# Review Validator
# =====================================================================


class TestReviewValidator:
    """Validates _validate_review extracts approval status."""

    def test_yaml_approved(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text(
            "---\nverdict: approved\n---\n# Review\nAll good.\n"
        )
        result = validate_phase_output(Phase.REVIEW, tmp_path)
        assert result.passed
        assert result.extracted.get("approved") is True

    def test_yaml_needs_revision(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text(
            "---\nverdict: needs_revision\n---\n# Review\nFix the auth flow.\n"
        )
        result = validate_phase_output(Phase.REVIEW, tmp_path)
        assert result.extracted.get("approved") is False

    def test_keyword_approved(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text("# Review\n\n## Status: APPROVED\n")
        result = validate_phase_output(Phase.REVIEW, tmp_path)
        assert result.extracted.get("approved") is True

    def test_keyword_needs_revision(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text("# Review\n\n## Status: NEEDS_REVISION\n")
        result = validate_phase_output(Phase.REVIEW, tmp_path)
        assert result.extracted.get("approved") is False

    def test_real_fixture_approved(self, tmp_path):
        content = load_fixture("review/review_approved.md")
        (tmp_path / "REVIEW.md").write_text(content)
        result = validate_phase_output(Phase.REVIEW, tmp_path)
        assert result.extracted.get("approved") is True

    def test_real_fixture_needs_revision(self, tmp_path):
        content = load_fixture("review/review_needs_revision.md")
        (tmp_path / "REVIEW.md").write_text(content)
        result = validate_phase_output(Phase.REVIEW, tmp_path)
        assert result.extracted.get("approved") is False


# =====================================================================
# Enhance Validator
# =====================================================================


class TestEnhanceValidator:
    """Validates _validate_enhance checks for (NEW) markers."""

    def test_with_new_markers(self, tmp_path):
        content = "# Design\n" + "x " * 200 + "\n## Feature (NEW)\nNew stuff."
        (tmp_path / "DESIGN.md").write_text(content)
        result = validate_phase_output(Phase.ENHANCE, tmp_path)
        assert result.passed
        assert result.extracted.get("new_items", 0) >= 1

    def test_multiple_new_markers(self, tmp_path):
        content = "# Design\n" + "x " * 200
        content += "\n## A (NEW)\n## B (NEW)\n## C (NEW)\n## D (NEW)\n## E (NEW)"
        (tmp_path / "DESIGN.md").write_text(content)
        result = validate_phase_output(Phase.ENHANCE, tmp_path)
        assert result.extracted.get("new_items") == 5

    def test_without_markers_warns(self, tmp_path):
        content = "# Design\n" + "x " * 200 + "\nPlain content."
        (tmp_path / "DESIGN.md").write_text(content)
        result = validate_phase_output(Phase.ENHANCE, tmp_path)
        assert result.passed  # Passes but warns


# =====================================================================
# Build Validator
# =====================================================================


class TestBuildValidator:
    """Validates _validate_build checks for source code."""

    def test_nextjs_structure_passes(self, tmp_path):
        src = tmp_path / "src" / "app"
        src.mkdir(parents=True)
        (src / "page.tsx").write_text("export default function Home() { return <h1>Hi</h1> }")
        (tmp_path / "package.json").write_text('{"name": "test"}')
        result = validate_phase_output(Phase.BUILD, tmp_path)
        assert result.passed

    def test_empty_project_fails(self, tmp_path):
        result = validate_phase_output(Phase.BUILD, tmp_path)
        assert not result.passed

    def test_swift_structure_passes(self, tmp_path):
        sources = tmp_path / "Sources" / "MyPlugin"
        sources.mkdir(parents=True)
        (sources / "Plugin.swift").write_text("import SwiftUI\nstruct MyPlugin {}")
        (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9")
        result = validate_phase_output(Phase.BUILD, tmp_path)
        assert result.passed

    def test_django_structure_passes(self, tmp_path):
        app = tmp_path / "src" / "core"
        app.mkdir(parents=True)
        (app / "views.py").write_text("from django.shortcuts import render")
        result = validate_phase_output(Phase.BUILD, tmp_path)
        assert result.passed


# =====================================================================
# Audit Validator
# =====================================================================


class TestAuditValidator:
    """Validates _validate_audit extracts requirements and CRITICAL counts."""

    def test_yaml_pass(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text(
            "---\nstatus: pass\nrequirements_met: 12\nrequirements_total: 12\n---\n# Audit\nAll good."
        )
        result = validate_phase_output(Phase.AUDIT, tmp_path)
        assert result.passed
        assert result.extracted.get("requirements_met") == 12

    def test_yaml_fail(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text(
            "---\nstatus: fail\nrequirements_met: 8\nrequirements_total: 12\n---\n# Audit\n4 discrepancies."
        )
        result = validate_phase_output(Phase.AUDIT, tmp_path)
        assert result.extracted.get("requirements_met") == 8

    def test_critical_override(self, tmp_path):
        """PASS status should be overridden when CRITICAL findings exist."""
        (tmp_path / "SPEC_AUDIT.md").write_text(
            "---\nstatus: pass\nrequirements_met: 12\nrequirements_total: 12\n---\n"
            "# Audit\n\n| Issue | Severity |\n|-------|----------|\n| Missing page | CRITICAL |\n"
        )
        result = validate_phase_output(Phase.AUDIT, tmp_path)
        assert result.extracted.get("passed") is False
        assert result.extracted.get("critical_count", 0) >= 1

    def test_missing_file_fails(self, tmp_path):
        result = validate_phase_output(Phase.AUDIT, tmp_path)
        assert not result.passed


# =====================================================================
# Test Validator
# =====================================================================


class TestTestValidator:
    """Validates _validate_test extracts test counts."""

    def test_yaml_format(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text(
            "---\ntests_passed: 14\ntests_total: 14\nall_passed: true\n---\n# Tests\nAll passed."
        )
        result = validate_phase_output(Phase.TEST, tmp_path)
        assert result.passed
        assert result.extracted.get("tests_passed") == 14
        assert result.extracted.get("tests_total") == 14

    def test_slash_format(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text("# Results\n\n12 / 14 passed\n")
        result = validate_phase_output(Phase.TEST, tmp_path)
        assert result.extracted.get("tests_passed") == 12
        assert result.extracted.get("tests_total") == 14

    def test_of_format(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text("# Results\n\n10 of 10 passed\n")
        result = validate_phase_output(Phase.TEST, tmp_path)
        assert result.extracted.get("tests_passed") == 10

    def test_simple_format(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text("# Results\n\n8 tests passed\n")
        result = validate_phase_output(Phase.TEST, tmp_path)
        assert result.extracted.get("tests_passed") == 8

    def test_failed_status(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text(
            "---\ntests_passed: 10\ntests_total: 14\nall_passed: false\n---\n# Tests\nSome failed."
        )
        result = validate_phase_output(Phase.TEST, tmp_path)
        assert result.extracted.get("all_passed") is False

    def test_missing_file_fails(self, tmp_path):
        result = validate_phase_output(Phase.TEST, tmp_path)
        assert not result.passed


# =====================================================================
# Deploy Validator
# =====================================================================


class TestDeployValidator:
    """Validates _validate_deploy extracts URLs and detects blockers."""

    def test_yaml_url(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "---\nurl: https://my-app.vercel.app\n---\n# Deployed\n"
        )
        result = validate_phase_output(Phase.DEPLOY, tmp_path)
        assert result.extracted.get("url") == "https://my-app.vercel.app"

    def test_regex_url_vercel(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "# Deploy\n\nDeployed to https://proserv-abc123.vercel.app successfully.\n"
        )
        result = validate_phase_output(Phase.DEPLOY, tmp_path)
        assert "vercel.app" in result.extracted.get("url", "")

    def test_deploy_blocked(self, tmp_path):
        (tmp_path / "DEPLOY_BLOCKED.md").write_text("# Blocked\nSQLite on Vercel.")
        result = validate_phase_output(Phase.DEPLOY, tmp_path)
        assert not result.passed

    def test_placeholder_database_url(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "# Deploy\nDATABASE_URL=placeholder\nhttps://app.vercel.app\n"
        )
        result = validate_phase_output(Phase.DEPLOY, tmp_path)
        assert result.extracted.get("database_placeholder") is True


# =====================================================================
# Verify Validator
# =====================================================================


class TestVerifyValidator:
    """Validates _validate_verify extracts verification status."""

    def test_yaml_verified(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text(
            "---\nverified: true\n---\n# Verification\nAll endpoints pass."
        )
        result = validate_phase_output(Phase.VERIFY, tmp_path)
        assert result.extracted.get("verified") is True

    def test_keyword_pass(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text("# Verification\n\nAll checks passed successfully.")
        result = validate_phase_output(Phase.VERIFY, tmp_path)
        assert result.extracted.get("verified") is True

    def test_keyword_fail(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text("# Verification\n\nHomepage check failed.")
        result = validate_phase_output(Phase.VERIFY, tmp_path)
        assert result.extracted.get("verified") is False

    def test_missing_file(self, tmp_path):
        result = validate_phase_output(Phase.VERIFY, tmp_path)
        assert not result.passed
