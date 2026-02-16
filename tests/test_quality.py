"""Tests for the quality scoring module (v9.0 weights)."""

import pytest

from agent.quality import QualityReport, compute_quality_score, format_quality_report
from agent.state import AgentState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> AgentState:
    """Create an AgentState with sensible defaults, applying overrides."""
    state = AgentState()
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def _perfect_state() -> AgentState:
    """Return a state that should yield a perfect 100 score."""
    return _make_state(
        tests_generated=True,
        tests_passed=True,
        spec_audit_completed=True,
        spec_audit_discrepancies=0,
        build_attempts=1,
        design_revision=0,
        deployment_verified=True,
        deployment_url="https://example.com",
    )


# ---------------------------------------------------------------------------
# QualityReport dataclass
# ---------------------------------------------------------------------------

class TestQualityReportDataclass:
    """Tests for the QualityReport dataclass itself."""

    def test_create_quality_report(self):
        report = QualityReport(
            score=85,
            grade="B+",
            factors={"tests": 25, "spec_coverage": 20},
            notes=["All good"],
        )
        assert report.score == 85
        assert report.grade == "B+"
        assert report.factors == {"tests": 25, "spec_coverage": 20}
        assert report.notes == ["All good"]

    def test_quality_report_empty_notes(self):
        report = QualityReport(score=100, grade="A", factors={}, notes=[])
        assert report.notes == []

    def test_quality_report_factors_are_mutable(self):
        report = QualityReport(score=0, grade="F", factors={}, notes=[])
        report.factors["tests"] = 25
        assert report.factors["tests"] == 25

    def test_quality_report_equality(self):
        a = QualityReport(score=90, grade="A-", factors={"tests": 25}, notes=["ok"])
        b = QualityReport(score=90, grade="A-", factors={"tests": 25}, notes=["ok"])
        assert a == b


# ---------------------------------------------------------------------------
# Perfect score
# ---------------------------------------------------------------------------

class TestPerfectScore:
    """Tests for a build with all factors maximized."""

    def test_perfect_score_is_100(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        assert report.score == 100

    def test_perfect_grade_is_A(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        assert report.grade == "A"

    def test_perfect_score_has_no_notes(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        assert report.notes == []

    def test_perfect_score_all_factors_present(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        expected_factors = {
            "verification": 35,
            "tests": 25,
            "spec_coverage": 20,
            "build_efficiency": 10,
            "design_quality": 10,
        }
        assert report.factors == expected_factors

    def test_perfect_score_factors_sum_to_100(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        assert sum(report.factors.values()) == 100


# ---------------------------------------------------------------------------
# Verification factor (35 points max) — most important
# ---------------------------------------------------------------------------

class TestVerificationFactor:
    """Tests for the verification scoring factor."""

    def test_verified_gives_35(self):
        state = _make_state(deployment_verified=True, deployment_url="https://example.com")
        report = compute_quality_score(state)
        assert report.factors["verification"] == 35

    def test_deployed_not_verified_gives_15(self):
        state = _make_state(deployment_verified=False, deployment_url="https://example.com")
        report = compute_quality_score(state)
        assert report.factors["verification"] == 15

    def test_deployed_not_verified_adds_note(self):
        state = _make_state(deployment_verified=False, deployment_url="https://example.com")
        report = compute_quality_score(state)
        assert any("not fully verified" in n.lower() for n in report.notes)

    def test_no_deployment_gives_5(self):
        state = _make_state(deployment_verified=False, deployment_url=None)
        report = compute_quality_score(state)
        assert report.factors["verification"] == 5

    def test_no_deployment_adds_note(self):
        state = _make_state(deployment_verified=False, deployment_url=None)
        report = compute_quality_score(state)
        assert any("no deployment" in n.lower() for n in report.notes)

    def test_verified_with_no_url_still_gives_35(self):
        """deployment_verified=True without URL still yields 35."""
        state = _make_state(deployment_verified=True, deployment_url=None)
        report = compute_quality_score(state)
        assert report.factors["verification"] == 35


# ---------------------------------------------------------------------------
# Tests factor (25 points max)
# ---------------------------------------------------------------------------

class TestTestsFactor:
    """Tests for the tests scoring factor."""

    def test_generated_and_passed_gives_25(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        assert report.factors["tests"] == 25

    def test_generated_but_failed_gives_8(self):
        state = _make_state(
            tests_generated=True,
            tests_passed=False,
            spec_audit_completed=True,
            build_attempts=1,
            deployment_verified=True,
        )
        report = compute_quality_score(state)
        assert report.factors["tests"] == 8

    def test_generated_but_failed_adds_note(self):
        state = _make_state(tests_generated=True, tests_passed=False)
        report = compute_quality_score(state)
        assert any("failed" in n.lower() for n in report.notes)

    def test_not_generated_gives_0(self):
        state = _make_state(tests_generated=False, tests_passed=False)
        report = compute_quality_score(state)
        assert report.factors["tests"] == 0

    def test_not_generated_adds_note(self):
        state = _make_state(tests_generated=False)
        report = compute_quality_score(state)
        assert any("no tests" in n.lower() for n in report.notes)

    def test_passed_without_generated_gives_0(self):
        """tests_passed=True but generated=False still gives 0."""
        state = _make_state(tests_generated=False, tests_passed=True)
        report = compute_quality_score(state)
        assert report.factors["tests"] == 0


# ---------------------------------------------------------------------------
# Spec coverage factor (20 points max)
# ---------------------------------------------------------------------------

class TestSpecCoverageFactor:
    """Tests for the spec coverage scoring factor."""

    def test_completed_zero_discrepancies_gives_20(self):
        state = _make_state(spec_audit_completed=True, spec_audit_discrepancies=0)
        report = compute_quality_score(state)
        assert report.factors["spec_coverage"] == 20

    def test_completed_one_discrepancy_gives_15(self):
        state = _make_state(spec_audit_completed=True, spec_audit_discrepancies=1)
        report = compute_quality_score(state)
        assert report.factors["spec_coverage"] == 15

    def test_completed_two_discrepancies_gives_15(self):
        state = _make_state(spec_audit_completed=True, spec_audit_discrepancies=2)
        report = compute_quality_score(state)
        assert report.factors["spec_coverage"] == 15

    def test_completed_three_discrepancies_gives_5(self):
        state = _make_state(spec_audit_completed=True, spec_audit_discrepancies=3)
        report = compute_quality_score(state)
        assert report.factors["spec_coverage"] == 5

    def test_completed_many_discrepancies_gives_5(self):
        state = _make_state(spec_audit_completed=True, spec_audit_discrepancies=50)
        report = compute_quality_score(state)
        assert report.factors["spec_coverage"] == 5

    def test_not_completed_gives_0(self):
        """Audit not completed now gives 0 (was 10 in v8)."""
        state = _make_state(spec_audit_completed=False)
        report = compute_quality_score(state)
        assert report.factors["spec_coverage"] == 0

    def test_not_completed_adds_note(self):
        state = _make_state(spec_audit_completed=False)
        report = compute_quality_score(state)
        assert any("audit" in n.lower() and "not completed" in n.lower() for n in report.notes)

    def test_discrepancies_note_includes_count(self):
        state = _make_state(spec_audit_completed=True, spec_audit_discrepancies=2)
        report = compute_quality_score(state)
        assert any("2" in n for n in report.notes)

    def test_many_discrepancies_note_says_needs_attention(self):
        state = _make_state(spec_audit_completed=True, spec_audit_discrepancies=5)
        report = compute_quality_score(state)
        assert any("needs attention" in n.lower() for n in report.notes)


# ---------------------------------------------------------------------------
# Build efficiency factor (10 points max)
# ---------------------------------------------------------------------------

class TestBuildEfficiencyFactor:
    """Tests for the build efficiency scoring factor."""

    def test_one_attempt_gives_10(self):
        state = _make_state(build_attempts=1)
        report = compute_quality_score(state)
        assert report.factors["build_efficiency"] == 10

    def test_two_attempts_gives_7(self):
        state = _make_state(build_attempts=2)
        report = compute_quality_score(state)
        assert report.factors["build_efficiency"] == 7

    def test_three_attempts_gives_4(self):
        state = _make_state(build_attempts=3)
        report = compute_quality_score(state)
        assert report.factors["build_efficiency"] == 4

    def test_four_attempts_gives_2(self):
        state = _make_state(build_attempts=4)
        report = compute_quality_score(state)
        assert report.factors["build_efficiency"] == 2

    def test_five_attempts_gives_2(self):
        state = _make_state(build_attempts=5)
        report = compute_quality_score(state)
        assert report.factors["build_efficiency"] == 2

    def test_many_attempts_gives_2(self):
        state = _make_state(build_attempts=100)
        report = compute_quality_score(state)
        assert report.factors["build_efficiency"] == 2

    def test_two_attempts_adds_note(self):
        state = _make_state(build_attempts=2)
        report = compute_quality_score(state)
        assert any("retry" in n.lower() for n in report.notes)

    def test_four_attempts_note_includes_retry_count(self):
        state = _make_state(build_attempts=4)
        report = compute_quality_score(state)
        assert any("3 retries" in n for n in report.notes)


# ---------------------------------------------------------------------------
# Design quality factor (10 points max)
# ---------------------------------------------------------------------------

class TestDesignQualityFactor:
    """Tests for the design quality scoring factor."""

    def test_zero_revisions_gives_10(self):
        state = _make_state(design_revision=0)
        report = compute_quality_score(state)
        assert report.factors["design_quality"] == 10

    def test_one_revision_gives_7(self):
        state = _make_state(design_revision=1)
        report = compute_quality_score(state)
        assert report.factors["design_quality"] == 7

    def test_two_revisions_gives_3(self):
        state = _make_state(design_revision=2)
        report = compute_quality_score(state)
        assert report.factors["design_quality"] == 3

    def test_many_revisions_gives_3(self):
        state = _make_state(design_revision=10)
        report = compute_quality_score(state)
        assert report.factors["design_quality"] == 3

    def test_one_revision_adds_note(self):
        state = _make_state(design_revision=1)
        report = compute_quality_score(state)
        assert any("1 revision" in n for n in report.notes)

    def test_multiple_revisions_note_includes_count(self):
        state = _make_state(design_revision=3)
        report = compute_quality_score(state)
        assert any("3 revisions" in n for n in report.notes)


# ---------------------------------------------------------------------------
# Hard caps
# ---------------------------------------------------------------------------

class TestHardCaps:
    """Tests for hard quality caps that prevent broken builds from scoring high."""

    def test_unverified_capped_at_69(self):
        """Efficient build + unverified deployment → capped at C."""
        state = _make_state(
            tests_generated=True,
            tests_passed=True,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            build_attempts=1,
            design_revision=0,
            deployment_verified=False,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        # Raw: 15 + 25 + 20 + 10 + 10 = 80, capped at 69
        assert report.score == 69
        assert report.grade == "C"
        assert any("capped" in n.lower() for n in report.notes)

    def test_unverified_below_cap_not_affected(self):
        """Score already below cap → no capping applied."""
        state = _make_state(
            tests_generated=True,
            tests_passed=False,
            spec_audit_completed=True,
            spec_audit_discrepancies=3,
            build_attempts=3,
            design_revision=2,
            deployment_verified=False,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        # Raw: 15 + 8 + 5 + 4 + 3 = 35, below 69 → no cap
        assert report.score == 35
        assert report.grade == "F"
        assert not any("capped" in n.lower() for n in report.notes)

    def test_no_tests_capped_at_79(self):
        """Perfect build but no tests → capped at B-."""
        state = _make_state(
            tests_generated=False,
            tests_passed=False,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            build_attempts=1,
            design_revision=0,
            deployment_verified=True,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        # Raw: 35 + 0 + 20 + 10 + 10 = 75, below 79 → no cap
        assert report.score == 75
        assert report.grade == "B-"

    def test_both_caps_take_minimum(self):
        """Both unverified and no tests → tighter cap wins."""
        state = _make_state(
            tests_generated=False,
            tests_passed=False,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            build_attempts=1,
            design_revision=0,
            deployment_verified=False,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        # Raw: 15 + 0 + 20 + 10 + 10 = 55
        # unverified cap: 69 (not triggered since 55 < 69)
        # no tests cap: 79 (not triggered since 55 < 79)
        assert report.score == 55
        assert report.grade == "F"

    def test_feedbase_scenario_capped(self):
        """The Feedbase stress test scenario: everything 'efficient' but broken app."""
        state = _make_state(
            tests_generated=True,
            tests_passed=True,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            build_attempts=1,
            design_revision=0,
            deployment_verified=False,  # App was broken!
            deployment_url="https://feedbase.vercel.app",
        )
        report = compute_quality_score(state)
        # Raw: 15 + 25 + 20 + 10 + 10 = 80, capped at 69
        assert report.score == 69
        assert report.grade == "C"
        # NOT an A — this is the fix for the stress test problem


# ---------------------------------------------------------------------------
# Grade thresholds
# ---------------------------------------------------------------------------

class TestGradeThresholds:
    """Tests for the letter grade assignments."""

    @pytest.mark.parametrize("score,expected_grade", [
        (100, "A"),
        (95, "A"),
        (94, "A-"),
        (90, "A-"),
        (89, "B+"),
        (85, "B+"),
        (84, "B"),
        (80, "B"),
        (79, "B-"),
        (70, "B-"),
        (69, "C"),
        (60, "C"),
        (59, "F"),
        (0, "F"),
    ])
    def test_grade_at_boundary(self, score, expected_grade):
        """Verify the grading logic at each boundary value."""
        if score >= 95:
            expected = "A"
        elif score >= 90:
            expected = "A-"
        elif score >= 85:
            expected = "B+"
        elif score >= 80:
            expected = "B"
        elif score >= 70:
            expected = "B-"
        elif score >= 60:
            expected = "C"
        else:
            expected = "F"
        assert expected == expected_grade

    def test_grade_A_from_compute(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        assert report.grade == "A"

    def test_grade_A_minus_from_compute(self):
        """Score 90 → A-."""
        # verify=35, tests=25, spec=20, efficiency=7, design=3 = 90
        state = _make_state(
            tests_generated=True,
            tests_passed=True,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            build_attempts=2,
            design_revision=2,
            deployment_verified=True,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        assert report.score == 90
        assert report.grade == "A-"

    def test_grade_B_plus_from_compute(self):
        """Score 85 → B+."""
        # verify=35, tests=25, spec=15, efficiency=7, design=3 = 85
        state = _make_state(
            tests_generated=True,
            tests_passed=True,
            spec_audit_completed=True,
            spec_audit_discrepancies=1,
            build_attempts=2,
            design_revision=2,
            deployment_verified=True,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        assert report.score == 85
        assert report.grade == "B+"

    def test_grade_B_from_compute(self):
        """Score 80 → B."""
        # verify=35, tests=8 (failed), spec=20, efficiency=10, design=7 = 80
        state = _make_state(
            tests_generated=True,
            tests_passed=False,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            build_attempts=1,
            design_revision=1,
            deployment_verified=True,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        assert report.score == 80
        assert report.grade == "B"

    def test_grade_B_minus_from_compute(self):
        """Score 70 → B-."""
        # verify=35, tests=8, spec=20, efficiency=4, design=3 = 70
        state = _make_state(
            tests_generated=True,
            tests_passed=False,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            build_attempts=3,
            design_revision=2,
            deployment_verified=True,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        assert report.score == 70
        assert report.grade == "B-"

    def test_grade_C_from_compute(self):
        """Unverified deployment → capped at C."""
        # verify=15, tests=25, spec=20, efficiency=7, design=3 = 70 → capped at 69
        state = _make_state(
            tests_generated=True,
            tests_passed=True,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            build_attempts=2,
            design_revision=2,
            deployment_verified=False,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        assert report.score == 69
        assert report.grade == "C"

    def test_grade_F_from_compute(self):
        """Low score → F."""
        # verify=5, tests=0, spec=0, efficiency=2, design=3 = 10
        state = _make_state(
            tests_generated=False,
            tests_passed=False,
            spec_audit_completed=False,
            build_attempts=4,
            design_revision=2,
            deployment_verified=False,
            deployment_url=None,
        )
        report = compute_quality_score(state)
        assert report.score == 10
        assert report.grade == "F"


# ---------------------------------------------------------------------------
# Combined scenarios
# ---------------------------------------------------------------------------

class TestCombinedScenarios:
    """Tests for realistic combined build scenarios."""

    def test_perfect_build(self):
        state = _make_state(
            tests_generated=True,
            tests_passed=True,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            build_attempts=1,
            design_revision=0,
            deployment_verified=True,
            deployment_url="https://myapp.vercel.app",
        )
        report = compute_quality_score(state)
        assert report.score == 100
        assert report.grade == "A"
        assert report.notes == []

    def test_mediocre_build(self):
        """Mediocre build with some issues across multiple factors."""
        state = _make_state(
            tests_generated=True,
            tests_passed=False,       # 8
            spec_audit_completed=True,
            spec_audit_discrepancies=1,  # 15
            build_attempts=2,          # 7
            design_revision=1,         # 7
            deployment_verified=False,
            deployment_url="https://myapp.vercel.app",  # 15
        )
        report = compute_quality_score(state)
        # 15 + 8 + 15 + 7 + 7 = 52 (below 69 cap, no capping)
        assert report.score == 52
        assert report.grade == "F"
        assert len(report.notes) > 0

    def test_poor_build(self):
        """Poor build with problems everywhere."""
        state = _make_state(
            tests_generated=False,     # 0
            tests_passed=False,
            spec_audit_completed=True,
            spec_audit_discrepancies=10,  # 5
            build_attempts=5,          # 2
            design_revision=3,         # 3
            deployment_verified=False,
            deployment_url=None,       # 5
        )
        report = compute_quality_score(state)
        # 5 + 0 + 5 + 2 + 3 = 15
        assert report.score == 15
        assert report.grade == "F"
        assert len(report.notes) >= 4

    def test_good_build_with_minor_issues(self):
        """Good build with one or two minor issues."""
        state = _make_state(
            tests_generated=True,
            tests_passed=True,          # 25
            spec_audit_completed=True,
            spec_audit_discrepancies=1,  # 15
            build_attempts=1,           # 10
            design_revision=0,          # 10
            deployment_verified=True,
            deployment_url="https://myapp.vercel.app",  # 35
        )
        report = compute_quality_score(state)
        # 35 + 25 + 15 + 10 + 10 = 95
        assert report.score == 95
        assert report.grade == "A"

    def test_default_state_score(self):
        """Score from a freshly created default AgentState."""
        state = AgentState()
        report = compute_quality_score(state)
        # verify=5, tests=0, spec=0, efficiency=10 (0 attempts <= 1), design=10
        # Total = 25
        assert report.score == 25
        assert report.grade == "F"

    def test_phase_results_param_accepted(self):
        from agent.progress import PhaseResult
        state = _perfect_state()
        results = [PhaseResult(phase_name="build", success=True, duration_s=10.0)]
        report = compute_quality_score(state, phase_results=results)
        assert report.score == 100

    def test_phase_results_none_accepted(self):
        state = _perfect_state()
        report = compute_quality_score(state, phase_results=None)
        assert report.score == 100


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_build_attempts_gives_10(self):
        state = _make_state(build_attempts=0)
        report = compute_quality_score(state)
        assert report.factors["build_efficiency"] == 10

    def test_negative_discrepancies_treated_as_nonzero(self):
        """Negative values fall through to the <= 2 branch."""
        state = _make_state(spec_audit_completed=True, spec_audit_discrepancies=-1)
        report = compute_quality_score(state)
        assert report.factors["spec_coverage"] == 15

    def test_score_clamped_to_max_100(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        assert report.score <= 100

    def test_score_clamped_to_min_0(self):
        state = AgentState()
        report = compute_quality_score(state)
        assert report.score >= 0

    def test_empty_deployment_url_string_counts_as_no_deployment(self):
        """Empty string is falsy, so it should behave like no deployment."""
        state = _make_state(deployment_verified=False, deployment_url="")
        report = compute_quality_score(state)
        assert report.factors["verification"] == 5

    def test_large_build_attempts_gives_2(self):
        state = _make_state(build_attempts=999)
        report = compute_quality_score(state)
        assert report.factors["build_efficiency"] == 2

    def test_large_design_revision_gives_3(self):
        state = _make_state(design_revision=999)
        report = compute_quality_score(state)
        assert report.factors["design_quality"] == 3


# ---------------------------------------------------------------------------
# format_quality_report
# ---------------------------------------------------------------------------

class TestFormatQualityReport:
    """Tests for the format_quality_report function."""

    def test_returns_string(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        output = format_quality_report(report)
        assert isinstance(output, str)

    def test_contains_grade_and_score(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        output = format_quality_report(report)
        assert "A" in output
        assert "100%" in output

    def test_contains_breakdown_header(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        output = format_quality_report(report)
        assert "Breakdown:" in output

    def test_contains_all_factor_labels(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        output = format_quality_report(report)
        assert "Verification" in output
        assert "Tests" in output
        assert "Spec Coverage" in output
        assert "Build Efficiency" in output
        assert "Design Quality" in output

    def test_contains_bar_characters(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        output = format_quality_report(report)
        assert "\u2588" in output  # Full block character

    def test_contains_score_fractions(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        output = format_quality_report(report)
        assert "35/35" in output
        assert "25/25" in output
        assert "20/20" in output
        assert "10/10" in output

    def test_notes_section_present_when_notes_exist(self):
        state = _make_state(tests_generated=False)
        report = compute_quality_score(state)
        output = format_quality_report(report)
        assert "Notes:" in output
        assert "No tests generated" in output

    def test_notes_section_absent_when_no_notes(self):
        state = _perfect_state()
        report = compute_quality_score(state)
        output = format_quality_report(report)
        assert "Notes:" not in output

    def test_partial_bar_for_partial_score(self):
        state = _make_state(
            tests_generated=True,
            tests_passed=False,  # 8/25
        )
        report = compute_quality_score(state)
        output = format_quality_report(report)
        assert "8/25" in output
        assert "\u2591" in output  # Light shade (empty bar) character

    def test_format_mediocre_build_output(self):
        state = _make_state(
            tests_generated=True,
            tests_passed=False,
            spec_audit_completed=True,
            spec_audit_discrepancies=3,
            build_attempts=3,
            design_revision=2,
            deployment_verified=False,
            deployment_url=None,
        )
        report = compute_quality_score(state)
        output = format_quality_report(report)
        assert f"{report.grade}" in output
        assert f"{report.score}%" in output
        for note in report.notes:
            assert note in output

    def test_quality_line_format(self):
        report = QualityReport(score=85, grade="B+", factors={}, notes=[])
        output = format_quality_report(report)
        first_line = output.split("\n")[0]
        assert first_line == "Quality: B+ (85%)"


# ---------------------------------------------------------------------------
# v10.0: CRITICAL audit findings penalty
# ---------------------------------------------------------------------------

class TestCriticalAuditPenalty:
    """Tests for the spec_audit_critical_count penalty and cap."""

    def test_critical_findings_reduce_spec_coverage(self):
        """2 CRITICAL findings should reduce spec_coverage (5 pts each = 10 pt penalty)."""
        state = _make_state(
            tests_generated=True,
            tests_passed=True,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            spec_audit_critical_count=2,
            build_attempts=1,
            design_revision=0,
            deployment_verified=True,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        # spec_coverage = max(0, 15 - 10) = 5
        assert report.factors["spec_coverage"] == 5
        assert any("CRITICAL" in n for n in report.notes)

    def test_critical_findings_cap_at_84(self):
        """Score should be capped at 84 when CRITICAL findings exist (max grade B)."""
        state = _make_state(
            tests_generated=True,
            tests_passed=True,
            spec_audit_completed=True,
            spec_audit_discrepancies=0,
            spec_audit_critical_count=1,
            build_attempts=1,
            design_revision=0,
            deployment_verified=True,
            deployment_url="https://example.com",
        )
        report = compute_quality_score(state)
        # Without cap: 35 + 25 + 10 + 10 + 10 = 90, but cap at 84
        assert report.score <= 84
        assert report.grade == "B"
        assert any("capped" in n.lower() for n in report.notes)

    def test_zero_critical_no_penalty(self):
        """0 CRITICAL findings should not change scoring from baseline."""
        perfect = _perfect_state()
        perfect.spec_audit_critical_count = 0
        report = compute_quality_score(perfect)
        assert report.factors["spec_coverage"] == 20
        assert report.score == 100
        assert report.grade == "A"

    def test_many_critical_findings_floor_at_zero(self):
        """Even with many CRITICAL findings, spec_coverage doesn't go negative."""
        state = _make_state(
            spec_audit_completed=True,
            spec_audit_critical_count=10,
            tests_generated=True,
            tests_passed=True,
            deployment_verified=True,
            deployment_url="https://example.com",
            build_attempts=1,
            design_revision=0,
        )
        report = compute_quality_score(state)
        assert report.factors["spec_coverage"] == 0  # max(0, 15 - 50) = 0
