"""Quality scoring for Product Agent v8.0.

Computes a confidence score after all phases complete. Factors in
test results, spec coverage, build attempts, and design revisions.
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

    Factors:
    - Test pass rate (30 points max)
    - Spec coverage (20 points max)
    - Build efficiency (20 points max) — fewer attempts = better
    - Design quality (15 points max) — fewer revisions = better
    - Verification (15 points max)
    """
    factors: dict[str, int] = {}
    notes: list[str] = []

    # Test pass rate (30 points)
    if state.tests_generated and state.tests_passed:
        factors["tests"] = 30
    elif state.tests_generated:
        factors["tests"] = 10
        notes.append("Tests generated but some failed")
    else:
        factors["tests"] = 0
        notes.append("No tests generated")

    # Spec coverage (20 points)
    if state.spec_audit_completed:
        if state.spec_audit_discrepancies == 0:
            factors["spec_coverage"] = 20
        elif state.spec_audit_discrepancies <= 2:
            factors["spec_coverage"] = 15
            notes.append(f"{state.spec_audit_discrepancies} spec discrepancies")
        else:
            factors["spec_coverage"] = 5
            notes.append(f"{state.spec_audit_discrepancies} spec discrepancies — needs attention")
    else:
        factors["spec_coverage"] = 10  # Neutral if not audited
        notes.append("Spec audit not completed")

    # Build efficiency (20 points)
    if state.build_attempts <= 1:
        factors["build_efficiency"] = 20
    elif state.build_attempts == 2:
        factors["build_efficiency"] = 15
        notes.append("Build needed 1 retry")
    elif state.build_attempts == 3:
        factors["build_efficiency"] = 10
        notes.append("Build needed 2 retries")
    else:
        factors["build_efficiency"] = 5
        notes.append(f"Build needed {state.build_attempts - 1} retries")

    # Design quality (15 points)
    if state.design_revision == 0:
        factors["design_quality"] = 15
    elif state.design_revision == 1:
        factors["design_quality"] = 10
        notes.append("Design required 1 revision")
    else:
        factors["design_quality"] = 5
        notes.append(f"Design required {state.design_revision} revisions")

    # Verification (15 points)
    if state.deployment_verified:
        factors["verification"] = 15
    elif state.deployment_url:
        factors["verification"] = 8
        notes.append("Deployed but not fully verified")
    else:
        factors["verification"] = 5
        notes.append("No deployment verification")

    # Compute total
    total = sum(factors.values())
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
        "tests": "Tests",
        "spec_coverage": "Spec Coverage",
        "build_efficiency": "Build Efficiency",
        "design_quality": "Design Quality",
        "verification": "Verification",
    }

    max_points = {
        "tests": 30,
        "spec_coverage": 20,
        "build_efficiency": 20,
        "design_quality": 15,
        "verification": 15,
    }

    for key, label in labels.items():
        score = report.factors.get(key, 0)
        maximum = max_points.get(key, 0)
        bar_len = int((score / maximum) * 10) if maximum > 0 else 0
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(f"  {label:<18} {bar} {score}/{maximum}")

    if report.notes:
        lines.append("")
        lines.append("Notes:")
        for note in report.notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)
