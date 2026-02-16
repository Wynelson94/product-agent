"""Tests for phase output validators (v9.0)."""

import pytest

from agent.state import Phase
from agent.validators import (
    ValidationResult,
    validate_phase_output,
    validate_build_routes,
    _validate_enrich,
    _validate_analysis,
    _validate_design,
    _validate_review,
    _validate_build,
    _validate_audit,
    _validate_test,
    _validate_deploy,
    _validate_verify,
    _extract_url,
    _extract_stack_id,
    _extract_design_routes,
    _route_to_page_path,
    _parse_frontmatter,
    _apply_critical_override,
)


# ---------------------------------------------------------------------------
# ValidationResult dataclass
# ---------------------------------------------------------------------------

class TestValidationResult:

    def test_initial_passed_true(self):
        r = ValidationResult(passed=True, phase=Phase.ENRICH)
        assert r.passed is True
        assert r.phase == Phase.ENRICH
        assert r.messages == []
        assert r.extracted == {}

    def test_initial_passed_false(self):
        r = ValidationResult(passed=False, phase=Phase.BUILD)
        assert r.passed is False

    def test_add_error_sets_passed_false(self):
        r = ValidationResult(passed=True, phase=Phase.ENRICH)
        r.add_error("something went wrong")
        assert r.passed is False
        assert len(r.messages) == 1
        assert r.messages[0] == "FAIL: something went wrong"

    def test_add_error_multiple(self):
        r = ValidationResult(passed=True, phase=Phase.BUILD)
        r.add_error("err1")
        r.add_error("err2")
        assert r.passed is False
        assert len(r.messages) == 2
        assert all(m.startswith("FAIL:") for m in r.messages)

    def test_add_info_does_not_change_passed(self):
        r = ValidationResult(passed=True, phase=Phase.DESIGN)
        r.add_info("all good")
        assert r.passed is True
        assert r.messages == ["INFO: all good"]

    def test_add_info_preserves_false(self):
        r = ValidationResult(passed=False, phase=Phase.DESIGN)
        r.add_info("note")
        assert r.passed is False

    def test_add_error_then_info(self):
        r = ValidationResult(passed=True, phase=Phase.DEPLOY)
        r.add_error("bad")
        r.add_info("fyi")
        assert r.passed is False
        assert len(r.messages) == 2

    def test_extracted_dict_mutable(self):
        r = ValidationResult(passed=True, phase=Phase.ANALYSIS)
        r.extracted["stack_id"] = "rails"
        assert r.extracted == {"stack_id": "rails"}


# ---------------------------------------------------------------------------
# _parse_frontmatter (v9.0)
# ---------------------------------------------------------------------------

class TestParseFrontmatter:

    def test_simple_string_values(self):
        content = "---\nstack_id: nextjs-supabase\nproduct_type: saas\n---\n# Body"
        fm = _parse_frontmatter(content)
        assert fm == {"stack_id": "nextjs-supabase", "product_type": "saas"}

    def test_integer_values(self):
        content = "---\ntests_passed: 10\ntests_total: 12\n---\n"
        fm = _parse_frontmatter(content)
        assert fm["tests_passed"] == 10
        assert fm["tests_total"] == 12

    def test_boolean_values(self):
        content = "---\nverified: true\nall_passed: false\n---\n"
        fm = _parse_frontmatter(content)
        assert fm["verified"] is True
        assert fm["all_passed"] is False

    def test_boolean_yes_no(self):
        content = "---\nverified: yes\nall_passed: no\n---\n"
        fm = _parse_frontmatter(content)
        assert fm["verified"] is True
        assert fm["all_passed"] is False

    def test_null_values(self):
        content = "---\nerror: null\n---\n"
        fm = _parse_frontmatter(content)
        assert fm["error"] is None

    def test_quoted_string_values(self):
        content = '---\nurl: "https://app.vercel.app"\nverdict: \'APPROVED\'\n---\n'
        fm = _parse_frontmatter(content)
        assert fm["url"] == "https://app.vercel.app"
        assert fm["verdict"] == "APPROVED"

    def test_float_values(self):
        content = "---\nscore: 85.5\n---\n"
        fm = _parse_frontmatter(content)
        assert fm["score"] == 85.5

    def test_no_frontmatter_returns_none(self):
        content = "# Just a markdown file\n\nNo front-matter here."
        assert _parse_frontmatter(content) is None

    def test_empty_frontmatter_returns_none(self):
        content = "---\n---\n# Body"
        assert _parse_frontmatter(content) is None

    def test_missing_closing_delimiter(self):
        content = "---\nkey: value\n# No closing delimiter"
        assert _parse_frontmatter(content) is None

    def test_leading_whitespace_stripped(self):
        content = "\n\n---\nstack_id: rails\n---\n"
        fm = _parse_frontmatter(content)
        assert fm["stack_id"] == "rails"

    def test_comments_ignored(self):
        content = "---\n# this is a comment\nstack_id: rails\n---\n"
        fm = _parse_frontmatter(content)
        assert fm == {"stack_id": "rails"}

    def test_empty_string(self):
        assert _parse_frontmatter("") is None

    def test_mixed_types(self):
        content = "---\nverdict: APPROVED\nissues_count: 0\nverified: true\nurl: https://a.vercel.app\n---\n"
        fm = _parse_frontmatter(content)
        assert fm["verdict"] == "APPROVED"
        assert fm["issues_count"] == 0
        assert fm["verified"] is True
        assert fm["url"] == "https://a.vercel.app"


# ---------------------------------------------------------------------------
# _extract_stack_id
# ---------------------------------------------------------------------------

class TestExtractStackId:

    def test_standard_format_with_backticks(self):
        content = "**Stack ID**: `nextjs-supabase`"
        assert _extract_stack_id(content) == "nextjs-supabase"

    def test_standard_format_without_backticks(self):
        content = "**Stack ID**: nextjs-prisma"
        assert _extract_stack_id(content) == "nextjs-prisma"

    def test_in_multiline_document(self):
        content = (
            "# Stack Decision\n\n"
            "We chose the following stack.\n\n"
            "**Stack ID**: `rails`\n\n"
            "## Rationale\nGreat for rapid prototyping."
        )
        assert _extract_stack_id(content) == "rails"

    def test_swift_swiftui(self):
        content = "**Stack ID**: `swift-swiftui`"
        assert _extract_stack_id(content) == "swift-swiftui"

    def test_no_match_returns_none(self):
        content = "This document has no stack ID at all."
        assert _extract_stack_id(content) is None

    def test_empty_string(self):
        assert _extract_stack_id("") is None

    def test_expo_supabase(self):
        content = "**Stack ID**: `expo-supabase`\n"
        assert _extract_stack_id(content) == "expo-supabase"

    def test_extra_whitespace(self):
        content = "**Stack ID**:   `nextjs-prisma`  "
        assert _extract_stack_id(content) == "nextjs-prisma"


# ---------------------------------------------------------------------------
# _extract_url
# ---------------------------------------------------------------------------

class TestExtractUrl:

    def test_vercel_url(self):
        content = "Deployed to https://my-app.vercel.app successfully"
        assert _extract_url(content) == "https://my-app.vercel.app"

    def test_railway_url(self):
        content = "URL: https://my-app-production.railway.app"
        assert _extract_url(content) == "https://my-app-production.railway.app"

    def test_fly_dev_url(self):
        content = "Live at https://cool-app.fly.dev"
        assert _extract_url(content) == "https://cool-app.fly.dev"

    def test_netlify_url(self):
        content = "Site: https://amazing-site-123.netlify.app"
        assert _extract_url(content) == "https://amazing-site-123.netlify.app"

    def test_render_url(self):
        content = "Hosted at https://my-service.onrender.com"
        assert _extract_url(content) == "https://my-service.onrender.com"

    def test_http_url(self):
        content = "Available at http://test-app.vercel.app"
        assert _extract_url(content) == "http://test-app.vercel.app"

    def test_no_url_returns_none(self):
        content = "No deployment URL in this text."
        assert _extract_url(content) is None

    def test_empty_content(self):
        assert _extract_url("") is None

    def test_non_matching_domain(self):
        content = "Visit https://example.com for more info"
        assert _extract_url(content) is None

    def test_first_match_wins(self):
        content = (
            "Primary: https://app.vercel.app\n"
            "Mirror: https://app.railway.app"
        )
        assert _extract_url(content) == "https://app.vercel.app"

    def test_url_with_subdomain(self):
        content = "https://my-org-my-app.vercel.app"
        assert _extract_url(content) == "https://my-org-my-app.vercel.app"


# ---------------------------------------------------------------------------
# _validate_enrich
# ---------------------------------------------------------------------------

class TestValidateEnrich:

    def test_prompt_md_missing(self, tmp_path):
        result = _validate_enrich(tmp_path)
        assert result.passed is False
        assert result.phase == Phase.ENRICH
        assert any("not created" in m for m in result.messages)

    def test_prompt_md_too_short(self, tmp_path):
        (tmp_path / "PROMPT.md").write_text("Short.")
        result = _validate_enrich(tmp_path)
        assert result.passed is False
        assert any("too short" in m for m in result.messages)

    def test_prompt_md_valid(self, tmp_path):
        (tmp_path / "PROMPT.md").write_text("x" * 200)
        result = _validate_enrich(tmp_path)
        assert result.passed is True
        assert any("PROMPT.md exists" in m for m in result.messages)

    def test_prompt_md_exactly_100_chars(self, tmp_path):
        (tmp_path / "PROMPT.md").write_text("a" * 100)
        result = _validate_enrich(tmp_path)
        assert result.passed is True

    def test_prompt_md_99_chars(self, tmp_path):
        (tmp_path / "PROMPT.md").write_text("a" * 99)
        result = _validate_enrich(tmp_path)
        assert result.passed is False


# ---------------------------------------------------------------------------
# _validate_analysis
# ---------------------------------------------------------------------------

class TestValidateAnalysis:

    def test_stack_decision_missing(self, tmp_path):
        result = _validate_analysis(tmp_path)
        assert result.passed is False
        assert any("not created" in m for m in result.messages)

    def test_valid_stack_id_via_regex(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text(
            "# Stack Decision\n\n**Stack ID**: `nextjs-supabase`\n"
        )
        result = _validate_analysis(tmp_path)
        assert result.passed is True
        assert result.extracted["stack_id"] == "nextjs-supabase"
        assert any("Stack selected" in m for m in result.messages)

    def test_valid_stack_id_rails(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text("**Stack ID**: `rails`\n")
        result = _validate_analysis(tmp_path)
        assert result.passed is True
        assert result.extracted["stack_id"] == "rails"

    def test_valid_stack_id_swift_swiftui(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text("**Stack ID**: `swift-swiftui`\n")
        result = _validate_analysis(tmp_path)
        assert result.passed is True
        assert result.extracted["stack_id"] == "swift-swiftui"

    def test_unknown_stack_id(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text("**Stack ID**: `unknown-stack`\n")
        result = _validate_analysis(tmp_path)
        assert result.passed is False
        assert any("Unknown stack ID" in m for m in result.messages)

    def test_fallback_detection(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text(
            "We recommend using the nextjs-prisma stack for this project."
        )
        result = _validate_analysis(tmp_path)
        assert result.passed is True
        assert result.extracted["stack_id"] == "nextjs-prisma"
        assert any("fallback" in m for m in result.messages)

    def test_fallback_detection_expo(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text(
            "For this mobile app, expo-supabase is the ideal choice."
        )
        result = _validate_analysis(tmp_path)
        assert result.passed is True
        assert result.extracted["stack_id"] == "expo-supabase"

    def test_no_stack_id_found(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text("This is a blank decision document.")
        result = _validate_analysis(tmp_path)
        assert result.passed is False
        assert any("No valid stack ID" in m for m in result.messages)

    def test_all_valid_stacks_accepted(self, tmp_path):
        valid_stacks = [
            "nextjs-supabase", "nextjs-prisma", "rails",
            "expo-supabase", "swift-swiftui",
        ]
        for sid in valid_stacks:
            (tmp_path / "STACK_DECISION.md").write_text(f"**Stack ID**: `{sid}`\n")
            result = _validate_analysis(tmp_path)
            assert result.passed is True, f"Stack {sid} should be valid"
            assert result.extracted["stack_id"] == sid

    def test_frontmatter_stack_id(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text(
            "---\nstack_id: nextjs-prisma\n---\n# Stack Decision\n"
        )
        result = _validate_analysis(tmp_path)
        assert result.passed is True
        assert result.extracted["stack_id"] == "nextjs-prisma"
        assert any("front-matter" in m for m in result.messages)

    def test_frontmatter_unknown_stack(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text(
            "---\nstack_id: django-postgres\n---\n# Stack Decision\n"
        )
        result = _validate_analysis(tmp_path)
        assert result.passed is False
        assert any("Unknown" in m for m in result.messages)

    def test_frontmatter_takes_precedence_over_body(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text(
            "---\nstack_id: rails\n---\n**Stack ID**: `nextjs-supabase`\n"
        )
        result = _validate_analysis(tmp_path)
        assert result.extracted["stack_id"] == "rails"


# ---------------------------------------------------------------------------
# _validate_design
# ---------------------------------------------------------------------------

class TestValidateDesign:

    def test_design_md_missing(self, tmp_path):
        result = _validate_design(tmp_path)
        assert result.passed is False
        assert any("not created" in m for m in result.messages)

    def test_design_md_too_short(self, tmp_path):
        (tmp_path / "DESIGN.md").write_text("Short design.")
        result = _validate_design(tmp_path)
        assert result.passed is False
        assert any("too short" in m for m in result.messages)

    def test_design_md_valid_with_all_sections(self, tmp_path):
        content = (
            "# Design Document\n\n"
            "## Data Model\nUsers, posts, comments...\n\n"
            "## Route Architecture\nGET /api/users, POST /api/posts...\n\n"
            "## Auth\nJWT-based authentication with Supabase.\n\n"
            + "x" * 200
        )
        (tmp_path / "DESIGN.md").write_text(content)
        result = _validate_design(tmp_path)
        assert result.passed is True
        info_msgs = [m for m in result.messages if "Section found" in m]
        assert len(info_msgs) == 3

    def test_design_md_missing_sections_non_critical(self, tmp_path):
        content = "# Design\n\n" + "x" * 250
        (tmp_path / "DESIGN.md").write_text(content)
        result = _validate_design(tmp_path)
        assert result.passed is True
        missing_msgs = [m for m in result.messages if "non-critical" in m]
        assert len(missing_msgs) == 3

    def test_design_md_exactly_200_chars(self, tmp_path):
        (tmp_path / "DESIGN.md").write_text("a" * 200)
        result = _validate_design(tmp_path)
        assert result.passed is True

    def test_design_md_199_chars(self, tmp_path):
        (tmp_path / "DESIGN.md").write_text("a" * 199)
        result = _validate_design(tmp_path)
        assert result.passed is False

    def test_design_sections_case_insensitive(self, tmp_path):
        content = (
            "# Design\n"
            "## DATA MODEL\nStuff\n"
            "## ROUTE\nMore stuff\n"
            "## AUTH\nTokens\n"
            + "x" * 200
        )
        (tmp_path / "DESIGN.md").write_text(content)
        result = _validate_design(tmp_path)
        info_found = [m for m in result.messages if "Section found" in m]
        assert len(info_found) == 3

    def test_design_partial_sections(self, tmp_path):
        content = (
            "# Design\n"
            "## Data Model\nTables\n"
            "No pages or endpoints defined yet.\n"
            + "x" * 200
        )
        (tmp_path / "DESIGN.md").write_text(content)
        result = _validate_design(tmp_path)
        assert result.passed is True
        found = [m for m in result.messages if "Section found" in m]
        missing = [m for m in result.messages if "non-critical" in m]
        assert len(found) >= 1  # data model found
        assert len(missing) >= 1  # route or auth missing


# ---------------------------------------------------------------------------
# _validate_review
# ---------------------------------------------------------------------------

class TestValidateReview:

    def test_review_md_missing(self, tmp_path):
        result = _validate_review(tmp_path)
        assert result.passed is True
        assert any("not found" in m for m in result.messages)

    def test_review_approved(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text("# Review\n\nThe design is APPROVED.")
        result = _validate_review(tmp_path)
        assert result.passed is True
        assert result.extracted["approved"] is True
        assert any("APPROVED" in m for m in result.messages)

    def test_review_needs_revision_underscore(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text(
            "# Review\n\nStatus: needs_revision\nPlease fix the auth flow."
        )
        result = _validate_review(tmp_path)
        assert result.passed is True
        assert result.extracted["approved"] is False
        assert "feedback" in result.extracted

    def test_review_needs_revision_space(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text(
            "# Review\n\nThe design needs revision in the data model."
        )
        result = _validate_review(tmp_path)
        assert result.passed is True
        assert result.extracted["approved"] is False

    def test_review_unclear_verdict(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text(
            "# Review\n\nThe design looks interesting. Some thoughts below."
        )
        result = _validate_review(tmp_path)
        assert result.passed is True
        assert result.extracted["approved"] is False
        assert result.extracted["verdict_uncertain"] is True
        assert any("unclear" in m for m in result.messages)

    def test_review_approved_case_insensitive(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text("approved")
        result = _validate_review(tmp_path)
        assert result.extracted["approved"] is True

    def test_review_needs_revision_feedback_stored(self, tmp_path):
        feedback_text = "# Review\n\nneeds_revision\nFix the database schema."
        (tmp_path / "REVIEW.md").write_text(feedback_text)
        result = _validate_review(tmp_path)
        assert result.extracted["feedback"] == feedback_text

    def test_review_frontmatter_approved(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text(
            "---\nverdict: APPROVED\nissues_count: 0\n---\n# Design Review\n"
        )
        result = _validate_review(tmp_path)
        assert result.extracted["approved"] is True
        assert any("front-matter" in m for m in result.messages)

    def test_review_frontmatter_needs_revision(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text(
            "---\nverdict: NEEDS_REVISION\nissues_count: 3\n---\n# Review\nFix auth.\n"
        )
        result = _validate_review(tmp_path)
        assert result.extracted["approved"] is False

    def test_review_frontmatter_unknown_verdict(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text(
            "---\nverdict: MAYBE\n---\n# Review\n"
        )
        result = _validate_review(tmp_path)
        assert result.extracted["approved"] is False
        assert result.extracted["verdict_uncertain"] is True


# ---------------------------------------------------------------------------
# _validate_build
# ---------------------------------------------------------------------------

class TestValidateBuild:

    def test_no_source_at_all(self, tmp_path):
        result = _validate_build(tmp_path)
        assert result.passed is False
        assert any("No source code" in m for m in result.messages)

    def test_src_directory_with_files(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "index.ts").write_text("console.log('hello');")
        result = _validate_build(tmp_path)
        assert result.passed is True
        assert any("src/" in m for m in result.messages)

    def test_app_directory_with_files(self, tmp_path):
        app = tmp_path / "app"
        app.mkdir()
        (app / "page.tsx").write_text("export default function Page() {}")
        result = _validate_build(tmp_path)
        assert result.passed is True
        assert any("app/" in m for m in result.messages)

    def test_sources_directory_swift(self, tmp_path):
        sources = tmp_path / "Sources"
        sources.mkdir()
        (sources / "main.swift").write_text("print(\"Hello\")")
        result = _validate_build(tmp_path)
        assert result.passed is True
        assert any("Sources/" in m for m in result.messages)

    def test_pages_directory(self, tmp_path):
        pages = tmp_path / "pages"
        pages.mkdir()
        (pages / "index.tsx").write_text("export default function Home() {}")
        result = _validate_build(tmp_path)
        assert result.passed is True
        assert any("pages/" in m for m in result.messages)

    def test_empty_source_dir_not_counted(self, tmp_path):
        (tmp_path / "src").mkdir()
        result = _validate_build(tmp_path)
        assert result.passed is False

    def test_code_files_in_root(self, tmp_path):
        (tmp_path / "app.py").write_text("print('hi')")
        (tmp_path / "server.js").write_text("require('http')")
        result = _validate_build(tmp_path)
        assert result.passed is True
        assert any("Code files in root" in m for m in result.messages)

    def test_code_file_ts(self, tmp_path):
        (tmp_path / "index.ts").write_text("const x = 1;")
        result = _validate_build(tmp_path)
        assert result.passed is True

    def test_code_file_tsx(self, tmp_path):
        (tmp_path / "component.tsx").write_text("<div />")
        result = _validate_build(tmp_path)
        assert result.passed is True

    def test_code_file_jsx(self, tmp_path):
        (tmp_path / "App.jsx").write_text("function App() {}")
        result = _validate_build(tmp_path)
        assert result.passed is True

    def test_code_file_rb(self, tmp_path):
        (tmp_path / "config.rb").write_text("puts 'hello'")
        result = _validate_build(tmp_path)
        assert result.passed is True

    def test_code_file_swift(self, tmp_path):
        (tmp_path / "ContentView.swift").write_text("import SwiftUI")
        result = _validate_build(tmp_path)
        assert result.passed is True

    def test_non_code_files_only(self, tmp_path):
        (tmp_path / "README.md").write_text("# Readme")
        (tmp_path / "data.json").write_text("{}")
        result = _validate_build(tmp_path)
        assert result.passed is False

    def test_package_json_detected(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.ts").write_text("const x = 1;")
        (tmp_path / "package.json").write_text('{"name": "app"}')
        result = _validate_build(tmp_path)
        assert result.passed is True
        assert any("package.json" in m for m in result.messages)

    def test_package_swift_detected(self, tmp_path):
        sources = tmp_path / "Sources"
        sources.mkdir()
        (sources / "main.swift").write_text("print(\"hi\")")
        (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9")
        result = _validate_build(tmp_path)
        assert result.passed is True
        assert any("Package.swift" in m for m in result.messages)

    def test_gemfile_detected(self, tmp_path):
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "controller.rb").write_text("class C; end")
        (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'")
        result = _validate_build(tmp_path)
        assert any("Gemfile" in m for m in result.messages)

    def test_multiple_source_dirs(self, tmp_path):
        for d in ["src", "app"]:
            p = tmp_path / d
            p.mkdir()
            (p / "file.ts").write_text("code")
        result = _validate_build(tmp_path)
        assert result.passed is True
        dir_msgs = [m for m in result.messages if "Source directory" in m]
        assert len(dir_msgs) == 2

    def test_nested_files_counted(self, tmp_path):
        src = tmp_path / "src" / "components"
        src.mkdir(parents=True)
        (src / "Button.tsx").write_text("export const Button = () => <button/>")
        (src / "Card.tsx").write_text("export const Card = () => <div/>")
        result = _validate_build(tmp_path)
        assert result.passed is True
        assert any("2 files" in m for m in result.messages)


# ---------------------------------------------------------------------------
# _validate_audit
# ---------------------------------------------------------------------------

class TestValidateAudit:

    def test_audit_file_missing(self, tmp_path):
        result = _validate_audit(tmp_path)
        assert result.passed is False
        assert any("not found" in m for m in result.messages)

    def test_audit_with_counts(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text(
            "# Spec Audit\n\nRequirements met: 8 / 10\n\nOverall: pass"
        )
        result = _validate_audit(tmp_path)
        assert result.passed is True
        assert result.extracted["requirements_met"] == 8
        assert result.extracted["requirements_total"] == 10
        assert result.extracted["passed"] is True

    def test_audit_failed(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text(
            "# Spec Audit\n\n3 / 10 requirements met\n\nResult: fail"
        )
        result = _validate_audit(tmp_path)
        assert result.extracted["requirements_met"] == 3
        assert result.extracted["requirements_total"] == 10
        assert result.extracted["passed"] is False
        assert any("issues" in m for m in result.messages)

    def test_audit_no_counts(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text("# Spec Audit\n\nAll looks good. pass")
        result = _validate_audit(tmp_path)
        assert result.passed is True
        assert "requirements_met" not in result.extracted
        assert result.extracted["passed"] is True

    def test_audit_neither_pass_nor_fail(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text("# Spec Audit\n\nPending review.")
        result = _validate_audit(tmp_path)
        assert result.passed is True
        assert "passed" not in result.extracted

    def test_audit_full_marks(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text("Coverage: 10/10 pass")
        result = _validate_audit(tmp_path)
        assert result.extracted["requirements_met"] == 10
        assert result.extracted["requirements_total"] == 10

    def test_audit_frontmatter_counts(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text(
            "---\nstatus: PASS\nrequirements_met: 9\nrequirements_total: 10\ndiscrepancies: 1\n---\n# Audit\n"
        )
        result = _validate_audit(tmp_path)
        assert result.passed is True
        assert result.extracted["requirements_met"] == 9
        assert result.extracted["requirements_total"] == 10
        assert result.extracted["discrepancies"] == 1
        assert result.extracted["passed"] is True

    def test_audit_frontmatter_needs_fix(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text(
            "---\nstatus: NEEDS_FIX\nrequirements_met: 3\nrequirements_total: 10\n---\n# Audit\n"
        )
        result = _validate_audit(tmp_path)
        assert result.extracted["passed"] is False

    def test_audit_frontmatter_takes_precedence(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text(
            "---\nstatus: PASS\nrequirements_met: 7\nrequirements_total: 10\n---\n5 / 10 fail"
        )
        result = _validate_audit(tmp_path)
        assert result.extracted["requirements_met"] == 7
        assert result.extracted["passed"] is True


# ---------------------------------------------------------------------------
# _apply_critical_override (v10.0)
# ---------------------------------------------------------------------------

class TestApplyCriticalOverride:
    """Tests for the CRITICAL override logic that flips PASS to FAIL."""

    def test_critical_in_table_overrides_pass(self, tmp_path):
        """Audit with PASS status + '| CRITICAL |' in body should flip to failed."""
        audit_content = """---
status: PASS
requirements_met: 16
requirements_total: 18
---
# Spec Audit

## Data Accuracy

### CRITICAL Discrepancies
| # | Category | Expected | Found | File | Severity |
|---|----------|----------|-------|------|----------|
| 1 | Dependency | @react-pdf/renderer | missing | package.json | CRITICAL |
| 2 | Data | real data | data={[]} | dashboard.tsx | CRITICAL |
"""
        (tmp_path / "SPEC_AUDIT.md").write_text(audit_content)
        result = _validate_audit(tmp_path)
        # Should be overridden to False despite front-matter PASS
        assert result.extracted["passed"] is False
        assert result.extracted["critical_count"] == 2
        assert any("CRITICAL" in m for m in result.messages)

    def test_critical_count_extracted(self, tmp_path):
        """Verify critical_count matches the number of '| CRITICAL |' occurrences."""
        audit_content = """---
status: PASS
requirements_met: 8
requirements_total: 10
---
| 1 | Price | $100 | $200 | file.ts | CRITICAL |
| 2 | Name | Foo | Bar | file.ts | MINOR |
| 3 | Dep | lib | missing | pkg.json | CRITICAL |
| 4 | Data | real | mock | dash.tsx | CRITICAL |
"""
        (tmp_path / "SPEC_AUDIT.md").write_text(audit_content)
        result = _validate_audit(tmp_path)
        assert result.extracted["passed"] is False
        assert result.extracted["critical_count"] == 3

    def test_no_override_without_critical(self, tmp_path):
        """PASS without CRITICAL content stays PASS."""
        audit_content = """---
status: PASS
requirements_met: 10
requirements_total: 10
---
# All good
| 1 | Price | $100 | $100 | file.ts | MINOR |
"""
        (tmp_path / "SPEC_AUDIT.md").write_text(audit_content)
        result = _validate_audit(tmp_path)
        assert result.extracted["passed"] is True
        assert "critical_count" not in result.extracted

    def test_override_with_severity_colon_format(self):
        """Direct test of _apply_critical_override with 'severity: critical'."""
        from agent.state import Phase
        result = ValidationResult(passed=True, phase=Phase.AUDIT)
        result.extracted["passed"] = True
        _apply_critical_override(result, "Some text\nseverity: critical\nmore text")
        assert result.extracted["passed"] is False
        assert result.extracted["critical_count"] == 1

    def test_no_override_when_already_failed(self):
        """If audit already failed, override does nothing."""
        from agent.state import Phase
        result = ValidationResult(passed=True, phase=Phase.AUDIT)
        result.extracted["passed"] = False  # Already failed
        _apply_critical_override(result, "| CRITICAL | stuff")
        # Should still be False but no critical_count added
        assert result.extracted["passed"] is False
        assert "critical_count" not in result.extracted


# ---------------------------------------------------------------------------
# _validate_build dependency audit (v10.0)
# ---------------------------------------------------------------------------

class TestBuildDependencyAudit:
    """Tests for the DESIGN.md → package.json dependency cross-check."""

    def test_missing_deps_detected(self, tmp_path):
        """DESIGN.md references @react-pdf/renderer, package.json lacks it."""
        (tmp_path / "DESIGN.md").write_text(
            "Use `@react-pdf/renderer` for PDF generation and `@tanstack/react-table` for tables."
        )
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"next": "14.0.0", "@tanstack/react-table": "8.0.0"}}'
        )
        # Need source dir for build validation to pass
        src = tmp_path / "src" / "app"
        src.mkdir(parents=True)
        (src / "page.tsx").write_text("export default function() { return <div/> }")
        result = _validate_build(tmp_path)
        assert result.passed is True
        assert "@react-pdf/renderer" in result.extracted.get("missing_deps", [])
        assert "@tanstack/react-table" not in result.extracted.get("missing_deps", [])

    def test_no_false_positive_deps(self, tmp_path):
        """DESIGN.md with no scoped package refs should not report missing deps."""
        (tmp_path / "DESIGN.md").write_text(
            "Build a dashboard with charts and tables. Use standard components."
        )
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"next": "14.0.0"}}'
        )
        src = tmp_path / "src" / "app"
        src.mkdir(parents=True)
        (src / "page.tsx").write_text("export default function() { return <div/> }")
        result = _validate_build(tmp_path)
        assert result.passed is True
        assert "missing_deps" not in result.extracted

    def test_all_deps_present(self, tmp_path):
        """When all referenced deps exist, no missing_deps reported."""
        (tmp_path / "DESIGN.md").write_text("Use `@supabase/supabase-js` for auth.")
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"@supabase/supabase-js": "2.0.0"}}'
        )
        src = tmp_path / "src" / "app"
        src.mkdir(parents=True)
        (src / "page.tsx").write_text("export default function() { return <div/> }")
        result = _validate_build(tmp_path)
        assert "missing_deps" not in result.extracted


# ---------------------------------------------------------------------------
# _validate_test
# ---------------------------------------------------------------------------

class TestValidateTest:

    def test_test_file_missing(self, tmp_path):
        result = _validate_test(tmp_path)
        assert result.passed is False
        assert any("not created" in m for m in result.messages)

    def test_test_standard_format(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text(
            "# Test Results\n\n8 / 10 passed\n\nStatus: passed"
        )
        result = _validate_test(tmp_path)
        assert result.passed is True
        assert result.extracted["tests_passed"] == 8
        assert result.extracted["tests_total"] == 10
        assert result.extracted["all_passed"] is True

    def test_test_passing_keyword(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text("5 / 5 passing")
        result = _validate_test(tmp_path)
        assert result.extracted["tests_passed"] == 5
        assert result.extracted["tests_total"] == 5

    def test_test_alternative_format(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text(
            "# Results\n\n12 tests passed"
        )
        result = _validate_test(tmp_path)
        assert result.extracted["tests_passed"] == 12

    def test_test_alternative_singular(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text("1 test passed")
        result = _validate_test(tmp_path)
        assert result.extracted["tests_passed"] == 1

    def test_test_failed_status(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text(
            "# Results\n\n3 / 10 passed\n\nStatus: failed"
        )
        result = _validate_test(tmp_path)
        assert result.passed is False
        assert result.extracted["all_passed"] is False
        assert result.extracted["tests_passed"] == 3
        assert result.extracted["tests_total"] == 10

    def test_test_all_tests_pass_phrase(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text("All tests pass. Great job!")
        result = _validate_test(tmp_path)
        assert result.extracted["all_passed"] is True

    def test_tests_failed_phrase(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text(
            "Some tests failed. See details below."
        )
        result = _validate_test(tmp_path)
        assert result.passed is False
        assert result.extracted["all_passed"] is False

    def test_test_of_format(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text("3 of 10 passed")
        result = _validate_test(tmp_path)
        assert result.extracted["tests_passed"] == 3
        assert result.extracted["tests_total"] == 10

    def test_test_passed_failed_total_format(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text(
            "Passed: 8, Failed: 2, Total: 10"
        )
        result = _validate_test(tmp_path)
        assert result.extracted["tests_passed"] == 8
        assert result.extracted["tests_total"] == 10

    def test_test_no_counts_no_status(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text("# Test Results\n\nTesting complete.")
        result = _validate_test(tmp_path)
        assert result.passed is True
        assert "tests_passed" not in result.extracted
        assert "all_passed" not in result.extracted

    def test_test_case_insensitive(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text("STATUS: PASSED")
        result = _validate_test(tmp_path)
        assert result.extracted["all_passed"] is True

    def test_test_frontmatter_counts(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text(
            "---\ntests_passed: 10\ntests_total: 12\nall_passed: false\n---\n# Results\n"
        )
        result = _validate_test(tmp_path)
        assert result.extracted["tests_passed"] == 10
        assert result.extracted["tests_total"] == 12
        assert result.extracted["all_passed"] is False
        assert result.passed is False  # all_passed=false triggers error

    def test_test_frontmatter_all_passed(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text(
            "---\ntests_passed: 5\ntests_total: 5\nall_passed: true\n---\n"
        )
        result = _validate_test(tmp_path)
        assert result.extracted["all_passed"] is True
        assert result.passed is True

    def test_test_frontmatter_takes_precedence(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text(
            "---\ntests_passed: 8\ntests_total: 10\n---\n3 / 5 passed"
        )
        result = _validate_test(tmp_path)
        assert result.extracted["tests_passed"] == 8
        assert result.extracted["tests_total"] == 10


# ---------------------------------------------------------------------------
# _validate_deploy
# ---------------------------------------------------------------------------

class TestValidateDeploy:

    def test_deploy_blocked(self, tmp_path):
        (tmp_path / "DEPLOY_BLOCKED.md").write_text(
            "Deployment blocked due to failing tests."
        )
        result = _validate_deploy(tmp_path)
        assert result.passed is False
        assert any("blocked" in m.lower() for m in result.messages)

    def test_deployment_md_with_url(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "# Deployment\n\nLive at https://myapp.vercel.app\n"
        )
        result = _validate_deploy(tmp_path)
        assert result.passed is True
        assert result.extracted["url"] == "https://myapp.vercel.app"

    def test_deploy_result_md_with_url(self, tmp_path):
        (tmp_path / "DEPLOY_RESULT.md").write_text(
            "Deployed to https://api.railway.app"
        )
        result = _validate_deploy(tmp_path)
        assert result.passed is True
        assert result.extracted["url"] == "https://api.railway.app"

    def test_deployment_md_preferred_over_other_md(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text("URL: https://app.vercel.app")
        (tmp_path / "NOTES.md").write_text("URL: https://other.railway.app")
        result = _validate_deploy(tmp_path)
        assert result.extracted["url"] == "https://app.vercel.app"

    def test_fallback_to_any_md_file(self, tmp_path):
        (tmp_path / "NOTES.md").write_text(
            "The app is at https://cool-app.fly.dev now."
        )
        result = _validate_deploy(tmp_path)
        assert result.passed is True
        assert result.extracted["url"] == "https://cool-app.fly.dev"

    def test_no_url_found(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text("Deployment complete. No URL available.")
        result = _validate_deploy(tmp_path)
        assert result.passed is True
        assert "url" not in result.extracted
        assert any("No deployment URL" in m for m in result.messages)

    def test_no_files_at_all(self, tmp_path):
        result = _validate_deploy(tmp_path)
        assert result.passed is True
        assert "url" not in result.extracted

    def test_deploy_blocked_truncated(self, tmp_path):
        long_reason = "x" * 500
        (tmp_path / "DEPLOY_BLOCKED.md").write_text(long_reason)
        result = _validate_deploy(tmp_path)
        assert result.passed is False
        fail_msg = [m for m in result.messages if "FAIL" in m][0]
        assert len(fail_msg) < 500

    def test_netlify_url_extraction(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "Site live: https://wonderful-site-abc.netlify.app"
        )
        result = _validate_deploy(tmp_path)
        assert result.extracted["url"] == "https://wonderful-site-abc.netlify.app"

    def test_render_url_extraction(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "Service: https://my-api.onrender.com"
        )
        result = _validate_deploy(tmp_path)
        assert result.extracted["url"] == "https://my-api.onrender.com"

    def test_deploy_frontmatter_url(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "---\nurl: https://myapp.vercel.app\nstatus: success\n---\n# Deploy\n"
        )
        result = _validate_deploy(tmp_path)
        assert result.passed is True
        assert result.extracted["url"] == "https://myapp.vercel.app"
        assert any("front-matter" in m for m in result.messages)

    def test_deploy_frontmatter_takes_precedence(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "---\nurl: https://fm.vercel.app\n---\nLive at https://body.vercel.app"
        )
        result = _validate_deploy(tmp_path)
        assert result.extracted["url"] == "https://fm.vercel.app"

    def test_deploy_placeholder_database_url(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "# Deployment\n\nDATABASE_URL=placeholder\nDeployed to https://app.vercel.app"
        )
        result = _validate_deploy(tmp_path)
        assert result.extracted.get("database_placeholder") is True
        assert result.passed is False

    def test_deploy_localhost_database_url(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "# Deployment\n\nDATABASE_URL=postgres://user:password@localhost:5432/db"
        )
        result = _validate_deploy(tmp_path)
        assert result.extracted.get("database_placeholder") is True
        assert result.passed is False

    def test_deploy_real_database_url_no_flag(self, tmp_path):
        (tmp_path / "DEPLOYMENT.md").write_text(
            "# Deployment\n\nDATABASE_URL=postgres://user:pass@db.supabase.co:5432/postgres\n"
            "Deployed to https://app.vercel.app"
        )
        result = _validate_deploy(tmp_path)
        assert result.extracted.get("database_placeholder") is not True


# ---------------------------------------------------------------------------
# _validate_verify
# ---------------------------------------------------------------------------

class TestValidateVerify:

    def test_verification_md_missing(self, tmp_path):
        result = _validate_verify(tmp_path)
        assert result.passed is False
        assert any("not found" in m for m in result.messages)

    def test_verification_passed(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text(
            "# Verification\n\nAll checks pass. Site is live."
        )
        result = _validate_verify(tmp_path)
        assert result.passed is True
        assert result.extracted["verified"] is True

    def test_verification_success_keyword(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text("Verification: success")
        result = _validate_verify(tmp_path)
        assert result.extracted["verified"] is True

    def test_verification_failed(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text(
            "# Verification\n\nEndpoint health check fail. 503 errors."
        )
        result = _validate_verify(tmp_path)
        assert result.passed is False
        assert result.extracted["verified"] is False
        assert any("FAILED" in m for m in result.messages)

    def test_verification_no_keywords(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text(
            "# Verification\n\nChecks are pending."
        )
        result = _validate_verify(tmp_path)
        assert result.passed is False
        assert result.extracted["verified"] is False
        assert any("inconclusive" in m for m in result.messages)

    def test_verification_pass_case_insensitive(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text("PASS")
        result = _validate_verify(tmp_path)
        assert result.extracted["verified"] is True

    def test_verify_frontmatter_passed(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text(
            "---\nverified: true\nendpoints_tested: 5\nendpoints_passed: 5\n---\n# Verification\n"
        )
        result = _validate_verify(tmp_path)
        assert result.passed is True
        assert result.extracted["verified"] is True
        assert result.extracted["endpoints_tested"] == 5
        assert result.extracted["endpoints_passed"] == 5

    def test_verify_frontmatter_failed(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text(
            "---\nverified: false\nendpoints_tested: 5\nendpoints_passed: 2\n---\n# Verification\n"
        )
        result = _validate_verify(tmp_path)
        assert result.passed is False
        assert result.extracted["verified"] is False

    def test_verify_frontmatter_takes_precedence(self, tmp_path):
        (tmp_path / "VERIFICATION.md").write_text(
            "---\nverified: false\n---\nAll checks pass!"
        )
        result = _validate_verify(tmp_path)
        assert result.extracted["verified"] is False


# ---------------------------------------------------------------------------
# Route extraction and build route validation (v9.0)
# ---------------------------------------------------------------------------

class TestExtractDesignRoutes:

    def test_no_design_file(self, tmp_path):
        assert _extract_design_routes(tmp_path) == []

    def test_extracts_routes_from_table(self, tmp_path):
        design = (
            "# Design\n\n"
            "## Routes\n"
            "| Route | Purpose | Auth |\n"
            "|-------|---------|------|\n"
            "| / | Landing | No |\n"
            "| /login | Auth | No |\n"
            "| /dashboard | Main | Yes |\n"
        )
        (tmp_path / "DESIGN.md").write_text(design)
        routes = _extract_design_routes(tmp_path)
        assert "/" in routes
        assert "/login" in routes
        assert "/dashboard" in routes

    def test_skips_api_routes(self, tmp_path):
        design = (
            "| /login | Auth | No |\n"
            "| /api/users | API | Yes |\n"
            "| /api/items | API | Yes |\n"
        )
        (tmp_path / "DESIGN.md").write_text(design)
        routes = _extract_design_routes(tmp_path)
        assert "/login" in routes
        assert "/api/users" not in routes
        assert "/api/items" not in routes

    def test_handles_dynamic_routes(self, tmp_path):
        design = "| /projects/[id] | Detail | Yes |\n"
        (tmp_path / "DESIGN.md").write_text(design)
        routes = _extract_design_routes(tmp_path)
        assert "/projects/[id]" in routes


class TestRouteToPagePath:

    def test_root_route(self):
        assert _route_to_page_path("/") == "src/app/page.tsx"

    def test_single_segment(self):
        assert _route_to_page_path("/login") == "src/app/login/page.tsx"

    def test_nested_route(self):
        assert _route_to_page_path("/dashboard/settings") == "src/app/dashboard/settings/page.tsx"

    def test_dynamic_route(self):
        assert _route_to_page_path("/projects/[id]") == "src/app/projects/[id]/page.tsx"


class TestValidateBuildRoutes:

    def test_no_design_file(self, tmp_path):
        result = validate_build_routes(tmp_path)
        assert result.passed is True
        assert any("No routes extracted" in m for m in result.messages)

    def test_all_routes_present(self, tmp_path):
        design = (
            "| Route | Purpose |\n"
            "|-------|---------|\n"
            "| / | Home |\n"
            "| /login | Auth |\n"
        )
        (tmp_path / "DESIGN.md").write_text(design)
        (tmp_path / "src" / "app").mkdir(parents=True)
        (tmp_path / "src" / "app" / "page.tsx").write_text("export default function() {}")
        (tmp_path / "src" / "app" / "login").mkdir()
        (tmp_path / "src" / "app" / "login" / "page.tsx").write_text("export default function() {}")
        result = validate_build_routes(tmp_path)
        assert result.passed is True
        assert result.extracted["missing_routes"] == []
        assert any("All 2 routes found" in m for m in result.messages)

    def test_missing_routes_non_strict(self, tmp_path):
        design = (
            "| / | Home |\n"
            "| /login | Auth |\n"
            "| /dashboard | Main |\n"
        )
        (tmp_path / "DESIGN.md").write_text(design)
        (tmp_path / "src" / "app").mkdir(parents=True)
        (tmp_path / "src" / "app" / "page.tsx").write_text("code")
        result = validate_build_routes(tmp_path, strict=False)
        assert result.passed is True  # Non-strict = warnings only
        assert "/login" in result.extracted["missing_routes"]
        assert "/dashboard" in result.extracted["missing_routes"]

    def test_missing_routes_strict(self, tmp_path):
        design = "| /login | Auth |\n| /signup | Register |\n"
        (tmp_path / "DESIGN.md").write_text(design)
        result = validate_build_routes(tmp_path, strict=True)
        assert result.passed is False
        assert any("FAIL" in m for m in result.messages)

    def test_prisma_schema_check(self, tmp_path):
        (tmp_path / "DESIGN.md").write_text("No routes here")
        (tmp_path / "prisma").mkdir()
        (tmp_path / "prisma" / "schema.prisma").write_text(
            "model User {\n  id String @id\n}\nmodel Post {\n  id String @id\n}\n"
        )
        result = validate_build_routes(tmp_path)
        assert any("2 models" in m for m in result.messages)

    def test_prisma_schema_missing(self, tmp_path):
        (tmp_path / "DESIGN.md").write_text("No routes")
        (tmp_path / "prisma").mkdir()
        result = validate_build_routes(tmp_path, strict=True)
        assert result.passed is False
        assert any("schema.prisma is missing" in m for m in result.messages)

    def test_auth_middleware_present(self, tmp_path):
        (tmp_path / "DESIGN.md").write_text("## Auth\nJWT tokens used for auth")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "middleware.ts").write_text("export function middleware() {}")
        result = validate_build_routes(tmp_path)
        assert any("middleware" in m for m in result.messages)

    def test_auth_middleware_missing_strict(self, tmp_path):
        (tmp_path / "DESIGN.md").write_text("## Auth\nUser authentication required")
        result = validate_build_routes(tmp_path, strict=True)
        assert result.passed is False
        assert any("middleware" in m for m in result.messages)

    def test_app_dir_without_src_prefix(self, tmp_path):
        design = "| / | Home |\n"
        (tmp_path / "DESIGN.md").write_text(design)
        # Some projects use app/ instead of src/app/
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "page.tsx").write_text("code")
        result = validate_build_routes(tmp_path)
        assert result.extracted["missing_routes"] == []


# ---------------------------------------------------------------------------
# validate_phase_output dispatcher
# ---------------------------------------------------------------------------

class TestValidatePhaseOutput:

    def test_dispatches_enrich(self, tmp_path):
        (tmp_path / "PROMPT.md").write_text("x" * 150)
        result = validate_phase_output(Phase.ENRICH, tmp_path)
        assert result.phase == Phase.ENRICH
        assert result.passed is True

    def test_dispatches_analysis(self, tmp_path):
        (tmp_path / "STACK_DECISION.md").write_text("**Stack ID**: `rails`\n")
        result = validate_phase_output(Phase.ANALYSIS, tmp_path)
        assert result.phase == Phase.ANALYSIS
        assert result.extracted["stack_id"] == "rails"

    def test_dispatches_design(self, tmp_path):
        (tmp_path / "DESIGN.md").write_text("a" * 300)
        result = validate_phase_output(Phase.DESIGN, tmp_path)
        assert result.phase == Phase.DESIGN

    def test_dispatches_review(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text("approved")
        result = validate_phase_output(Phase.REVIEW, tmp_path)
        assert result.phase == Phase.REVIEW

    def test_dispatches_build(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.ts").write_text("code")
        result = validate_phase_output(Phase.BUILD, tmp_path)
        assert result.phase == Phase.BUILD

    def test_dispatches_audit(self, tmp_path):
        (tmp_path / "SPEC_AUDIT.md").write_text("8/10 pass")
        result = validate_phase_output(Phase.AUDIT, tmp_path)
        assert result.phase == Phase.AUDIT

    def test_dispatches_test(self, tmp_path):
        (tmp_path / "TEST_RESULTS.md").write_text("10 / 10 passed")
        result = validate_phase_output(Phase.TEST, tmp_path)
        assert result.phase == Phase.TEST

    def test_dispatches_deploy(self, tmp_path):
        result = validate_phase_output(Phase.DEPLOY, tmp_path)
        assert result.phase == Phase.DEPLOY

    def test_dispatches_verify(self, tmp_path):
        result = validate_phase_output(Phase.VERIFY, tmp_path)
        assert result.phase == Phase.VERIFY

    def test_unknown_phase_returns_info(self, tmp_path):
        result = validate_phase_output(Phase.INIT, tmp_path)
        assert result.passed is True
        assert any("No validator defined" in m for m in result.messages)

    def test_complete_phase_returns_info(self, tmp_path):
        result = validate_phase_output(Phase.COMPLETE, tmp_path)
        assert result.passed is True
        assert any("No validator defined" in m for m in result.messages)

    def test_failed_phase_returns_info(self, tmp_path):
        result = validate_phase_output(Phase.FAILED, tmp_path)
        assert result.passed is True

    def test_accepts_string_path(self, tmp_path):
        (tmp_path / "PROMPT.md").write_text("x" * 150)
        result = validate_phase_output(Phase.ENRICH, str(tmp_path))
        assert result.passed is True

    def test_enrich_failure_via_dispatcher(self, tmp_path):
        result = validate_phase_output(Phase.ENRICH, tmp_path)
        assert result.passed is False

    def test_build_failure_via_dispatcher(self, tmp_path):
        result = validate_phase_output(Phase.BUILD, tmp_path)
        assert result.passed is False
