"""Tests for progress reporting module."""

import io
import time

import pytest

from agent.progress import PhaseResult, ProgressReporter, _format_duration


# ---------------------------------------------------------------------------
# PhaseResult dataclass
# ---------------------------------------------------------------------------

class TestPhaseResult:
    """Tests for the PhaseResult dataclass."""

    def test_creation_with_required_fields(self):
        """Test creating PhaseResult with only required fields."""
        result = PhaseResult(phase_name="scaffold", success=True, duration_s=2.5)
        assert result.phase_name == "scaffold"
        assert result.success is True
        assert result.duration_s == 2.5

    def test_default_detail_is_empty(self):
        """Test that detail defaults to an empty string."""
        result = PhaseResult(phase_name="test", success=False, duration_s=1.0)
        assert result.detail == ""

    def test_default_num_turns_is_zero(self):
        """Test that num_turns defaults to 0."""
        result = PhaseResult(phase_name="test", success=True, duration_s=0.5)
        assert result.num_turns == 0

    def test_default_cost_usd_is_none(self):
        """Test that cost_usd defaults to None."""
        result = PhaseResult(phase_name="test", success=True, duration_s=0.5)
        assert result.cost_usd is None

    def test_creation_with_all_fields(self):
        """Test creating PhaseResult with every field specified."""
        result = PhaseResult(
            phase_name="deploy",
            success=True,
            duration_s=45.3,
            detail="deployed to production",
            num_turns=5,
            cost_usd=0.12,
        )
        assert result.phase_name == "deploy"
        assert result.success is True
        assert result.duration_s == 45.3
        assert result.detail == "deployed to production"
        assert result.num_turns == 5
        assert result.cost_usd == 0.12

    def test_failed_result(self):
        """Test creating a failed PhaseResult."""
        result = PhaseResult(
            phase_name="build",
            success=False,
            duration_s=10.0,
            detail="compilation error",
        )
        assert result.success is False
        assert result.detail == "compilation error"

    def test_zero_duration(self):
        """Test PhaseResult with zero duration."""
        result = PhaseResult(phase_name="skip", success=True, duration_s=0.0)
        assert result.duration_s == 0.0


# ---------------------------------------------------------------------------
# _format_duration
# ---------------------------------------------------------------------------

class TestFormatDuration:
    """Tests for the _format_duration helper."""

    def test_zero_seconds(self):
        """Test formatting 0 seconds."""
        assert _format_duration(0) == "0s"

    def test_fractional_seconds_rounds(self):
        """Test that fractional seconds are rounded."""
        assert _format_duration(2.4) == "2s"
        assert _format_duration(2.6) == "3s"

    def test_one_second(self):
        """Test formatting exactly 1 second."""
        assert _format_duration(1.0) == "1s"

    def test_59_seconds_stays_in_seconds(self):
        """Test that 59 seconds does not switch to minute format."""
        assert _format_duration(59) == "59s"

    def test_59_point_9_rounds_to_60s_but_still_seconds_format(self):
        """Test 59.9 rounds to 60s, staying under the < 60 branch due to float."""
        # 59.9 < 60 is True, so it uses seconds format
        assert _format_duration(59.9) == "60s"

    def test_60_seconds_is_one_minute(self):
        """Test that exactly 60 seconds formats as 1m00s."""
        assert _format_duration(60) == "1m00s"

    def test_90_seconds(self):
        """Test 90 seconds formats as 1m30s."""
        assert _format_duration(90) == "1m30s"

    def test_61_seconds(self):
        """Test 61 seconds formats as 1m01s."""
        assert _format_duration(61) == "1m01s"

    def test_3661_seconds_is_one_hour_one_minute_one_second(self):
        """Test large value: 3661s = 61m01s."""
        assert _format_duration(3661) == "61m01s"

    def test_120_seconds(self):
        """Test exactly 2 minutes."""
        assert _format_duration(120) == "2m00s"

    def test_seconds_with_leading_zero_in_secs(self):
        """Test that seconds portion is zero-padded to 2 digits."""
        result = _format_duration(65)
        assert result == "1m05s"


# ---------------------------------------------------------------------------
# ProgressReporter initialization
# ---------------------------------------------------------------------------

class TestProgressReporterInit:
    """Tests for ProgressReporter initialization and defaults."""

    def test_default_verbose_is_false(self):
        """Test that verbose defaults to False."""
        reporter = ProgressReporter(output=io.StringIO())
        assert reporter.verbose is False

    def test_default_total_phases_is_nine(self):
        """Test that the default total phases is 9."""
        reporter = ProgressReporter(output=io.StringIO())
        assert reporter._total_phases == 9

    def test_default_phase_count_is_zero(self):
        """Test that phase count starts at 0."""
        reporter = ProgressReporter(output=io.StringIO())
        assert reporter._phase_count == 0

    def test_default_results_is_empty(self):
        """Test that results list starts empty."""
        reporter = ProgressReporter(output=io.StringIO())
        assert reporter._results == []

    def test_custom_verbose(self):
        """Test setting verbose to True on construction."""
        reporter = ProgressReporter(verbose=True, output=io.StringIO())
        assert reporter.verbose is True

    def test_start_time_is_set(self):
        """Test that _start_time is set to approximately now."""
        before = time.time()
        reporter = ProgressReporter(output=io.StringIO())
        after = time.time()
        assert before <= reporter._start_time <= after


# ---------------------------------------------------------------------------
# set_total_phases
# ---------------------------------------------------------------------------

class TestSetTotalPhases:
    """Tests for set_total_phases."""

    def test_changes_total(self):
        """Test that set_total_phases updates _total_phases."""
        reporter = ProgressReporter(output=io.StringIO())
        reporter.set_total_phases(5)
        assert reporter._total_phases == 5

    def test_reflected_in_phase_start_label(self):
        """Test that the new total appears in phase_start output."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.set_total_phases(3)
        reporter.phase_start("scaffold")
        output = buf.getvalue()
        assert "[1/3]" in output


# ---------------------------------------------------------------------------
# phase_start
# ---------------------------------------------------------------------------

class TestPhaseStart:
    """Tests for phase_start."""

    def test_increments_phase_count(self):
        """Test that phase_start increments the internal counter."""
        reporter = ProgressReporter(output=io.StringIO())
        assert reporter._phase_count == 0
        reporter.phase_start("scaffold")
        assert reporter._phase_count == 1
        reporter.phase_start("implement")
        assert reporter._phase_count == 2

    def test_writes_phase_name(self):
        """Test that phase_start writes the phase name to output."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_start("scaffold")
        output = buf.getvalue()
        assert "scaffold..." in output

    def test_writes_counter_label(self):
        """Test that phase_start writes [N/M] counter."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_start("scaffold")
        output = buf.getvalue()
        assert "[1/9]" in output

    def test_output_uses_newline_for_non_tty(self):
        """Test that non-TTY output uses newline instead of carriage return.

        v12.2: StringIO is not a TTY, so progress lines should end with \\n
        instead of starting with \\r. This ensures clean output when spawned
        from pipes (e.g., Shipwright calling Product Agent via Bash tool).
        """
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_start("scaffold")
        # Non-TTY: no \r prefix, ends with \n
        output = buf.getvalue()
        assert not output.startswith("\r")
        assert output.endswith("\n")

    def test_sequential_starts_increment_correctly(self):
        """Test counter increments across multiple phase_start calls."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_start("phase_a")
        reporter.phase_start("phase_b")
        reporter.phase_start("phase_c")
        assert reporter._phase_count == 3
        output = buf.getvalue()
        assert "[3/9]" in output


# ---------------------------------------------------------------------------
# phase_complete
# ---------------------------------------------------------------------------

class TestPhaseComplete:
    """Tests for phase_complete."""

    def test_appends_result(self):
        """Test that phase_complete appends the result to _results."""
        reporter = ProgressReporter(output=io.StringIO())
        result = PhaseResult(phase_name="scaffold", success=True, duration_s=1.0)
        reporter.phase_complete(result)
        assert len(reporter._results) == 1
        assert reporter._results[0] is result

    def test_writes_done_for_success(self):
        """Test that successful results write 'done'."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_start("scaffold")
        result = PhaseResult(phase_name="scaffold", success=True, duration_s=2.0)
        reporter.phase_complete(result)
        output = buf.getvalue()
        assert "done" in output

    def test_writes_fail_for_failure(self):
        """Test that failed results write 'FAIL'."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_start("build")
        result = PhaseResult(phase_name="build", success=False, duration_s=5.0)
        reporter.phase_complete(result)
        output = buf.getvalue()
        assert "FAIL" in output

    def test_writes_duration(self):
        """Test that phase_complete writes the formatted duration."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_start("deploy")
        result = PhaseResult(phase_name="deploy", success=True, duration_s=90.0)
        reporter.phase_complete(result)
        output = buf.getvalue()
        assert "1m30s" in output

    def test_writes_detail_when_present(self):
        """Test that detail string appears in the output."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_start("test")
        result = PhaseResult(
            phase_name="test", success=True, duration_s=3.0, detail="14/14 passed"
        )
        reporter.phase_complete(result)
        output = buf.getvalue()
        assert "14/14 passed" in output

    def test_no_detail_when_empty(self):
        """Test that empty detail does not add extra spaces."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_start("scaffold")
        result = PhaseResult(phase_name="scaffold", success=True, duration_s=1.0)
        reporter.phase_complete(result)
        # The line should have "scaffold..." directly without extra detail text
        output = buf.getvalue()
        assert "scaffold..." in output

    def test_output_ends_with_newline(self):
        """Test that phase_complete output ends with a newline."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_start("scaffold")
        result = PhaseResult(phase_name="scaffold", success=True, duration_s=1.0)
        reporter.phase_complete(result)
        assert buf.getvalue().rstrip(" ").endswith("\n")

    def test_multiple_results_accumulate(self):
        """Test that multiple phase_complete calls accumulate results."""
        reporter = ProgressReporter(output=io.StringIO())
        for i in range(3):
            reporter.phase_start(f"phase_{i}")
            result = PhaseResult(phase_name=f"phase_{i}", success=True, duration_s=float(i))
            reporter.phase_complete(result)
        assert len(reporter._results) == 3


# ---------------------------------------------------------------------------
# phase_parallel_complete
# ---------------------------------------------------------------------------

class TestPhaseParallelComplete:
    """Tests for phase_parallel_complete."""

    def test_increments_counter_per_result(self):
        """Test that _phase_count is incremented once per result."""
        reporter = ProgressReporter(output=io.StringIO())
        results = [
            PhaseResult(phase_name="lint", success=True, duration_s=1.0),
            PhaseResult(phase_name="typecheck", success=True, duration_s=2.0),
            PhaseResult(phase_name="test", success=True, duration_s=3.0),
        ]
        reporter.phase_parallel_complete(results)
        assert reporter._phase_count == 3

    def test_writes_parallel_marker(self):
        """Test that output contains '(parallel)' annotation."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        results = [
            PhaseResult(phase_name="lint", success=True, duration_s=1.0),
        ]
        reporter.phase_parallel_complete(results)
        assert "(parallel)" in buf.getvalue()

    def test_writes_each_result_name(self):
        """Test that each parallel result phase name appears in output."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        results = [
            PhaseResult(phase_name="lint", success=True, duration_s=1.0),
            PhaseResult(phase_name="typecheck", success=False, duration_s=2.0),
        ]
        reporter.phase_parallel_complete(results)
        output = buf.getvalue()
        assert "lint" in output
        assert "typecheck" in output

    def test_shows_done_and_fail(self):
        """Test that parallel results show done/FAIL status correctly."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        results = [
            PhaseResult(phase_name="lint", success=True, duration_s=1.0),
            PhaseResult(phase_name="typecheck", success=False, duration_s=2.0),
        ]
        reporter.phase_parallel_complete(results)
        output = buf.getvalue()
        assert "done" in output
        assert "FAIL" in output

    def test_does_not_append_to_results_list(self):
        """Test that phase_parallel_complete does NOT append to _results."""
        reporter = ProgressReporter(output=io.StringIO())
        results = [
            PhaseResult(phase_name="lint", success=True, duration_s=1.0),
        ]
        reporter.phase_parallel_complete(results)
        # phase_parallel_complete only increments count and writes output;
        # it does not call _results.append
        assert len(reporter._results) == 0

    def test_counter_labels_sequential(self):
        """Test that parallel results get sequential counter labels."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.set_total_phases(5)
        results = [
            PhaseResult(phase_name="a", success=True, duration_s=1.0),
            PhaseResult(phase_name="b", success=True, duration_s=2.0),
        ]
        reporter.phase_parallel_complete(results)
        output = buf.getvalue()
        assert "[1/5]" in output
        assert "[2/5]" in output


# ---------------------------------------------------------------------------
# build_header
# ---------------------------------------------------------------------------

class TestBuildHeader:
    """Tests for build_header."""

    def test_writes_idea(self):
        """Test that the idea text appears in the header."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_header("a todo list app")
        assert "a todo list app" in buf.getvalue()

    def test_writes_version(self):
        """Test that the version appears in the header."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_header("app", version="8.0")
        assert "v8.0" in buf.getvalue()

    def test_custom_version(self):
        """Test that a custom version string is displayed."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_header("app", version="9.1")
        assert "v9.1" in buf.getvalue()

    def test_truncates_long_idea_at_60_chars(self):
        """Test that ideas longer than 60 characters are truncated."""
        long_idea = "a" * 80
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_header(long_idea)
        output = buf.getvalue()
        # Should show first 57 chars + "..."
        assert "a" * 57 + "..." in output
        # Should NOT contain the full 80-char string
        assert "a" * 80 not in output

    def test_exactly_60_chars_not_truncated(self):
        """Test that an idea of exactly 60 characters is NOT truncated."""
        idea = "b" * 60
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_header(idea)
        output = buf.getvalue()
        assert "b" * 60 in output
        assert "..." not in output

    def test_61_chars_is_truncated(self):
        """Test that an idea of 61 characters IS truncated."""
        idea = "c" * 61
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_header(idea)
        output = buf.getvalue()
        assert "c" * 57 + "..." in output

    def test_includes_building_label(self):
        """Test that the header includes 'Building:' label."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_header("my app")
        assert "Building:" in buf.getvalue()


# ---------------------------------------------------------------------------
# build_complete
# ---------------------------------------------------------------------------

class TestBuildComplete:
    """Tests for build_complete."""

    def test_writes_build_complete(self):
        """Test that 'BUILD COMPLETE' appears in output."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_complete(url="https://example.com")
        assert "BUILD COMPLETE" in buf.getvalue()

    def test_writes_url(self):
        """Test that the URL is included in the output."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_complete(url="https://my-app.vercel.app")
        assert "https://my-app.vercel.app" in buf.getvalue()

    def test_no_url_when_none(self):
        """Test that URL line is omitted when url is None."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_complete(url=None)
        assert "URL:" not in buf.getvalue()

    def test_writes_quality_when_provided(self):
        """Test that quality rating appears in output."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_complete(url=None, quality="A")
        output = buf.getvalue()
        assert "Quality: A" in output

    def test_no_quality_when_none(self):
        """Test that quality line is omitted when not provided."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_complete(url=None, quality=None)
        assert "Quality:" not in buf.getvalue()

    def test_includes_test_detail_from_results(self):
        """Test that test phase details appear in the summary."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        result = PhaseResult(
            phase_name="Run tests", success=True, duration_s=5.0, detail="14/14 passed"
        )
        reporter._results.append(result)
        reporter.build_complete(url=None)
        assert "Tests: 14/14 passed" in buf.getvalue()

    def test_includes_audit_detail_from_results(self):
        """Test that audit phase details appear in the summary as Spec."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        result = PhaseResult(
            phase_name="Spec audit", success=True, duration_s=3.0, detail="9/9 criteria met"
        )
        reporter._results.append(result)
        reporter.build_complete(url=None)
        assert "Spec: 9/9 criteria met" in buf.getvalue()

    def test_skips_non_test_non_audit_results(self):
        """Test that non-test, non-audit results do not produce summary lines."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        result = PhaseResult(
            phase_name="scaffold", success=True, duration_s=1.0, detail="created 5 files"
        )
        reporter._results.append(result)
        reporter.build_complete(url=None)
        output = buf.getvalue()
        assert "Tests:" not in output
        assert "Spec:" not in output

    def test_writes_formatted_duration(self):
        """Test that build_complete outputs the total duration."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        # The duration will be based on time.time() - _start_time,
        # so it should contain some duration string ending in 's'
        reporter.build_complete(url=None)
        output = buf.getvalue()
        assert "BUILD COMPLETE" in output
        # Duration appears right after BUILD COMPLETE
        assert "s" in output


# ---------------------------------------------------------------------------
# build_failed
# ---------------------------------------------------------------------------

class TestBuildFailed:
    """Tests for build_failed."""

    def test_writes_build_failed(self):
        """Test that 'BUILD FAILED' appears in output."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_failed("out of memory")
        assert "BUILD FAILED" in buf.getvalue()

    def test_writes_reason(self):
        """Test that the failure reason is included."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_failed("deployment timed out")
        output = buf.getvalue()
        assert "Reason: deployment timed out" in output

    def test_writes_duration(self):
        """Test that build_failed includes a duration."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_failed("error")
        output = buf.getvalue()
        # Should have some duration marker
        assert "s" in output


# ---------------------------------------------------------------------------
# log (verbose mode)
# ---------------------------------------------------------------------------

class TestLog:
    """Tests for the log method."""

    def test_writes_when_verbose(self):
        """Test that log writes message when verbose is True."""
        buf = io.StringIO()
        reporter = ProgressReporter(verbose=True, output=buf)
        reporter.log("debug info here")
        assert "debug info here" in buf.getvalue()

    def test_silent_when_not_verbose(self):
        """Test that log produces no output when verbose is False."""
        buf = io.StringIO()
        reporter = ProgressReporter(verbose=False, output=buf)
        reporter.log("should not appear")
        assert buf.getvalue() == ""

    def test_message_prefixed_with_arrow(self):
        """Test that verbose log messages are prefixed with '  > '."""
        buf = io.StringIO()
        reporter = ProgressReporter(verbose=True, output=buf)
        reporter.log("checking files")
        assert "  > checking files" in buf.getvalue()

    def test_log_ends_with_newline(self):
        """Test that verbose log messages end with a newline."""
        buf = io.StringIO()
        reporter = ProgressReporter(verbose=True, output=buf)
        reporter.log("hello")
        assert buf.getvalue().endswith("\n")


# ---------------------------------------------------------------------------
# results property
# ---------------------------------------------------------------------------

class TestResultsProperty:
    """Tests for the results property."""

    def test_returns_empty_list_initially(self):
        """Test that results returns an empty list when no phases completed."""
        reporter = ProgressReporter(output=io.StringIO())
        assert reporter.results == []

    def test_returns_copy_not_reference(self):
        """Test that results returns a copy, not the internal list."""
        reporter = ProgressReporter(output=io.StringIO())
        result = PhaseResult(phase_name="a", success=True, duration_s=1.0)
        reporter._results.append(result)
        returned = reporter.results
        returned.append(PhaseResult(phase_name="b", success=True, duration_s=2.0))
        # Mutating the returned list should not affect the internal list
        assert len(reporter._results) == 1
        assert len(reporter.results) == 1

    def test_contains_all_completed_results(self):
        """Test that results contains all appended phase results."""
        reporter = ProgressReporter(output=io.StringIO())
        for i in range(4):
            result = PhaseResult(phase_name=f"phase_{i}", success=True, duration_s=float(i))
            reporter.phase_complete(result)
        assert len(reporter.results) == 4
        assert reporter.results[0].phase_name == "phase_0"
        assert reporter.results[3].phase_name == "phase_3"


# ---------------------------------------------------------------------------
# total_duration_s property
# ---------------------------------------------------------------------------

class TestTotalDurationS:
    """Tests for the total_duration_s property."""

    def test_returns_positive_value(self):
        """Test that total_duration_s is a positive number."""
        reporter = ProgressReporter(output=io.StringIO())
        assert reporter.total_duration_s >= 0

    def test_increases_over_time(self):
        """Test that total_duration_s increases as time passes."""
        reporter = ProgressReporter(output=io.StringIO())
        d1 = reporter.total_duration_s
        time.sleep(0.05)
        d2 = reporter.total_duration_s
        assert d2 > d1

    def test_is_float(self):
        """Test that total_duration_s returns a float."""
        reporter = ProgressReporter(output=io.StringIO())
        assert isinstance(reporter.total_duration_s, float)


# ---------------------------------------------------------------------------
# phase_skipped (v9.1)
# ---------------------------------------------------------------------------

class TestPhaseSkipped:
    """Tests for the phase_skipped method (v9.1 crash recovery)."""

    def test_increments_counter(self):
        """phase_skipped should increment the phase counter."""
        reporter = ProgressReporter(output=io.StringIO())
        reporter.phase_skipped("Analysis")
        assert reporter._phase_count == 1

    def test_writes_skipped_label(self):
        """Output should contain 'skipped' and the phase name."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_skipped("Analysis")
        output = buf.getvalue()
        assert "skipped" in output
        assert "Analysis" in output

    def test_includes_detail(self):
        """When detail is provided, it should appear in the output."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_skipped("Analysis", "stack: nextjs-supabase")
        assert "stack: nextjs-supabase" in buf.getvalue()

    def test_no_detail_no_parens(self):
        """When detail is empty, no parentheses should appear."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_skipped("Enrich")
        output = buf.getvalue()
        assert "(" not in output

    def test_counter_label_correct(self):
        """Counter label should reflect current phase number."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.set_total_phases(9)
        reporter.phase_skipped("Analysis")
        assert "[1/9]" in buf.getvalue()

    def test_multiple_skips_increment(self):
        """Multiple phase_skipped calls should increment counter correctly."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.set_total_phases(9)
        reporter.phase_skipped("Analysis")
        reporter.phase_skipped("Design")
        reporter.phase_skipped("Review")
        assert reporter._phase_count == 3
        assert "[3/9]" in buf.getvalue()

    def test_output_ends_with_newline(self):
        """Output should end with a newline."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.phase_skipped("Test")
        assert buf.getvalue().endswith("\n")


# ---------------------------------------------------------------------------
# build_resume_header (v9.1)
# ---------------------------------------------------------------------------

class TestBuildResumeHeader:
    """Tests for build_resume_header (v9.1 crash recovery)."""

    def test_writes_resuming_label(self):
        """Output should contain 'Resuming:' instead of 'Building:'."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_resume_header("Todo app", "build")
        output = buf.getvalue()
        assert "Resuming:" in output
        assert "Todo app" in output

    def test_writes_resume_phase(self):
        """Output should show which phase we're resuming from."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_resume_header("Todo app", "build")
        assert "Resuming from: build" in buf.getvalue()

    def test_truncates_long_idea(self):
        """Long ideas should be truncated at 60 characters."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        long_idea = "x" * 80
        reporter.build_resume_header(long_idea, "analysis")
        output = buf.getvalue()
        assert "x" * 57 + "..." in output
        assert "x" * 80 not in output

    def test_exactly_60_not_truncated(self):
        """An idea of exactly 60 characters should not be truncated."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        idea = "y" * 60
        reporter.build_resume_header(idea, "deploy")
        output = buf.getvalue()
        assert "y" * 60 in output
        assert "..." not in output

    def test_includes_version(self):
        """Version should appear in the header."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_resume_header("app", "build", version="9.1")
        assert "v9.1" in buf.getvalue()

    def test_does_not_say_building(self):
        """Resume header should NOT contain 'Building:'."""
        buf = io.StringIO()
        reporter = ProgressReporter(output=buf)
        reporter.build_resume_header("app", "build")
        assert "Building:" not in buf.getvalue()
