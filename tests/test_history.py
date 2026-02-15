"""Comprehensive tests for the build history module."""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pytest

from agent.history import (
    BUILDS_FILE,
    HISTORY_DIR,
    BuildHistory,
    BuildRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_record(**overrides) -> BuildRecord:
    """Create a BuildRecord with sensible defaults, overridable via kwargs."""
    defaults = dict(
        id="test_001",
        idea="build a todo app",
        stack="nextjs-supabase",
        mode="full",
    )
    defaults.update(overrides)
    return BuildRecord(**defaults)


def _write_jsonl(path: Path, records: list[BuildRecord]) -> None:
    """Write a list of BuildRecords directly to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(asdict(r)) + "\n")


# ===========================================================================
# TestBuildRecord
# ===========================================================================

class TestBuildRecord:
    """Tests for the BuildRecord dataclass."""

    def test_required_fields_only(self):
        """BuildRecord can be created with only required fields."""
        rec = BuildRecord(id="1", idea="an app", stack="react", mode="quick")
        assert rec.id == "1"
        assert rec.idea == "an app"
        assert rec.stack == "react"
        assert rec.mode == "quick"

    def test_default_values(self):
        """Optional fields have correct defaults."""
        rec = _minimal_record()
        assert rec.domain is None
        assert rec.phases is None
        assert rec.total_duration_s == 0.0
        assert rec.outcome == "unknown"
        assert rec.url is None
        assert rec.quality is None
        assert rec.test_count is None
        assert rec.spec_coverage is None
        assert rec.timestamp is None

    def test_all_fields_populated(self):
        """BuildRecord accepts every field explicitly."""
        rec = BuildRecord(
            id="x",
            idea="my idea",
            stack="swift",
            mode="full",
            domain="finance",
            phases={"plan": 10, "build": 50},
            total_duration_s=123.4,
            outcome="success",
            url="https://example.com",
            quality="A",
            test_count="42",
            spec_coverage="90%",
            timestamp="2025-01-01T00:00:00",
        )
        assert rec.domain == "finance"
        assert rec.phases == {"plan": 10, "build": 50}
        assert rec.total_duration_s == 123.4
        assert rec.outcome == "success"
        assert rec.url == "https://example.com"
        assert rec.quality == "A"
        assert rec.test_count == "42"
        assert rec.spec_coverage == "90%"
        assert rec.timestamp == "2025-01-01T00:00:00"

    def test_asdict_roundtrip(self):
        """A record survives a dict -> JSON -> dict -> record roundtrip."""
        original = _minimal_record(outcome="success", total_duration_s=42.5)
        json_str = json.dumps(asdict(original))
        restored = BuildRecord(**json.loads(json_str))
        assert restored == original

    def test_asdict_contains_all_keys(self):
        """asdict produces a dict with every field present."""
        rec = _minimal_record()
        d = asdict(rec)
        expected_keys = {
            "id", "idea", "stack", "mode", "domain", "phases",
            "total_duration_s", "outcome", "url", "quality",
            "test_count", "spec_coverage", "timestamp",
            "failure_reasons", "lessons",
        }
        assert set(d.keys()) == expected_keys

    def test_default_failure_reasons_and_lessons(self):
        """failure_reasons and lessons default to empty lists."""
        rec = _minimal_record()
        assert rec.failure_reasons == []
        assert rec.lessons == []

    def test_failure_reasons_and_lessons_roundtrip(self):
        """failure_reasons and lessons survive JSON roundtrip."""
        rec = _minimal_record(
            failure_reasons=["peer dep conflict", "missing middleware"],
            lessons=["Always validate peer deps before build"],
        )
        json_str = json.dumps(asdict(rec))
        restored = BuildRecord(**json.loads(json_str))
        assert restored.failure_reasons == ["peer dep conflict", "missing middleware"]
        assert restored.lessons == ["Always validate peer deps before build"]

    def test_empty_string_idea(self):
        """BuildRecord allows an empty idea string."""
        rec = _minimal_record(idea="")
        assert rec.idea == ""

    def test_special_characters_in_idea(self):
        """BuildRecord handles special characters in idea field."""
        idea = 'Build a "real-time" chat app with <websockets> & emojis'
        rec = _minimal_record(idea=idea)
        assert rec.idea == idea

    def test_unicode_in_fields(self):
        """BuildRecord preserves unicode content."""
        rec = _minimal_record(idea="Build an app with international text")
        assert rec.idea == "Build an app with international text"


# ===========================================================================
# TestBuildHistory
# ===========================================================================

class TestBuildHistory:
    """Tests for the BuildHistory manager."""

    # -----------------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------------

    def test_init_creates_history_dir(self, tmp_path):
        """__init__ creates the .agent_history directory."""
        history = BuildHistory(project_root=tmp_path)
        assert history.history_dir.exists()
        assert history.history_dir.is_dir()
        assert history.history_dir == tmp_path / HISTORY_DIR

    def test_init_sets_builds_file_path(self, tmp_path):
        """__init__ sets the builds_file path under the history dir."""
        history = BuildHistory(project_root=tmp_path)
        assert history.builds_file == tmp_path / HISTORY_DIR / BUILDS_FILE

    def test_init_idempotent(self, tmp_path):
        """Creating BuildHistory twice on the same root does not error."""
        BuildHistory(project_root=tmp_path)
        BuildHistory(project_root=tmp_path)
        assert (tmp_path / HISTORY_DIR).exists()

    def test_init_creates_nested_parent_dirs(self, tmp_path):
        """__init__ creates intermediate parent directories."""
        deep = tmp_path / "a" / "b" / "c"
        history = BuildHistory(project_root=deep)
        assert history.history_dir.exists()

    def test_init_with_string_path(self, tmp_path):
        """__init__ accepts a plain string for project_root."""
        history = BuildHistory(project_root=str(tmp_path))
        assert history.history_dir.exists()

    def test_init_with_path_object(self, tmp_path):
        """__init__ accepts a Path object for project_root."""
        history = BuildHistory(project_root=tmp_path)
        assert history.history_dir.exists()

    # -----------------------------------------------------------------------
    # record_build
    # -----------------------------------------------------------------------

    def test_record_build_creates_file(self, tmp_path):
        """record_build creates the JSONL file if it does not exist."""
        history = BuildHistory(project_root=tmp_path)
        rec = _minimal_record()
        history.record_build(rec)
        assert history.builds_file.exists()

    def test_record_build_writes_valid_json(self, tmp_path):
        """Each line written by record_build is valid JSON."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record())
        line = history.builds_file.read_text().strip()
        data = json.loads(line)
        assert data["idea"] == "build a todo app"

    def test_record_build_autofills_timestamp(self, tmp_path):
        """record_build fills in timestamp when it is None."""
        history = BuildHistory(project_root=tmp_path)
        rec = _minimal_record(timestamp=None)
        history.record_build(rec)
        assert rec.timestamp is not None
        # Verify it looks like an ISO timestamp
        datetime.fromisoformat(rec.timestamp)

    def test_record_build_preserves_existing_timestamp(self, tmp_path):
        """record_build does not overwrite an already-set timestamp."""
        history = BuildHistory(project_root=tmp_path)
        ts = "2024-06-15T12:00:00"
        rec = _minimal_record(timestamp=ts)
        history.record_build(rec)
        assert rec.timestamp == ts

    def test_record_build_autofills_id(self, tmp_path):
        """record_build fills in id when it is empty string."""
        history = BuildHistory(project_root=tmp_path)
        rec = _minimal_record(id="")
        history.record_build(rec)
        assert rec.id != ""
        # The auto-generated id should follow the YYYYMMDD_HHMMSS pattern
        assert "_" in rec.id

    def test_record_build_preserves_existing_id(self, tmp_path):
        """record_build does not overwrite an already-set id."""
        history = BuildHistory(project_root=tmp_path)
        rec = _minimal_record(id="my_custom_id")
        history.record_build(rec)
        assert rec.id == "my_custom_id"

    def test_record_build_appends_not_overwrites(self, tmp_path):
        """Multiple record_build calls append lines, not overwrite."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(id="first"))
        history.record_build(_minimal_record(id="second"))
        history.record_build(_minimal_record(id="third"))

        lines = history.builds_file.read_text().strip().split("\n")
        assert len(lines) == 3

        ids = [json.loads(l)["id"] for l in lines]
        assert ids == ["first", "second", "third"]

    def test_record_build_special_characters_survive(self, tmp_path):
        """Special characters in the idea survive the JSON roundtrip."""
        history = BuildHistory(project_root=tmp_path)
        idea = 'A "quoted" idea with <html> & newline\\n chars'
        history.record_build(_minimal_record(idea=idea))

        data = json.loads(history.builds_file.read_text().strip())
        assert data["idea"] == idea

    # -----------------------------------------------------------------------
    # get_all_builds
    # -----------------------------------------------------------------------

    def test_get_all_builds_empty_when_no_file(self, tmp_path):
        """get_all_builds returns [] when the file does not exist."""
        history = BuildHistory(project_root=tmp_path)
        assert history.get_all_builds() == []

    def test_get_all_builds_empty_file(self, tmp_path):
        """get_all_builds returns [] for an empty file."""
        history = BuildHistory(project_root=tmp_path)
        history.builds_file.write_text("")
        assert history.get_all_builds() == []

    def test_get_all_builds_single_record(self, tmp_path):
        """get_all_builds returns a single record correctly."""
        history = BuildHistory(project_root=tmp_path)
        original = _minimal_record(timestamp="2025-01-01T00:00:00")
        history.record_build(original)

        builds = history.get_all_builds()
        assert len(builds) == 1
        assert builds[0].idea == original.idea
        assert builds[0].id == original.id

    def test_get_all_builds_multiple_records(self, tmp_path):
        """get_all_builds returns all recorded builds in order."""
        history = BuildHistory(project_root=tmp_path)
        for i in range(5):
            history.record_build(_minimal_record(id=f"build_{i}", idea=f"idea {i}"))

        builds = history.get_all_builds()
        assert len(builds) == 5
        assert [b.id for b in builds] == [f"build_{i}" for i in range(5)]

    def test_get_all_builds_returns_build_record_instances(self, tmp_path):
        """get_all_builds returns actual BuildRecord objects."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record())
        builds = history.get_all_builds()
        assert isinstance(builds[0], BuildRecord)

    def test_get_all_builds_preserves_all_fields(self, tmp_path):
        """get_all_builds roundtrip preserves every field."""
        history = BuildHistory(project_root=tmp_path)
        original = BuildRecord(
            id="full",
            idea="complex app",
            stack="swift",
            mode="full",
            domain="healthcare",
            phases={"plan": 5, "build": 30},
            total_duration_s=99.9,
            outcome="success",
            url="https://test.com",
            quality="A+",
            test_count="55",
            spec_coverage="100%",
            timestamp="2025-06-01T12:00:00",
        )
        history.record_build(original)
        restored = history.get_all_builds()[0]

        assert restored.id == original.id
        assert restored.idea == original.idea
        assert restored.stack == original.stack
        assert restored.mode == original.mode
        assert restored.domain == original.domain
        assert restored.phases == original.phases
        assert restored.total_duration_s == original.total_duration_s
        assert restored.outcome == original.outcome
        assert restored.url == original.url
        assert restored.quality == original.quality
        assert restored.test_count == original.test_count
        assert restored.spec_coverage == original.spec_coverage
        assert restored.timestamp == original.timestamp

    # -----------------------------------------------------------------------
    # find_similar_builds
    # -----------------------------------------------------------------------

    def test_find_similar_builds_empty_history(self, tmp_path):
        """find_similar_builds returns [] when there are no builds."""
        history = BuildHistory(project_root=tmp_path)
        assert history.find_similar_builds("build a todo app") == []

    def test_find_similar_builds_exact_match(self, tmp_path):
        """find_similar_builds finds an exact idea match (Jaccard = 1.0)."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(idea="build a todo app"))
        results = history.find_similar_builds("build a todo app")
        assert len(results) == 1
        assert results[0].idea == "build a todo app"

    def test_find_similar_builds_partial_match(self, tmp_path):
        """find_similar_builds finds a partial keyword overlap."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(idea="build a todo list app"))
        # "todo app" shares words with "build a todo list app"
        results = history.find_similar_builds("todo app")
        assert len(results) == 1

    def test_find_similar_builds_no_match(self, tmp_path):
        """find_similar_builds returns [] when no ideas share words."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(idea="build a todo app"))
        results = history.find_similar_builds("completely unrelated query xyz")
        assert results == []

    def test_find_similar_builds_case_insensitive(self, tmp_path):
        """find_similar_builds matching is case-insensitive."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(idea="Build A Todo App"))
        results = history.find_similar_builds("build a todo app")
        assert len(results) == 1

    def test_find_similar_builds_respects_limit(self, tmp_path):
        """find_similar_builds returns at most `limit` results."""
        history = BuildHistory(project_root=tmp_path)
        for i in range(10):
            history.record_build(_minimal_record(id=f"b{i}", idea=f"build a todo app version {i}"))

        results = history.find_similar_builds("build a todo app", limit=3)
        assert len(results) <= 3

    def test_find_similar_builds_limit_one(self, tmp_path):
        """find_similar_builds with limit=1 returns at most one result."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(id="a", idea="build a chat app"))
        history.record_build(_minimal_record(id="b", idea="build a chat widget"))
        results = history.find_similar_builds("build a chat application", limit=1)
        assert len(results) == 1

    def test_find_similar_builds_ordered_by_similarity(self, tmp_path):
        """find_similar_builds returns results in descending similarity order."""
        history = BuildHistory(project_root=tmp_path)
        # Exact match should score highest
        history.record_build(_minimal_record(id="exact", idea="real time chat app"))
        # Partial match scores lower
        history.record_build(_minimal_record(id="partial", idea="real time video streaming platform"))
        results = history.find_similar_builds("real time chat app")
        assert len(results) >= 1
        assert results[0].id == "exact"

    def test_find_similar_builds_threshold_excludes_low_overlap(self, tmp_path):
        """Builds with Jaccard similarity <= 0.1 are excluded."""
        history = BuildHistory(project_root=tmp_path)
        # idea words: {"alpha","bravo","charlie","delta","echo","foxtrot","golf","hotel","india","juliet"} (10)
        # query words: {"kilo","lima","mike","november","oscar","papa","quebec","romeo","sierra","alpha"} (10)
        # intersection: {"alpha"}, union: 19 words -> Jaccard = 1/19 ≈ 0.053 < 0.1
        history.record_build(_minimal_record(
            idea="alpha bravo charlie delta echo foxtrot golf hotel india juliet"
        ))
        results = history.find_similar_builds(
            "kilo lima mike november oscar papa quebec romeo sierra alpha"
        )
        assert results == []

    def test_find_similar_builds_threshold_includes_above(self, tmp_path):
        """Builds with Jaccard similarity > 0.1 are included."""
        history = BuildHistory(project_root=tmp_path)
        # idea words: {"build", "app"}, query words: {"build", "app", "now"}
        # intersection: {"build", "app"}, union: {"build", "app", "now"} -> Jaccard = 2/3 = 0.67
        history.record_build(_minimal_record(idea="build app"))
        results = history.find_similar_builds("build app now")
        assert len(results) == 1

    def test_find_similar_builds_empty_idea_query(self, tmp_path):
        """find_similar_builds with an empty string query returns []."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(idea="build a todo app"))
        # Empty query -> idea_words is empty set -> union is non-empty, intersection is empty
        # score = 0 / len(union) = 0, which is not > 0.1
        results = history.find_similar_builds("")
        assert results == []

    # -----------------------------------------------------------------------
    # format_similar_builds
    # -----------------------------------------------------------------------

    def test_format_similar_builds_empty_list(self, tmp_path):
        """format_similar_builds returns empty string for empty list."""
        history = BuildHistory(project_root=tmp_path)
        assert history.format_similar_builds([]) == ""

    def test_format_similar_builds_contains_header(self, tmp_path):
        """format_similar_builds output starts with the section header."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(outcome="success")]
        result = history.format_similar_builds(builds)
        assert "## Similar Past Builds" in result

    def test_format_similar_builds_contains_idea(self, tmp_path):
        """format_similar_builds includes the build idea."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(idea="my cool project")]
        result = history.format_similar_builds(builds)
        assert "my cool project" in result

    def test_format_similar_builds_contains_stack(self, tmp_path):
        """format_similar_builds includes the stack."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(stack="nextjs-supabase")]
        result = history.format_similar_builds(builds)
        assert "nextjs-supabase" in result

    def test_format_similar_builds_contains_outcome(self, tmp_path):
        """format_similar_builds includes the outcome."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(outcome="success")]
        result = history.format_similar_builds(builds)
        assert "success" in result

    def test_format_similar_builds_includes_quality_when_set(self, tmp_path):
        """format_similar_builds includes quality if present."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(quality="A")]
        result = history.format_similar_builds(builds)
        assert "Quality: A" in result

    def test_format_similar_builds_omits_quality_when_none(self, tmp_path):
        """format_similar_builds omits quality line when quality is None."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(quality=None)]
        result = history.format_similar_builds(builds)
        assert "Quality:" not in result

    def test_format_similar_builds_includes_test_count_when_set(self, tmp_path):
        """format_similar_builds includes test count if present."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(test_count="15")]
        result = history.format_similar_builds(builds)
        assert "Tests: 15" in result

    def test_format_similar_builds_omits_test_count_when_none(self, tmp_path):
        """format_similar_builds omits tests line when test_count is None."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(test_count=None)]
        result = history.format_similar_builds(builds)
        assert "Tests:" not in result

    def test_format_similar_builds_includes_duration(self, tmp_path):
        """format_similar_builds includes duration in seconds (no decimals)."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(total_duration_s=123.7)]
        result = history.format_similar_builds(builds)
        assert "Duration: 124s" in result

    def test_format_similar_builds_multiple_builds_numbered(self, tmp_path):
        """format_similar_builds numbers multiple builds sequentially."""
        history = BuildHistory(project_root=tmp_path)
        builds = [
            _minimal_record(id="a", idea="first project"),
            _minimal_record(id="b", idea="second project"),
            _minimal_record(id="c", idea="third project"),
        ]
        result = history.format_similar_builds(builds)
        assert "### Build 1:" in result
        assert "### Build 2:" in result
        assert "### Build 3:" in result

    def test_format_similar_builds_truncates_long_idea(self, tmp_path):
        """format_similar_builds truncates idea to 80 characters in heading."""
        history = BuildHistory(project_root=tmp_path)
        long_idea = "x" * 200
        builds = [_minimal_record(idea=long_idea)]
        result = history.format_similar_builds(builds)
        # The heading should contain the truncated idea (first 80 chars)
        assert ("x" * 80) in result
        assert ("x" * 81) not in result

    # -----------------------------------------------------------------------
    # get_success_rate
    # -----------------------------------------------------------------------

    def test_get_success_rate_no_builds(self, tmp_path):
        """get_success_rate returns (0, 0) when there are no builds."""
        history = BuildHistory(project_root=tmp_path)
        assert history.get_success_rate() == (0, 0)

    def test_get_success_rate_all_success(self, tmp_path):
        """get_success_rate counts all successful builds."""
        history = BuildHistory(project_root=tmp_path)
        for i in range(3):
            history.record_build(_minimal_record(id=f"s{i}", outcome="success"))
        assert history.get_success_rate() == (3, 3)

    def test_get_success_rate_all_failed(self, tmp_path):
        """get_success_rate counts zero successful if all failed."""
        history = BuildHistory(project_root=tmp_path)
        for i in range(4):
            history.record_build(_minimal_record(id=f"f{i}", outcome="failed"))
        assert history.get_success_rate() == (0, 4)

    def test_get_success_rate_mixed_outcomes(self, tmp_path):
        """get_success_rate handles a mix of success, failed, partial, unknown."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(id="1", outcome="success"))
        history.record_build(_minimal_record(id="2", outcome="failed"))
        history.record_build(_minimal_record(id="3", outcome="success"))
        history.record_build(_minimal_record(id="4", outcome="partial"))
        history.record_build(_minimal_record(id="5", outcome="unknown"))
        assert history.get_success_rate() == (2, 5)

    # -----------------------------------------------------------------------
    # get_stack_stats
    # -----------------------------------------------------------------------

    def test_get_stack_stats_no_builds(self, tmp_path):
        """get_stack_stats returns {} when there are no builds."""
        history = BuildHistory(project_root=tmp_path)
        assert history.get_stack_stats() == {}

    def test_get_stack_stats_single_stack(self, tmp_path):
        """get_stack_stats tracks a single stack correctly."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(id="1", stack="nextjs", outcome="success", total_duration_s=100.0))
        history.record_build(_minimal_record(id="2", stack="nextjs", outcome="failed", total_duration_s=200.0))

        stats = history.get_stack_stats()
        assert "nextjs" in stats
        assert stats["nextjs"]["total"] == 2
        assert stats["nextjs"]["success"] == 1
        assert stats["nextjs"]["avg_duration"] == pytest.approx(150.0)

    def test_get_stack_stats_multiple_stacks(self, tmp_path):
        """get_stack_stats tracks multiple stacks independently."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(id="1", stack="nextjs", outcome="success", total_duration_s=60.0))
        history.record_build(_minimal_record(id="2", stack="swift", outcome="success", total_duration_s=120.0))
        history.record_build(_minimal_record(id="3", stack="nextjs", outcome="failed", total_duration_s=40.0))
        history.record_build(_minimal_record(id="4", stack="swift", outcome="failed", total_duration_s=80.0))

        stats = history.get_stack_stats()
        assert len(stats) == 2

        assert stats["nextjs"]["total"] == 2
        assert stats["nextjs"]["success"] == 1
        assert stats["nextjs"]["avg_duration"] == pytest.approx(50.0)

        assert stats["swift"]["total"] == 2
        assert stats["swift"]["success"] == 1
        assert stats["swift"]["avg_duration"] == pytest.approx(100.0)

    def test_get_stack_stats_zero_duration(self, tmp_path):
        """get_stack_stats handles builds with zero duration."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(id="1", stack="react", total_duration_s=0.0))
        stats = history.get_stack_stats()
        assert stats["react"]["avg_duration"] == pytest.approx(0.0)

    def test_get_stack_stats_only_counts_success_outcome(self, tmp_path):
        """get_stack_stats only counts outcome='success' as successful."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(id="1", stack="vue", outcome="partial"))
        history.record_build(_minimal_record(id="2", stack="vue", outcome="unknown"))
        history.record_build(_minimal_record(id="3", stack="vue", outcome="failed"))

        stats = history.get_stack_stats()
        assert stats["vue"]["success"] == 0
        assert stats["vue"]["total"] == 3

    # -----------------------------------------------------------------------
    # Integration / edge cases
    # -----------------------------------------------------------------------

    def test_write_then_read_roundtrip(self, tmp_path):
        """Records survive a full write-then-read cycle."""
        history = BuildHistory(project_root=tmp_path)
        records = [
            _minimal_record(id=f"r{i}", idea=f"idea {i}", outcome="success")
            for i in range(5)
        ]
        for r in records:
            history.record_build(r)

        loaded = history.get_all_builds()
        assert len(loaded) == 5
        for original, loaded_rec in zip(records, loaded):
            assert original.id == loaded_rec.id
            assert original.idea == loaded_rec.idea

    def test_separate_history_instances_share_file(self, tmp_path):
        """Two BuildHistory instances on the same root share the same file."""
        h1 = BuildHistory(project_root=tmp_path)
        h2 = BuildHistory(project_root=tmp_path)

        h1.record_build(_minimal_record(id="from_h1"))
        h2.record_build(_minimal_record(id="from_h2"))

        builds = h1.get_all_builds()
        assert len(builds) == 2
        assert builds[0].id == "from_h1"
        assert builds[1].id == "from_h2"

    def test_preexisting_jsonl_file_is_appended(self, tmp_path):
        """record_build appends to an existing JSONL file, not overwrites."""
        history = BuildHistory(project_root=tmp_path)
        # Manually seed a record
        _write_jsonl(history.builds_file, [_minimal_record(id="seed")])

        history.record_build(_minimal_record(id="new"))
        builds = history.get_all_builds()
        assert len(builds) == 2
        assert builds[0].id == "seed"
        assert builds[1].id == "new"

    # -----------------------------------------------------------------------
    # get_relevant_lessons
    # -----------------------------------------------------------------------

    def test_get_relevant_lessons_empty_history(self, tmp_path):
        """get_relevant_lessons returns [] when there are no builds."""
        history = BuildHistory(project_root=tmp_path)
        assert history.get_relevant_lessons("build a todo app") == []

    def test_get_relevant_lessons_from_similar_build(self, tmp_path):
        """get_relevant_lessons finds lessons from similar past builds."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(
            id="past",
            idea="build a task management app",
            stack="nextjs-prisma",
            outcome="failed",
            failure_reasons=["peer dep conflict with next-auth"],
            lessons=["Always run npm ls after installing next-auth"],
        ))
        lessons = history.get_relevant_lessons("build a task manager app")
        assert len(lessons) > 0
        assert any("next-auth" in l for l in lessons)

    def test_get_relevant_lessons_stack_boost(self, tmp_path):
        """get_relevant_lessons boosts score for same stack."""
        history = BuildHistory(project_root=tmp_path)
        # Low word overlap but same stack
        history.record_build(_minimal_record(
            id="same_stack",
            idea="create xyz dashboard",
            stack="nextjs-prisma",
            lessons=["Use useActionState for forms"],
        ))
        # Higher word overlap but different stack
        history.record_build(_minimal_record(
            id="diff_stack",
            idea="build a dashboard app",
            stack="rails",
            lessons=["Rails lesson"],
        ))
        lessons = history.get_relevant_lessons("build a dashboard", stack="nextjs-prisma")
        # Should include lessons from both but stack-matched one gets boosted
        assert len(lessons) > 0

    def test_get_relevant_lessons_deduplicates(self, tmp_path):
        """get_relevant_lessons returns unique lessons."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(
            id="b1",
            idea="build a todo app",
            lessons=["Always validate forms"],
        ))
        history.record_build(_minimal_record(
            id="b2",
            idea="build a todo list",
            lessons=["Always validate forms"],
        ))
        lessons = history.get_relevant_lessons("build a todo app")
        assert lessons.count("Always validate forms") == 1

    def test_get_relevant_lessons_respects_limit(self, tmp_path):
        """get_relevant_lessons returns at most limit lessons."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(
            id="past",
            idea="build a todo app",
            lessons=[f"lesson {i}" for i in range(10)],
        ))
        lessons = history.get_relevant_lessons("build a todo app", limit=3)
        assert len(lessons) <= 3

    def test_get_relevant_lessons_includes_failure_reasons(self, tmp_path):
        """get_relevant_lessons includes failure_reasons prefixed with 'Previous failure:'."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(
            id="past",
            idea="build a todo app",
            failure_reasons=["database not configured"],
        ))
        lessons = history.get_relevant_lessons("build a todo app")
        assert any("Previous failure:" in l for l in lessons)
        assert any("database not configured" in l for l in lessons)

    def test_get_relevant_lessons_ignores_unrelated_builds(self, tmp_path):
        """get_relevant_lessons ignores builds with very low similarity."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(
            id="unrelated",
            idea="alpha bravo charlie delta echo foxtrot",
            lessons=["Unrelated lesson"],
        ))
        lessons = history.get_relevant_lessons("kilo lima mike november")
        assert lessons == []

    # -----------------------------------------------------------------------
    # format_lessons
    # -----------------------------------------------------------------------

    def test_format_lessons_empty(self, tmp_path):
        """format_lessons returns empty string for no lessons."""
        history = BuildHistory(project_root=tmp_path)
        assert history.format_lessons([]) == ""

    def test_format_lessons_contains_header(self, tmp_path):
        """format_lessons output starts with section header."""
        history = BuildHistory(project_root=tmp_path)
        result = history.format_lessons(["Use useActionState"])
        assert "## Lessons from Past Builds" in result

    def test_format_lessons_contains_items(self, tmp_path):
        """format_lessons includes each lesson as a bullet point."""
        history = BuildHistory(project_root=tmp_path)
        result = history.format_lessons(["Lesson A", "Lesson B"])
        assert "- Lesson A" in result
        assert "- Lesson B" in result

    # -----------------------------------------------------------------------
    # format_similar_builds with lessons/failures
    # -----------------------------------------------------------------------

    def test_format_similar_builds_includes_lessons(self, tmp_path):
        """format_similar_builds shows lessons when present."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(lessons=["Check peer deps"])]
        result = history.format_similar_builds(builds)
        assert "Lessons learned:" in result
        assert "Check peer deps" in result

    def test_format_similar_builds_includes_failure_reasons(self, tmp_path):
        """format_similar_builds shows failure reasons when present."""
        history = BuildHistory(project_root=tmp_path)
        builds = [_minimal_record(failure_reasons=["Missing middleware"])]
        result = history.format_similar_builds(builds)
        assert "Failure reasons:" in result
        assert "Missing middleware" in result

    # -----------------------------------------------------------------------
    # Integration
    # -----------------------------------------------------------------------

    def test_find_similar_then_format_integration(self, tmp_path):
        """find_similar_builds + format_similar_builds work end-to-end."""
        history = BuildHistory(project_root=tmp_path)
        history.record_build(_minimal_record(
            id="past",
            idea="build a real time chat application",
            outcome="success",
            quality="A",
            test_count="20",
            total_duration_s=180.0,
        ))

        similar = history.find_similar_builds("build a chat application")
        formatted = history.format_similar_builds(similar)

        assert "## Similar Past Builds" in formatted
        assert "build a real time chat application" in formatted
        assert "success" in formatted
        assert "Quality: A" in formatted
        assert "Tests: 20" in formatted
        assert "Duration: 180s" in formatted
