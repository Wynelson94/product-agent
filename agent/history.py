"""Build memory for Product Agent.

Tracks every build's decisions and outcomes in an append-only log.
Queries similar past builds to inject context and failure lessons into new builds.

v12.4: Added file locking (fcntl.flock) for concurrent write safety and
JSONL rotation to prevent unbounded growth. MAX_BUILD_RECORDS controls
the rotation threshold (default 500).
"""

import fcntl
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


HISTORY_DIR = ".agent_history"
BUILDS_FILE = "builds.jsonl"

# Maximum number of build records to retain. When exceeded, the oldest
# records are dropped during the next write. 500 records ≈ 250KB on disk,
# which loads in <50ms even on slow storage.
MAX_BUILD_RECORDS = 500


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
    failure_reasons: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)


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
        """Append a build record to the history log.

        Uses fcntl.flock() for exclusive locking so concurrent builds don't
        interleave JSONL lines. Also triggers rotation when the file exceeds
        MAX_BUILD_RECORDS to prevent unbounded growth.
        """
        if not record.timestamp:
            record.timestamp = datetime.now().isoformat()
        if not record.id:
            record.id = datetime.now().strftime("%Y%m%d_%H%M%S")

        line = json.dumps(asdict(record)) + "\n"

        with open(self.builds_file, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(line)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

        # Rotate if the file has grown too large
        self._rotate_if_needed()

    def _rotate_if_needed(self) -> None:
        """Drop oldest records when the file exceeds MAX_BUILD_RECORDS.

        Reads all lines, keeps the most recent MAX_BUILD_RECORDS, and
        atomically rewrites the file. Uses exclusive lock during rewrite.
        """
        if not self.builds_file.exists():
            return

        lines = self.builds_file.read_text().strip().split("\n")
        lines = [l for l in lines if l.strip()]

        if len(lines) <= MAX_BUILD_RECORDS:
            return

        # Keep the most recent records (bottom of the file = newest)
        kept = lines[-MAX_BUILD_RECORDS:]

        # Atomic rewrite with exclusive lock
        with open(self.builds_file, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write("\n".join(kept) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def get_all_builds(self) -> list[BuildRecord]:
        """Load all build records.

        Uses a shared lock so concurrent reads don't conflict with writes.
        Skips malformed lines instead of crashing.
        """
        if not self.builds_file.exists():
            return []

        records = []
        with open(self.builds_file, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                content = f.read()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

        for line in content.strip().split("\n"):
            if line.strip():
                try:
                    data = json.loads(line)
                    records.append(BuildRecord(**data))
                except (json.JSONDecodeError, TypeError):
                    # Skip malformed lines — don't crash on corrupted history
                    continue
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
            # Jaccard similarity: |intersection| / |union|. Ranges 0.0 (no overlap)
            # to 1.0 (identical). Simple but effective for short product descriptions.
            intersection = idea_words & record_words
            union = idea_words | record_words
            score = len(intersection) / len(union) if union else 0
            if score > 0.1:  # Below 10% similarity = not meaningfully related
                scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [record for _, record in scored[:limit]]

    def get_relevant_lessons(
        self,
        idea: str,
        stack: str | None = None,
        limit: int = 5,
    ) -> list[str]:
        """Find lessons from similar past builds.

        Searches failure_reasons and lessons from builds that match by
        idea similarity or stack. Returns deduplicated lessons.

        Args:
            idea: The current product idea
            stack: Optional stack ID to filter by
            limit: Maximum number of lessons to return

        Returns:
            List of lesson strings relevant to this build
        """
        all_builds = self.get_all_builds()
        if not all_builds:
            return []

        idea_words = set(idea.lower().split())
        lessons: list[tuple[float, str]] = []

        for record in all_builds:
            if not record.lessons and not record.failure_reasons:
                continue

            # Score by idea similarity + stack match
            record_words = set(record.idea.lower().split())
            intersection = idea_words & record_words
            union = idea_words | record_words
            score = len(intersection) / len(union) if union else 0

            # Boost same-stack matches by 0.3 so stack-specific lessons rank higher.
            # This means a low-similarity build (0.05) on the same stack (0.05+0.3=0.35)
            # will rank above a moderate-similarity build (0.2) on a different stack.
            if stack and record.stack == stack:
                score += 0.3

            # Re-check threshold after stack boost — a same-stack build with low
            # idea similarity may now exceed 0.1 and be included.
            if score < 0.1:
                continue

            for lesson in record.lessons:
                lessons.append((score, lesson))
            for reason in record.failure_reasons:
                lessons.append((score, f"Previous failure: {reason}"))

        # Deduplicate and sort by relevance
        seen: set[str] = set()
        unique: list[tuple[float, str]] = []
        for score, lesson in sorted(lessons, key=lambda x: x[0], reverse=True):
            if lesson not in seen:
                seen.add(lesson)
                unique.append((score, lesson))

        return [lesson for _, lesson in unique[:limit]]

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
            if build.lessons:
                parts.append("- Lessons learned:")
                for lesson in build.lessons[:3]:
                    parts.append(f"  - {lesson}")
            if build.failure_reasons:
                parts.append("- Failure reasons:")
                for reason in build.failure_reasons[:3]:
                    parts.append(f"  - {reason}")

        return "\n".join(parts)

    def format_lessons(self, lessons: list[str]) -> str:
        """Format lessons for injection into builder prompts.

        Args:
            lessons: List of lesson strings

        Returns:
            Formatted markdown section, or empty string if no lessons
        """
        if not lessons:
            return ""

        parts = ["## Lessons from Past Builds"]
        parts.append("Avoid these known issues:")
        for lesson in lessons:
            parts.append(f"- {lesson}")
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
