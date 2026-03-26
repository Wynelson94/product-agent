"""Tests for the public API surface (agent/api.py)."""

from agent.api import (
    build,
    BuildConfig,
    BuildResult,
    BuildHistory,
    BuildRecord,
    QualityReport,
    compute_quality_score,
    format_quality_report,
    PhaseResult,
)


class TestPublicAPIExports:
    """Verify all public API symbols are importable and correct types."""

    def test_build_is_async_callable(self):
        """build() should be an async function."""
        import inspect
        assert inspect.iscoroutinefunction(build)

    def test_build_config_is_dataclass(self):
        """BuildConfig should be instantiable with defaults."""
        cfg = BuildConfig()
        assert cfg.stack is None or isinstance(cfg.stack, str)

    def test_build_result_has_expected_fields(self):
        """BuildResult should have success, url, quality fields."""
        result = BuildResult(success=True, url="https://test.vercel.app", quality="A (95%)")
        assert result.success is True
        assert result.url == "https://test.vercel.app"
        assert result.quality == "A (95%)"

    def test_quality_report_is_importable(self):
        """QualityReport should be importable from the public API."""
        assert QualityReport is not None

    def test_compute_quality_score_is_callable(self):
        """compute_quality_score should be a callable function."""
        assert callable(compute_quality_score)

    def test_format_quality_report_is_callable(self):
        """format_quality_report should be a callable function."""
        assert callable(format_quality_report)

    def test_phase_result_is_importable(self):
        """PhaseResult should be importable and instantiable."""
        pr = PhaseResult(phase_name="test", success=True, duration_s=1.0)
        assert pr.phase_name == "test"

    def test_all_exports_listed(self):
        """__all__ should list all public symbols."""
        from agent import api
        assert hasattr(api, "__all__")
        expected = {"build", "BuildConfig", "BuildResult", "BuildHistory",
                    "BuildRecord", "QualityReport", "compute_quality_score",
                    "format_quality_report", "PhaseResult"}
        assert set(api.__all__) == expected
