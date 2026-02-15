"""Comprehensive tests for the checkpoint system in agent/checkpoints.py.

Tests cover CheckpointManager methods, convenience functions,
state round-trip serialization, and resume prompt generation.
"""

import json
import time

import pytest

from agent.checkpoints import (
    CheckpointManager,
    load_latest_checkpoint,
    resume_from_checkpoint,
    save_checkpoint,
)
from agent.state import AgentState, Phase, create_initial_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(tmp_path, idea="test idea", phase=Phase.INIT, **overrides):
    """Create an AgentState pre-populated with common defaults."""
    state = create_initial_state(idea, str(tmp_path))
    state.phase = phase
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


# ---------------------------------------------------------------------------
# TestCheckpointManager -- init and save
# ---------------------------------------------------------------------------

class TestCheckpointManager:
    """Tests for CheckpointManager.__init__ and save()."""

    def test_init_creates_checkpoint_dir(self, tmp_path):
        """Constructing a manager should create the .agent_checkpoints dir."""
        mgr = CheckpointManager(str(tmp_path))
        assert (tmp_path / ".agent_checkpoints").exists()
        assert (tmp_path / ".agent_checkpoints").is_dir()

    def test_init_idempotent(self, tmp_path):
        """Creating a manager twice should not fail or remove existing data."""
        mgr1 = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        mgr1.save(state)
        mgr2 = CheckpointManager(str(tmp_path))
        # The checkpoint created by mgr1 should still exist.
        assert mgr2.load_latest() is not None

    def test_save_returns_checkpoint_id(self, tmp_path):
        """save() should return a non-empty string containing the phase name."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        cp_id = mgr.save(state)
        assert isinstance(cp_id, str)
        assert len(cp_id) > 0
        assert "init" in cp_id

    def test_save_creates_checkpoint_file(self, tmp_path):
        """save() should write a <checkpoint_id>.json file."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        cp_id = mgr.save(state)
        checkpoint_file = tmp_path / ".agent_checkpoints" / f"{cp_id}.json"
        assert checkpoint_file.exists()

        data = json.loads(checkpoint_file.read_text())
        assert data["id"] == cp_id
        assert data["phase"] == "init"
        assert "state" in data
        assert "timestamp" in data

    def test_save_creates_latest_file(self, tmp_path):
        """save() should also write a latest.json file."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        cp_id = mgr.save(state)
        latest_file = tmp_path / ".agent_checkpoints" / "latest.json"
        assert latest_file.exists()

        data = json.loads(latest_file.read_text())
        assert data["id"] == cp_id

    def test_save_with_phase_override(self, tmp_path):
        """save(state, phase=...) should use the override phase, not state.phase."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path, phase=Phase.INIT)
        cp_id = mgr.save(state, phase=Phase.BUILD)
        assert "build" in cp_id
        # The checkpoint file should record the overridden phase.
        checkpoint_file = tmp_path / ".agent_checkpoints" / f"{cp_id}.json"
        data = json.loads(checkpoint_file.read_text())
        assert data["phase"] == "build"


# ---------------------------------------------------------------------------
# TestCheckpointLoadLatest
# ---------------------------------------------------------------------------

class TestCheckpointLoadLatest:
    """Tests for CheckpointManager.load_latest()."""

    def test_load_latest_when_no_checkpoints(self, tmp_path):
        """load_latest() should return None when no checkpoints exist."""
        mgr = CheckpointManager(str(tmp_path))
        assert mgr.load_latest() is None

    def test_load_latest_returns_state(self, tmp_path):
        """load_latest() should return a (checkpoint_id, AgentState) tuple."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path, idea="my product")
        cp_id = mgr.save(state)

        result = mgr.load_latest()
        assert result is not None
        loaded_id, loaded_state = result
        assert loaded_id == cp_id
        assert isinstance(loaded_state, AgentState)

    def test_load_latest_preserves_state_fields(self, tmp_path):
        """Round-tripping through save/load_latest should preserve all fields."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(
            tmp_path,
            idea="preserved fields test",
            phase=Phase.BUILD,
            stack_id="nextjs-supabase",
            build_attempts=3,
            last_build_error="module not found",
            deployment_target="vercel",
            database_type="postgresql",
            prompt_enriched=True,
            enrichment_source_url="https://example.com",
            spec_audit_completed=True,
            spec_audit_discrepancies=2,
            audit_fix_attempted=True,
        )
        mgr.save(state)

        _, loaded = mgr.load_latest()
        assert loaded.idea == "preserved fields test"
        assert loaded.phase == Phase.BUILD
        assert loaded.stack_id == "nextjs-supabase"
        assert loaded.build_attempts == 3
        assert loaded.last_build_error == "module not found"
        assert loaded.deployment_target == "vercel"
        assert loaded.database_type == "postgresql"
        assert loaded.prompt_enriched is True
        assert loaded.enrichment_source_url == "https://example.com"
        assert loaded.spec_audit_completed is True
        assert loaded.spec_audit_discrepancies == 2
        assert loaded.audit_fix_attempted is True


# ---------------------------------------------------------------------------
# TestCheckpointLoad
# ---------------------------------------------------------------------------

class TestCheckpointLoad:
    """Tests for CheckpointManager.load(checkpoint_id)."""

    def test_load_by_id(self, tmp_path):
        """load() should retrieve a specific checkpoint by its ID."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path, idea="load-by-id")
        cp_id = mgr.save(state)

        loaded = mgr.load(cp_id)
        assert loaded is not None
        assert isinstance(loaded, AgentState)
        assert loaded.idea == "load-by-id"

    def test_load_nonexistent_returns_none(self, tmp_path):
        """load() should return None for a non-existent checkpoint ID."""
        mgr = CheckpointManager(str(tmp_path))
        assert mgr.load("nonexistent_20260101_000000") is None


# ---------------------------------------------------------------------------
# TestCheckpointList
# ---------------------------------------------------------------------------

class TestCheckpointList:
    """Tests for CheckpointManager.list_checkpoints()."""

    def test_list_empty(self, tmp_path):
        """list_checkpoints() should return an empty list when none exist."""
        mgr = CheckpointManager(str(tmp_path))
        assert mgr.list_checkpoints() == []

    def test_list_multiple_checkpoints(self, tmp_path):
        """list_checkpoints() should return metadata for every saved checkpoint."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)

        ids = []
        for phase in (Phase.INIT, Phase.ANALYSIS, Phase.BUILD):
            state.phase = phase
            cp_id = mgr.save(state, phase=phase)
            ids.append(cp_id)
            # Ensure distinct timestamps (format is down to the second).
            time.sleep(1.1)

        checkpoints = mgr.list_checkpoints()
        assert len(checkpoints) == 3
        listed_ids = [cp["id"] for cp in checkpoints]
        for cp_id in ids:
            assert cp_id in listed_ids

        # Each entry has the expected keys.
        for cp in checkpoints:
            assert "id" in cp
            assert "phase" in cp
            assert "timestamp" in cp

    def test_list_excludes_latest(self, tmp_path):
        """list_checkpoints() should not include the latest.json symlink entry."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        mgr.save(state)

        checkpoints = mgr.list_checkpoints()
        for cp in checkpoints:
            assert cp["id"] != "latest"
            assert "latest" not in cp["id"]


# ---------------------------------------------------------------------------
# TestCheckpointForPhase
# ---------------------------------------------------------------------------

class TestCheckpointForPhase:
    """Tests for CheckpointManager.get_checkpoint_for_phase()."""

    def test_get_checkpoint_for_phase(self, tmp_path):
        """get_checkpoint_for_phase() should return the most recent match."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path, idea="phase lookup", phase=Phase.BUILD)
        cp_id = mgr.save(state)

        result = mgr.get_checkpoint_for_phase(Phase.BUILD)
        assert result is not None
        found_id, found_state = result
        assert found_id == cp_id
        assert found_state.idea == "phase lookup"
        assert found_state.phase == Phase.BUILD

    def test_get_checkpoint_for_phase_not_found(self, tmp_path):
        """get_checkpoint_for_phase() should return None if no matching phase."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path, phase=Phase.INIT)
        mgr.save(state)

        assert mgr.get_checkpoint_for_phase(Phase.DEPLOY) is None


# ---------------------------------------------------------------------------
# TestCheckpointDelete
# ---------------------------------------------------------------------------

class TestCheckpointDelete:
    """Tests for delete_checkpoint() and clear_all()."""

    def test_delete_checkpoint(self, tmp_path):
        """delete_checkpoint() should remove the file and return True."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        cp_id = mgr.save(state)

        assert mgr.delete_checkpoint(cp_id) is True
        # File should be gone.
        assert not (tmp_path / ".agent_checkpoints" / f"{cp_id}.json").exists()
        # load by id should now return None.
        assert mgr.load(cp_id) is None

    def test_delete_nonexistent_returns_false(self, tmp_path):
        """delete_checkpoint() should return False for a missing checkpoint."""
        mgr = CheckpointManager(str(tmp_path))
        assert mgr.delete_checkpoint("does_not_exist_20260101_000000") is False

    def test_clear_all(self, tmp_path):
        """clear_all() should remove every checkpoint and return the count."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)

        mgr.save(state, phase=Phase.INIT)
        time.sleep(1.1)
        mgr.save(state, phase=Phase.BUILD)

        # 2 phase files + 1 latest.json = 3 json files total
        deleted = mgr.clear_all()
        assert deleted == 3

        assert mgr.list_checkpoints() == []
        assert mgr.load_latest() is None


# ---------------------------------------------------------------------------
# TestResumePrompt
# ---------------------------------------------------------------------------

class TestResumePrompt:
    """Tests for CheckpointManager.get_resume_prompt()."""

    def test_resume_prompt_contains_idea(self, tmp_path):
        """The resume prompt must mention the original idea."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path, idea="AI-powered todo app")
        prompt = mgr.get_resume_prompt(state)
        assert "AI-powered todo app" in prompt

    def test_resume_prompt_contains_phase(self, tmp_path):
        """The resume prompt must mention the current phase."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path, phase=Phase.BUILD)
        prompt = mgr.get_resume_prompt(state)
        assert "build" in prompt

    def test_resume_prompt_with_stack(self, tmp_path):
        """When a stack is selected, the resume prompt should include it."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path, stack_id="nextjs-supabase")
        prompt = mgr.get_resume_prompt(state)
        assert "nextjs-supabase" in prompt

    def test_resume_prompt_with_errors(self, tmp_path):
        """The resume prompt should surface last_error and last_build_error."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(
            tmp_path,
            phase=Phase.BUILD,
            build_attempts=2,
            last_build_error="Cannot find module 'react'",
            last_error="Timeout during build step",
        )
        prompt = mgr.get_resume_prompt(state)
        assert "Build attempts: 2" in prompt
        assert "Cannot find module" in prompt
        assert "Timeout during build step" in prompt

    def test_resume_prompt_with_enrichment(self, tmp_path):
        """When enrichment is complete, the prompt should mention it."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(
            tmp_path,
            phase=Phase.ANALYSIS,
            prompt_enriched=True,
            enrichment_source_url="https://example.com/ref",
        )
        prompt = mgr.get_resume_prompt(state)
        assert "enrichment: completed" in prompt.lower() or "Prompt enrichment: completed" in prompt
        assert "https://example.com/ref" in prompt

    def test_resume_prompt_with_audit(self, tmp_path):
        """When spec audit is complete, the prompt should mention discrepancies."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(
            tmp_path,
            phase=Phase.AUDIT,
            spec_audit_completed=True,
            spec_audit_discrepancies=4,
            audit_fix_attempted=True,
        )
        prompt = mgr.get_resume_prompt(state)
        assert "Spec audit: completed" in prompt
        assert "4 discrepancies" in prompt
        assert "Audit fix: attempted" in prompt

    def test_resume_prompt_next_action(self, tmp_path):
        """The prompt should include a 'Next action' line for actionable phases."""
        mgr = CheckpointManager(str(tmp_path))
        actionable_phases = {
            Phase.INIT: "stack analysis",
            Phase.ENRICH: "enrichment",
            Phase.ANALYSIS: "design creation",
            Phase.DESIGN: "design review",
            Phase.REVIEW: "review feedback",
            Phase.BUILD: "building",
            Phase.AUDIT: "spec audit",
            Phase.TEST: "testing",
            Phase.DEPLOY: "deployment",
            Phase.VERIFY: "verification",
        }
        for phase, keyword in actionable_phases.items():
            state = _make_state(tmp_path, phase=phase)
            prompt = mgr.get_resume_prompt(state)
            assert "Next action:" in prompt, (
                f"Phase {phase.value} should have a Next action line"
            )

    def test_resume_prompt_with_deployment_info(self, tmp_path):
        """Deployment fields should be reflected in the resume prompt."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(
            tmp_path,
            phase=Phase.VERIFY,
            deployment_target="vercel",
            database_type="postgresql",
            deployment_url="https://my-app.vercel.app",
            verification_attempts=1,
            verification_results={"status": "partial"},
        )
        prompt = mgr.get_resume_prompt(state)
        assert "vercel" in prompt
        assert "postgresql" in prompt
        assert "https://my-app.vercel.app" in prompt
        assert "Verification attempts: 1" in prompt
        assert "partial" in prompt


# ---------------------------------------------------------------------------
# TestConvenienceFunctions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_save_checkpoint_function(self, tmp_path):
        """save_checkpoint() should save and return a checkpoint ID."""
        state = _make_state(tmp_path)
        cp_id = save_checkpoint(str(tmp_path), state)
        assert isinstance(cp_id, str)
        assert len(cp_id) > 0
        # The file should exist.
        assert (tmp_path / ".agent_checkpoints" / f"{cp_id}.json").exists()

    def test_load_latest_checkpoint_function(self, tmp_path):
        """load_latest_checkpoint() should load the most recent checkpoint."""
        state = _make_state(tmp_path, idea="convenience load")
        save_checkpoint(str(tmp_path), state)

        result = load_latest_checkpoint(str(tmp_path))
        assert result is not None
        cp_id, loaded = result
        assert loaded.idea == "convenience load"

    def test_load_latest_checkpoint_no_checkpoints(self, tmp_path):
        """load_latest_checkpoint() should return None when nothing is saved."""
        result = load_latest_checkpoint(str(tmp_path))
        assert result is None

    def test_resume_from_checkpoint_no_checkpoints(self, tmp_path):
        """resume_from_checkpoint() should return None when nothing is saved."""
        result = resume_from_checkpoint(str(tmp_path))
        assert result is None

    def test_resume_from_checkpoint_latest(self, tmp_path):
        """resume_from_checkpoint() without an ID should use the latest."""
        state = _make_state(tmp_path, idea="resume latest")
        save_checkpoint(str(tmp_path), state)

        result = resume_from_checkpoint(str(tmp_path))
        assert result is not None
        cp_id, loaded_state, resume_prompt = result
        assert loaded_state.idea == "resume latest"
        assert "resume latest" in resume_prompt

    def test_resume_from_checkpoint_by_id(self, tmp_path):
        """resume_from_checkpoint(checkpoint_id=...) should load that specific one."""
        state1 = _make_state(tmp_path, idea="first save")
        cp_id1 = save_checkpoint(str(tmp_path), state1)
        time.sleep(1.1)

        state2 = _make_state(tmp_path, idea="second save")
        save_checkpoint(str(tmp_path), state2)

        # Explicitly request the first checkpoint, not latest.
        result = resume_from_checkpoint(str(tmp_path), checkpoint_id=cp_id1)
        assert result is not None
        loaded_id, loaded_state, resume_prompt = result
        assert loaded_id == cp_id1
        assert loaded_state.idea == "first save"
        assert "first save" in resume_prompt

    def test_resume_from_checkpoint_nonexistent_id(self, tmp_path):
        """resume_from_checkpoint() with a bad ID should return None."""
        result = resume_from_checkpoint(str(tmp_path), checkpoint_id="bogus_20260101_000000")
        assert result is None


# ---------------------------------------------------------------------------
# TestCheckpointCleanup
# ---------------------------------------------------------------------------

class TestCheckpointCleanup:
    """Tests for CheckpointManager.cleanup()."""

    def test_cleanup_keeps_latest_n(self, tmp_path):
        """cleanup(keep_latest=2) should delete all but the 2 most recent."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)

        ids = []
        for i, phase in enumerate([Phase.INIT, Phase.ANALYSIS, Phase.DESIGN, Phase.BUILD]):
            state.phase = phase
            cp_id = mgr.save(state, phase=phase)
            ids.append(cp_id)
            time.sleep(0.05)  # ensure distinct mtime

        deleted = mgr.cleanup(keep_latest=2)
        assert deleted == 2

        # The 2 oldest should be gone
        assert not (tmp_path / ".agent_checkpoints" / f"{ids[0]}.json").exists()
        assert not (tmp_path / ".agent_checkpoints" / f"{ids[1]}.json").exists()
        # The 2 newest should remain
        assert (tmp_path / ".agent_checkpoints" / f"{ids[2]}.json").exists()
        assert (tmp_path / ".agent_checkpoints" / f"{ids[3]}.json").exists()

    def test_cleanup_noop_when_below_limit(self, tmp_path):
        """cleanup() should return 0 when there are fewer checkpoints than the limit."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        mgr.save(state)

        deleted = mgr.cleanup(keep_latest=5)
        assert deleted == 0

    def test_cleanup_preserves_latest_json(self, tmp_path):
        """cleanup() should not delete latest.json."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        for phase in [Phase.INIT, Phase.ANALYSIS, Phase.DESIGN]:
            state.phase = phase
            mgr.save(state, phase=phase)
            time.sleep(0.05)

        mgr.cleanup(keep_latest=1)
        assert (tmp_path / ".agent_checkpoints" / "latest.json").exists()


# ---------------------------------------------------------------------------
# TestCheckpointArchive
# ---------------------------------------------------------------------------

class TestCheckpointArchive:
    """Tests for CheckpointManager.archive()."""

    def test_archive_creates_zip(self, tmp_path):
        """archive() should create a .zip file containing checkpoints."""
        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        mgr.save(state)

        archive_path = mgr.archive()
        assert archive_path is not None
        assert archive_path.exists()
        assert archive_path.suffix == ".zip"

    def test_archive_includes_checkpoint_files(self, tmp_path):
        """The archive should contain checkpoint JSON files."""
        import zipfile

        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        cp_id = mgr.save(state)

        archive_path = mgr.archive()
        with zipfile.ZipFile(archive_path, "r") as zf:
            names = zf.namelist()
            assert any(cp_id in name for name in names)

    def test_archive_includes_logs_if_present(self, tmp_path):
        """If .agent_logs/ exists, archive should include those files."""
        import zipfile

        logs_dir = tmp_path / ".agent_logs"
        logs_dir.mkdir()
        (logs_dir / "test_log.md").write_text("log content")

        mgr = CheckpointManager(str(tmp_path))
        state = _make_state(tmp_path)
        mgr.save(state)

        archive_path = mgr.archive()
        with zipfile.ZipFile(archive_path, "r") as zf:
            names = zf.namelist()
            assert any("agent_logs" in name for name in names)

    def test_archive_returns_none_when_empty(self, tmp_path):
        """archive() should return None when there's nothing to archive."""
        # Create manager but don't save anything, and remove the empty dir
        mgr = CheckpointManager(str(tmp_path))
        # Clear the checkpoint dir
        for f in mgr.checkpoint_dir.iterdir():
            f.unlink()

        result = mgr.archive()
        assert result is None


# ---------------------------------------------------------------------------
# TestPhaseHistoryCap
# ---------------------------------------------------------------------------

class TestPhaseHistoryCap:
    """Tests for phase_history capping in AgentState.transition_to()."""

    def test_phase_history_capped_at_max(self, tmp_path):
        """transition_to() should cap phase_history at MAX_PHASE_HISTORY."""
        state = _make_state(tmp_path)
        max_hist = state.MAX_PHASE_HISTORY

        # Add more than the limit
        phases = [Phase.ANALYSIS, Phase.DESIGN, Phase.REVIEW, Phase.BUILD]
        for i in range(max_hist + 20):
            state.transition_to(phases[i % len(phases)], f"transition {i}")

        assert len(state.phase_history) == max_hist

    def test_phase_history_keeps_most_recent(self, tmp_path):
        """When capped, the most recent entries should be preserved."""
        state = _make_state(tmp_path)
        max_hist = state.MAX_PHASE_HISTORY

        for i in range(max_hist + 5):
            state.transition_to(Phase.BUILD, f"entry-{i}")

        # The last entry should be the most recent
        assert state.phase_history[-1]["notes"] == f"entry-{max_hist + 4}"
        # The first entry should be from after the cap kicked in
        assert state.phase_history[0]["notes"] == "entry-5"

    def test_phase_history_below_cap_unchanged(self, tmp_path):
        """Below the cap, all entries should be preserved."""
        state = _make_state(tmp_path)
        state.transition_to(Phase.ANALYSIS, "first")
        state.transition_to(Phase.DESIGN, "second")
        state.transition_to(Phase.BUILD, "third")

        assert len(state.phase_history) == 3
        assert state.phase_history[0]["notes"] == "first"
