"""Build memory for Product Agent v8.0.

Tracks every build's decisions and outcomes in an append-only log.
Queries similar past builds to inject context into new builds.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


HISTORY_DIR = ".agent_history"
BUILDS_FILE = "builds.jsonl"


@dataclass
class BuildRecord:
    """Record of a single build."""
    id: str
    idea: str
    stack: str
    mode: str
    domain: str | None = None
    phases: dict | None = None
    total_duration_s: float = 0.0
    outcome: str = "unknown"  # success | failed | partial
    url: str | None = None
    quality: str | None = None
    test_count: str | None = None
    spec_coverage: str | None = None
    timestamp: str | None = None


class BuildHistory:
    """Manages build history for learning from past builds."""

    def __init__(self, project_root: str | Path | None = None):
        """Initialize build history.

        Args:
            project_root: Root directory for the history file.
                          Defaults to current directory.
        """
        root = Path(project_root) if project_root else Path(".")
        self.history_dir = root / HISTORY_DIR
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.builds_file = self.history_dir / BUILDS_FILE

    def record_build(self, record: BuildRecord) -> None:
        """Append a build record to the history log."""
        if not record.timestamp:
            record.timestamp = datetime.now().isoformat()
        if not record.id:
            record.id = datetime.now().strftime("%Y%m%d_%H%M%S")

        with open(self.builds_file, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def get_all_builds(self) -> list[BuildRecord]:
        """Load all build records."""
        if not self.builds_file.exists():
            return []

        records = []
        for line in self.builds_file.read_text().strip().split("\n"):
            if line.strip():
                data = json.loads(line)
                records.append(BuildRecord(**data))
        return records

    def find_similar_builds(
        self,
        idea: str,
        limit: int = 3,
    ) -> list[BuildRecord]:
        """Find builds with similar ideas.

        Uses simple keyword matching to find relevant past builds.
        """
        all_builds = self.get_all_builds()
        if not all_builds:
            return []

        idea_words = set(idea.lower().split())

        scored: list[tuple[float, BuildRecord]] = []
        for record in all_builds:
            record_words = set(record.idea.lower().split())
            # Jaccard similarity
            intersection = idea_words & record_words
            union = idea_words | record_words
            score = len(intersection) / len(union) if union else 0
            if score > 0.1:  # Minimum threshold
                scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [record for _, record in scored[:limit]]

    def format_similar_builds(self, builds: list[BuildRecord]) -> str:
        """Format similar builds as context for injection."""
        if not builds:
            return ""

        parts = ["## Similar Past Builds"]
        for i, build in enumerate(builds, 1):
            parts.append(f"\n### Build {i}: {build.idea[:80]}")
            parts.append(f"- Stack: {build.stack}")
            parts.append(f"- Outcome: {build.outcome}")
            if build.quality:
                parts.append(f"- Quality: {build.quality}")
            if build.test_count:
                parts.append(f"- Tests: {build.test_count}")
            parts.append(f"- Duration: {build.total_duration_s:.0f}s")

        return "\n".join(parts)

    def get_success_rate(self) -> tuple[int, int]:
        """Get the overall success rate.

        Returns:
            Tuple of (successful_builds, total_builds)
        """
        builds = self.get_all_builds()
        successful = sum(1 for b in builds if b.outcome == "success")
        return successful, len(builds)

    def get_stack_stats(self) -> dict[str, dict]:
        """Get per-stack statistics."""
        builds = self.get_all_builds()
        stats: dict[str, dict] = {}

        for build in builds:
            if build.stack not in stats:
                stats[build.stack] = {"total": 0, "success": 0, "avg_duration": 0.0}
            stats[build.stack]["total"] += 1
            if build.outcome == "success":
                stats[build.stack]["success"] += 1
            stats[build.stack]["avg_duration"] += build.total_duration_s

        for stack in stats:
            total = stats[stack]["total"]
            if total > 0:
                stats[stack]["avg_duration"] /= total

        return stats
