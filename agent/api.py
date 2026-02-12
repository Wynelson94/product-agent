"""Public API for Product Agent v8.0.

Clean interface for programmatic use. Designed to eventually become
a Claude Code plugin or MCP server.

Usage:
    from agent.api import build, BuildConfig

    result = await build(
        "Create a marketplace for vintage guitars",
        config=BuildConfig(stack="nextjs-prisma"),
    )
    print(result.url)
    print(result.quality)
"""

from pathlib import Path
from typing import Callable

from .orchestrator import (
    BuildConfig,
    BuildResult,
    build_product as _build_product,
)
from .history import BuildHistory, BuildRecord
from .quality import compute_quality_score, format_quality_report, QualityReport
from .progress import PhaseResult


async def build(
    idea: str,
    project_dir: str | Path = "./projects/new-product",
    config: BuildConfig | None = None,
    on_progress: Callable[[PhaseResult], None] | None = None,
) -> BuildResult:
    """Build a product from an idea.

    This is the primary public API. One prompt in, production app out.

    Args:
        idea: Plain English description of what to build
        project_dir: Where to create the project (default: ./projects/new-product)
        config: Build configuration (stack, mode, flags)
        on_progress: Optional callback for real-time phase updates

    Returns:
        BuildResult with URL, quality score, test results, and metrics

    Example:
        result = await build("Build a todo app with real-time sync")
        print(result.url)      # https://todo-app.vercel.app
        print(result.quality)  # A- (92%)
    """
    cfg = config or BuildConfig()
    project_path = Path(project_dir).resolve()

    # Check for similar past builds
    history = BuildHistory(project_path.parent)
    similar = history.find_similar_builds(idea)

    # Run the build
    result = await _build_product(idea, project_path, cfg)

    # Record build in history
    record = BuildRecord(
        id="",  # Auto-generated
        idea=idea,
        stack=cfg.stack or "auto",
        mode=cfg.mode,
        total_duration_s=result.duration_s,
        outcome="success" if result.success else "failed",
        url=result.url,
        quality=result.quality,
        test_count=result.test_count,
        spec_coverage=result.spec_coverage,
    )
    history.record_build(record)

    return result


# Re-export for convenience
__all__ = [
    "build",
    "BuildConfig",
    "BuildResult",
    "BuildHistory",
    "BuildRecord",
    "QualityReport",
    "compute_quality_score",
    "format_quality_report",
    "PhaseResult",
]
