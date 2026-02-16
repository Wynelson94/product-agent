"""Quality scoring for Product Agent v9.0.

Computes a confidence score after all phases complete. Prioritizes
product outcomes (does it work?) over process metrics (how many retries?).

Hard caps ensure broken deployments and untested builds cannot score highly.
"""

from dataclasses import dataclass
from pathlib import Path

from .state import AgentState
from .progress import PhaseResult


@dataclass
class QualityReport:
    """Detailed quality breakdown."""
    score: int  # 0-100
    grade: str  # A, A-, B+, B, B-, C, F
    factors: dict[str, int]  # factor name → score contribution
    notes: list[str]


def compute_quality_score(
    state: AgentState,
    phase_results: list[PhaseResult] | None = None,
) -> QualityReport:
    """Compute a quality score from build metrics.

    v9.0 weights — product outcomes prioritized over process metrics:
    - Verification (35 points max) — deployed app actually works
    - Test pass rate (25 points max) — tests exist AND pass
    - Spec coverage (20 points max) — 0 when audit skipped
    - Build efficiency (10 points max) — fewer attempts = better
    - Design quality (10 points max) — fewer revisions = better

    Hard caps:
    - deployment_verified=False → max grade C (score capped at 69)
    - tests_generated=False → max grade B- (score capped at 79)
    """
    factors: dict[str, int] = {}
    notes: list[str] = []

    # Verification (35 points) — most important: does the app work?
    if state.deployment_verified:
        factors["verification"] = 35
    elif state.deployment_url:
        factors["verification"] = 15
        notes.append("Deployed but not fully verified")
    else:
        factors["verification"] = 5
        notes.append("No deployment verification")

    # Test pass rate (25 points)
    if state.tests_generated and state.tests_passed:
        factors["tests"] = 25
    elif state.tests_generated:
        factors["tests"] = 8
        notes.append("Tests generated but some failed")
    else:
        factors["tests"] = 0
        notes.append("No tests generated")

    # Spec coverage (20 points)
    if state.spec_audit_completed:
        # v10.0: CRITICAL findings penalty — each CRITICAL finding costs 5 points
        critical_penalty = min(15, state.spec_audit_critical_count * 5)
        if state.spec_audit_discrepancies == 0 and state.spec_audit_critical_count == 0:
            factors["spec_coverage"] = 20
        elif state.spec_audit_critical_count > 0:
            factors["spec_coverage"] = max(0, 15 - critical_penalty)
            notes.append(f"{state.spec_audit_critical_count} CRITICAL audit finding(s)")
        elif state.spec_audit_discrepancies <= 2:
            factors["spec_coverage"] = 15
            notes.append(f"{state.spec_audit_discrepancies} spec discrepancies")
        else:
            factors["spec_coverage"] = 5
            notes.append(f"{state.spec_audit_discrepancies} spec discrepancies — needs attention")
    else:
        factors["spec_coverage"] = 0
        notes.append("Spec audit not completed")

    # Build efficiency (10 points)
    if state.build_attempts <= 1:
        factors["build_efficiency"] = 10
    elif state.build_attempts == 2:
        factors["build_efficiency"] = 7
        notes.append("Build needed 1 retry")
    elif state.build_attempts == 3:
        factors["build_efficiency"] = 4
        notes.append("Build needed 2 retries")
    else:
        factors["build_efficiency"] = 2
        notes.append(f"Build needed {state.build_attempts - 1} retries")

    # Design quality (10 points)
    if state.design_revision == 0:
        factors["design_quality"] = 10
    elif state.design_revision == 1:
        factors["design_quality"] = 7
        notes.append("Design required 1 revision")
    else:
        factors["design_quality"] = 3
        notes.append(f"Design required {state.design_revision} revisions")

    # Compute total
    total = sum(factors.values())

    # Hard caps prevent "quality theater" — a broken app that happened to build
    # on the first try would otherwise score 100%. These caps force the grade down
    # when critical outcomes are missing, regardless of process metrics.
    if not state.deployment_verified:
        if total > 69:
            total = 69  # 69 = grade C ceiling (70+ would be B-)
            notes.append("Score capped: deployment not verified (max grade C)")

    if not state.tests_generated:
        if total > 79:
            total = 79  # 79 = grade B- ceiling (80+ would be B)
            notes.append("Score capped: no tests generated (max grade B-)")

    # v10.0: CRITICAL audit findings cap — can't get A with CRITICAL issues
    if state.spec_audit_critical_count > 0:
        if total > 84:
            total = 84  # 84 = grade B ceiling (85+ would be B+)
            notes.append(
                f"Score capped: {state.spec_audit_critical_count} CRITICAL "
                f"audit finding(s) (max grade B)"
            )

    total = max(0, min(100, total))

    # Grade
    if total >= 95:
        grade = "A"
    elif total >= 90:
        grade = "A-"
    elif total >= 85:
        grade = "B+"
    elif total >= 80:
        grade = "B"
    elif total >= 70:
        grade = "B-"
    elif total >= 60:
        grade = "C"
    else:
        grade = "F"

    return QualityReport(
        score=total,
        grade=grade,
        factors=factors,
        notes=notes,
    )


def format_quality_report(report: QualityReport) -> str:
    """Format a quality report for display."""
    lines = [
        f"Quality: {report.grade} ({report.score}%)",
        "",
        "Breakdown:",
    ]

    labels = {
        "verification": "Verification",
        "tests": "Tests",
        "spec_coverage": "Spec Coverage",
        "build_efficiency": "Build Efficiency",
        "design_quality": "Design Quality",
    }

    max_points = {
        "verification": 35,
        "tests": 25,
        "spec_coverage": 20,
        "build_efficiency": 10,
        "design_quality": 10,
    }

    for key, label in labels.items():
        score = report.factors.get(key, 0)
        maximum = max_points.get(key, 0)
        # Scale score to a 10-character visual bar for compact terminal display
        bar_len = int((score / maximum) * 10) if maximum > 0 else 0
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(f"  {label:<18} {bar} {score}/{maximum}")

    if report.notes:
        lines.append("")
        lines.append("Notes:")
        for note in report.notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)
