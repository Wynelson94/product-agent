"""Checkpoint system for resumable builds in Product Agent v6.0.

Allows saving and restoring agent state for long-running builds.
Includes verification phase tracking, spec audit, and enrichment state.
"""

import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from .state import AgentState, Phase


class CheckpointManager:
    """Manages checkpoints for resumable agent execution.

    Checkpoints are saved as JSON files in a .agent_checkpoints directory
    within the project directory.
    """

    CHECKPOINT_DIR = ".agent_checkpoints"

    def __init__(self, project_dir: str):
        """Initialize the checkpoint manager.

        Args:
            project_dir: The project directory to store checkpoints in
        """
        self.project_dir = Path(project_dir)
        self.checkpoint_dir = self.project_dir / self.CHECKPOINT_DIR
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: AgentState, phase: Optional[Phase] = None) -> str:
        """Save a checkpoint of the current state.

        Args:
            state: The agent state to save
            phase: Optional phase override (defaults to state.phase)

        Returns:
            The checkpoint ID
        """
        phase_name = (phase or state.phase).value
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_id = f"{phase_name}_{timestamp}"

        checkpoint_data = {
            "id": checkpoint_id,
            "phase": phase_name,
            "timestamp": datetime.now().isoformat(),
            "state": state.to_dict(),
            "artifact_hashes": self._compute_artifact_hashes(),
        }

        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        # Also save as "latest" for easy access
        latest_path = self.checkpoint_dir / "latest.json"
        with open(latest_path, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        return checkpoint_id

    def load_latest(self) -> Optional[tuple[str, AgentState]]:
        """Load the most recent checkpoint.

        Returns:
            Tuple of (checkpoint_id, AgentState) or None if no checkpoints exist
        """
        latest_path = self.checkpoint_dir / "latest.json"
        if not latest_path.exists():
            return None

        with open(latest_path) as f:
            data = json.load(f)

        return data["id"], AgentState.from_dict(data["state"])

    def load(self, checkpoint_id: str) -> Optional[AgentState]:
        """Load a specific checkpoint by ID.

        Args:
            checkpoint_id: The checkpoint ID to load

        Returns:
            The AgentState or None if checkpoint doesn't exist
        """
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        if not checkpoint_path.exists():
            return None

        with open(checkpoint_path) as f:
            data = json.load(f)

        return AgentState.from_dict(data["state"])

    def list_checkpoints(self) -> list[dict]:
        """List all available checkpoints.

        Returns:
            List of checkpoint metadata (id, phase, timestamp)
        """
        checkpoints = []

        for path in sorted(self.checkpoint_dir.glob("*.json")):
            if path.name == "latest.json":
                continue

            with open(path) as f:
                data = json.load(f)
                checkpoints.append({
                    "id": data["id"],
                    "phase": data["phase"],
                    "timestamp": data["timestamp"],
                })

        return checkpoints

    def get_checkpoint_for_phase(self, phase: Phase) -> Optional[tuple[str, AgentState]]:
        """Get the most recent checkpoint for a specific phase.

        Args:
            phase: The phase to find a checkpoint for

        Returns:
            Tuple of (checkpoint_id, AgentState) or None
        """
        phase_checkpoints = []

        for path in self.checkpoint_dir.glob(f"{phase.value}_*.json"):
            with open(path) as f:
                data = json.load(f)
                phase_checkpoints.append((data["id"], data["timestamp"], data["state"]))

        if not phase_checkpoints:
            return None

        # Sort by timestamp descending and get the latest
        phase_checkpoints.sort(key=lambda x: x[1], reverse=True)
        checkpoint_id, _, state_dict = phase_checkpoints[0]

        return checkpoint_id, AgentState.from_dict(state_dict)

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a specific checkpoint.

        Args:
            checkpoint_id: The checkpoint ID to delete

        Returns:
            True if deleted, False if not found
        """
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            return True
        return False

    def clear_all(self) -> int:
        """Delete all checkpoints.

        Returns:
            Number of checkpoints deleted
        """
        count = 0
        for path in self.checkpoint_dir.glob("*.json"):
            path.unlink()
            count += 1
        return count

    def _compute_artifact_hashes(self) -> dict[str, str]:
        """Compute sha256 hashes of all .md artifacts in the project directory.

        Returns:
            Dict of filename → sha256 hex digest
        """
        hashes = {}
        try:
            for md_file in self.project_dir.glob("*.md"):
                content = md_file.read_bytes()
                hashes[md_file.name] = hashlib.sha256(content).hexdigest()
        except Exception:
            pass  # Never let hashing break checkpoint saving
        return hashes

    def get_resume_prompt(self, state: AgentState) -> str:
        """Generate a prompt for resuming from a checkpoint.

        Args:
            state: The state to resume from

        Returns:
            A prompt describing the current state and next steps
        """
        phase = state.phase.value
        idea = state.idea

        prompt_parts = [
            f"Resuming build for: {idea}",
            f"Current phase: {phase}",
        ]

        if state.stack_id:
            prompt_parts.append(f"Selected stack: {state.stack_id}")

        if state.design_revision > 0:
            prompt_parts.append(f"Design revisions: {state.design_revision}")

        if state.build_attempts > 0:
            prompt_parts.append(f"Build attempts: {state.build_attempts}")
            if state.last_build_error:
                prompt_parts.append(f"Last build error: {state.last_build_error[:200]}...")

        if state.last_error:
            prompt_parts.append(f"Last error: {state.last_error[:200]}...")

        # v5.0: Add deployment and verification info
        if state.deployment_target:
            prompt_parts.append(f"Deployment target: {state.deployment_target}")

        if state.database_type:
            prompt_parts.append(f"Database type: {state.database_type}")

        if state.deployment_url:
            prompt_parts.append(f"Deployed URL: {state.deployment_url}")

        if state.verification_attempts > 0:
            prompt_parts.append(f"Verification attempts: {state.verification_attempts}")
            if state.verification_results:
                status = state.verification_results.get("status", "unknown")
                prompt_parts.append(f"Last verification status: {status}")

        # v6.0: Add enrichment and audit info
        if state.prompt_enriched:
            prompt_parts.append("Prompt enrichment: completed")
            if state.enrichment_source_url:
                prompt_parts.append(f"Enrichment source: {state.enrichment_source_url}")

        if state.spec_audit_completed:
            prompt_parts.append(f"Spec audit: completed ({state.spec_audit_discrepancies} discrepancies)")
            if state.audit_fix_attempted:
                prompt_parts.append("Audit fix: attempted")

        # Add next action based on phase
        next_actions = {
            Phase.INIT: "Start with stack analysis.",
            Phase.ENRICH: "Continue with enrichment or proceed to analysis.",  # v6.0
            Phase.ANALYSIS: "Continue with design creation.",
            Phase.DESIGN: "Continue with design review.",
            Phase.REVIEW: "Apply review feedback or proceed to build.",
            Phase.BUILD: "Continue building or fix build errors.",
            Phase.AUDIT: "Continue spec audit or proceed to testing.",  # v6.0
            Phase.TEST: "Continue testing or fix test failures.",  # v5.1
            Phase.DEPLOY: "Continue deployment or fix deploy errors.",
            Phase.VERIFY: "Continue verification or address verification failures.",  # v5.0
        }

        if state.phase in next_actions:
            prompt_parts.append(f"\nNext action: {next_actions[state.phase]}")

        return "\n".join(prompt_parts)


def save_checkpoint(project_dir: str, state: AgentState) -> str:
    """Convenience function to save a checkpoint.

    Args:
        project_dir: The project directory
        state: The agent state to save

    Returns:
        The checkpoint ID
    """
    manager = CheckpointManager(project_dir)
    return manager.save(state)


def load_latest_checkpoint(project_dir: str) -> Optional[tuple[str, AgentState]]:
    """Convenience function to load the latest checkpoint.

    Args:
        project_dir: The project directory

    Returns:
        Tuple of (checkpoint_id, AgentState) or None
    """
    manager = CheckpointManager(project_dir)
    return manager.load_latest()


def resume_from_checkpoint(
    project_dir: str,
    checkpoint_id: Optional[str] = None
) -> Optional[tuple[str, AgentState, str]]:
    """Load a checkpoint and generate a resume prompt.

    Args:
        project_dir: The project directory
        checkpoint_id: Optional specific checkpoint to load (defaults to latest)

    Returns:
        Tuple of (checkpoint_id, AgentState, resume_prompt) or None
    """
    manager = CheckpointManager(project_dir)

    if checkpoint_id:
        state = manager.load(checkpoint_id)
        if not state:
            return None
    else:
        result = manager.load_latest()
        if not result:
            return None
        checkpoint_id, state = result

    resume_prompt = manager.get_resume_prompt(state)
    return checkpoint_id, state, resume_prompt
