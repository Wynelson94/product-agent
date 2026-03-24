"""State management for Product Agent v10.1.

Tracks the agent's progress through phases and handles iteration limits.
Includes deployment-aware verification, compatibility tracking,
spec auditing (v6.0), prompt enrichment (v6.0), Swift/SwiftUI
plugin architecture tracking (v7.0), and CRITICAL audit override (v10.0).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json
from datetime import datetime


class Phase(Enum):
    """Phases of the product building process."""
    INIT = "init"
    ENRICH = "enrich"  # v6.0: Optional prompt enrichment via research
    ANALYSIS = "analysis"
    DESIGN = "design"
    REVIEW = "review"
    ENHANCE = "enhance"  # v10.2: Enhancement mode — modify existing design with new features
    BUILD = "build"
    AUDIT = "audit"  # v6.0: Spec audit — verify build matches original prompt
    TEST = "test"  # v5.1: Test generation and execution
    DEPLOY = "deploy"
    VERIFY = "verify"  # v5.0: Post-deployment verification
    COMPLETE = "complete"
    FAILED = "failed"


class ReviewStatus(Enum):
    """Status from design review."""
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"


@dataclass
class AgentState:
    """Tracks the state of an agent execution.

    This state can be serialized to JSON for checkpointing and resume.
    """
    # Current phase
    phase: Phase = Phase.INIT

    # Product info
    idea: str = ""
    project_dir: str = ""

    # Stack selection
    stack_id: Optional[str] = None

    # Design iteration tracking
    design_revision: int = 0
    review_status: ReviewStatus = ReviewStatus.PENDING

    # Build iteration tracking
    build_attempts: int = 0
    last_build_error: Optional[str] = None

    # Deployment tracking
    deployment_url: Optional[str] = None
    deployment_verified: bool = False

    # Error tracking
    last_error: Optional[str] = None
    error_count: int = 0

    # Timestamps
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Phase history for debugging
    phase_history: list = field(default_factory=list)

    # Enhancement mode tracking
    enhancement_mode: bool = False
    enhance_features: list = field(default_factory=list)
    original_design_path: Optional[str] = None

    # v5.0: Deployment-aware tracking
    deployment_target: Optional[str] = None  # "vercel", "railway", etc.
    database_type: Optional[str] = None  # "postgresql", "sqlite", etc.
    verification_results: dict = field(default_factory=dict)
    verification_attempts: int = 0

    # v5.1: Test tracking
    tests_generated: bool = False
    tests_passed: bool = False
    test_results: dict = field(default_factory=dict)
    test_attempts: int = 0

    # v6.0: Prompt enrichment tracking
    prompt_enriched: bool = False
    enriched_prompt: Optional[str] = None
    enrichment_source_url: Optional[str] = None

    # v6.0: Spec audit tracking
    spec_audit_completed: bool = False
    spec_audit_discrepancies: int = 0
    spec_audit_critical_count: int = 0  # v10.0: Count of CRITICAL findings from audit
    audit_fix_attempted: bool = False

    # v7.0: Swift/SwiftUI plugin architecture
    build_mode: str = "standard"  # "standard" | "host" | "plugin"
    plugin_packaged: bool = False  # True when plugin swift build + swift test pass

    MAX_PHASE_HISTORY = 50

    def transition_to(self, new_phase: Phase, notes: str = "") -> None:
        """Transition to a new phase, recording the change."""
        self.phase_history.append({
            "from": self.phase.value,
            "to": new_phase.value,
            "timestamp": datetime.now().isoformat(),
            "notes": notes,
        })
        # Cap phase history to prevent unbounded growth
        if len(self.phase_history) > self.MAX_PHASE_HISTORY:
            self.phase_history = self.phase_history[-self.MAX_PHASE_HISTORY:]
        self.phase = new_phase

    def record_error(self, error: str) -> None:
        """Record an error occurrence."""
        self.last_error = error
        self.error_count += 1

    def can_revise_design(self, max_revisions: int = 2) -> bool:
        """Check if we can do another design revision."""
        return self.design_revision < max_revisions

    def can_retry_build(self, max_attempts: int = 5) -> bool:
        """Check if we can retry the build."""
        return self.build_attempts < max_attempts

    def increment_design_revision(self) -> None:
        """Increment design revision counter."""
        self.design_revision += 1

    def increment_build_attempt(self, error: Optional[str] = None) -> None:
        """Increment build attempt counter."""
        self.build_attempts += 1
        if error:
            self.last_build_error = error

    def mark_started(self) -> None:
        """Mark the execution as started."""
        self.started_at = datetime.now().isoformat()

    def mark_completed(self, url: Optional[str] = None) -> None:
        """Mark the execution as completed."""
        self.completed_at = datetime.now().isoformat()
        self.transition_to(Phase.COMPLETE)
        if url:
            self.deployment_url = url

    def mark_failed(self, error: str) -> None:
        """Mark the execution as failed."""
        self.completed_at = datetime.now().isoformat()
        self.last_error = error
        self.transition_to(Phase.FAILED, notes=error)

    def mark_verified(self, results: dict) -> None:
        """Mark deployment as verified with results.

        Args:
            results: Verification results dict with 'status', 'tests', etc.
        """
        self.deployment_verified = True
        self.verification_results = results
        self.transition_to(Phase.VERIFY, notes="Verification passed")

    def mark_verification_failed(self, results: dict) -> None:
        """Mark verification as failed.

        Args:
            results: Verification results dict with failure details
        """
        self.deployment_verified = False
        self.verification_results = results
        self.verification_attempts += 1

    def can_retry_verification(self, max_attempts: int = 2) -> bool:
        """Check if we can retry verification."""
        return self.verification_attempts < max_attempts

    def can_retry_tests(self, max_attempts: int = 3) -> bool:
        """Check if we can retry running tests."""
        return self.test_attempts < max_attempts

    def increment_test_attempt(self) -> None:
        """Increment test attempt counter."""
        self.test_attempts += 1

    def mark_tests_passed(self, results: dict) -> None:
        """Mark that tests have been generated and passed.

        Args:
            results: Test results dict with 'total', 'passed', 'failed', etc.
        """
        self.tests_generated = True
        self.tests_passed = True
        self.test_results = results

    def mark_tests_failed(self, results: dict) -> None:
        """Mark that tests have failed.

        Args:
            results: Test results dict with failure details
        """
        self.tests_generated = True
        self.tests_passed = False
        self.test_results = results
        self.test_attempts += 1

    def mark_enrichment_complete(self, source_url: Optional[str] = None) -> None:
        """Mark prompt enrichment as complete.

        Args:
            source_url: Optional URL that was used as reference
        """
        self.prompt_enriched = True
        self.enrichment_source_url = source_url

    def mark_audit_complete(self, discrepancies: int = 0) -> None:
        """Mark spec audit as complete.

        Args:
            discrepancies: Number of discrepancies found
        """
        self.spec_audit_completed = True
        self.spec_audit_discrepancies = discrepancies

    def mark_audit_fix_attempted(self) -> None:
        """Mark that an audit fix attempt was made."""
        self.audit_fix_attempted = True

    def to_dict(self) -> dict:
        """Serialize state to dictionary."""
        return {
            "phase": self.phase.value,
            "idea": self.idea,
            "project_dir": self.project_dir,
            "stack_id": self.stack_id,
            "design_revision": self.design_revision,
            "review_status": self.review_status.value,
            "build_attempts": self.build_attempts,
            "last_build_error": self.last_build_error,
            "deployment_url": self.deployment_url,
            "deployment_verified": self.deployment_verified,
            "last_error": self.last_error,
            "error_count": self.error_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "phase_history": self.phase_history,
            # Enhancement mode
            "enhancement_mode": self.enhancement_mode,
            "enhance_features": self.enhance_features,
            "original_design_path": self.original_design_path,
            # v5.0: Deployment-aware tracking
            "deployment_target": self.deployment_target,
            "database_type": self.database_type,
            "verification_results": self.verification_results,
            "verification_attempts": self.verification_attempts,
            # v5.1: Test tracking
            "tests_generated": self.tests_generated,
            "tests_passed": self.tests_passed,
            "test_results": self.test_results,
            "test_attempts": self.test_attempts,
            # v6.0: Prompt enrichment tracking
            "prompt_enriched": self.prompt_enriched,
            "enriched_prompt": self.enriched_prompt,
            "enrichment_source_url": self.enrichment_source_url,
            # v6.0: Spec audit tracking
            "spec_audit_completed": self.spec_audit_completed,
            "spec_audit_discrepancies": self.spec_audit_discrepancies,
            "spec_audit_critical_count": self.spec_audit_critical_count,
            "audit_fix_attempted": self.audit_fix_attempted,
            # v7.0: Swift/SwiftUI plugin architecture
            "build_mode": self.build_mode,
            "plugin_packaged": self.plugin_packaged,
        }

    def to_json(self) -> str:
        """Serialize state to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentState":
        """Deserialize state from dictionary."""
        state = cls()
        state.phase = Phase(data.get("phase", "init"))
        state.idea = data.get("idea", "")
        state.project_dir = data.get("project_dir", "")
        state.stack_id = data.get("stack_id")
        state.design_revision = data.get("design_revision", 0)
        state.review_status = ReviewStatus(data.get("review_status", "pending"))
        state.build_attempts = data.get("build_attempts", 0)
        state.last_build_error = data.get("last_build_error")
        state.deployment_url = data.get("deployment_url")
        state.deployment_verified = data.get("deployment_verified", False)
        state.last_error = data.get("last_error")
        state.error_count = data.get("error_count", 0)
        state.started_at = data.get("started_at")
        state.completed_at = data.get("completed_at")
        state.phase_history = data.get("phase_history", [])
        # Enhancement mode
        state.enhancement_mode = data.get("enhancement_mode", False)
        state.enhance_features = data.get("enhance_features", [])
        state.original_design_path = data.get("original_design_path")
        # v5.0: Deployment-aware tracking
        state.deployment_target = data.get("deployment_target")
        state.database_type = data.get("database_type")
        state.verification_results = data.get("verification_results", {})
        state.verification_attempts = data.get("verification_attempts", 0)
        # v5.1: Test tracking
        state.tests_generated = data.get("tests_generated", False)
        state.tests_passed = data.get("tests_passed", False)
        state.test_results = data.get("test_results", {})
        state.test_attempts = data.get("test_attempts", 0)
        # v6.0: Prompt enrichment tracking
        state.prompt_enriched = data.get("prompt_enriched", False)
        state.enriched_prompt = data.get("enriched_prompt")
        state.enrichment_source_url = data.get("enrichment_source_url")
        # v6.0: Spec audit tracking
        state.spec_audit_completed = data.get("spec_audit_completed", False)
        state.spec_audit_discrepancies = data.get("spec_audit_discrepancies", 0)
        state.spec_audit_critical_count = data.get("spec_audit_critical_count", 0)
        state.audit_fix_attempted = data.get("audit_fix_attempted", False)
        # v7.0: Swift/SwiftUI plugin architecture
        state.build_mode = data.get("build_mode", "standard")
        state.plugin_packaged = data.get("plugin_packaged", False)
        return state

    @classmethod
    def from_json(cls, json_str: str) -> "AgentState":
        """Deserialize state from JSON string."""
        return cls.from_dict(json.loads(json_str))


def create_initial_state(idea: str, project_dir: str) -> AgentState:
    """Create a new agent state for a build."""
    state = AgentState()
    state.idea = idea
    state.project_dir = project_dir
    state.mark_started()
    return state


def get_next_phase(current_phase: Phase, review_approved: bool = True) -> Phase:
    """Determine the next phase based on current phase and status.

    Args:
        current_phase: The current phase
        review_approved: Whether the design review was approved (only matters in REVIEW phase)

    Returns:
        The next phase to transition to
    """
    transitions = {
        Phase.INIT: Phase.ANALYSIS,
        Phase.ENRICH: Phase.ANALYSIS,  # v6.0: Enrich -> Analysis
        Phase.ANALYSIS: Phase.DESIGN,
        Phase.DESIGN: Phase.REVIEW,
        Phase.REVIEW: Phase.BUILD if review_approved else Phase.DESIGN,
        Phase.BUILD: Phase.AUDIT,  # v6.0: Build -> Audit
        Phase.AUDIT: Phase.TEST,  # v6.0: Audit -> Test
        Phase.TEST: Phase.DEPLOY,  # v5.1: Test -> Deploy
        Phase.DEPLOY: Phase.VERIFY,  # v5.0: Deploy -> Verify
        Phase.VERIFY: Phase.COMPLETE,  # v5.0: Verify -> Complete
    }
    return transitions.get(current_phase, Phase.FAILED)
