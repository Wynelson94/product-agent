"""Phase output validators for Product Agent v8.0.

Code-level validation between phases. Each validator checks that the
previous phase produced its required artifacts with expected content.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .state import Phase
from .stacks.criteria import STACKS


@dataclass
class ValidationResult:
    """Result of validating a phase's output."""
    passed: bool
    phase: Phase
    messages: list[str] = field(default_factory=list)
    extracted: dict = field(default_factory=dict)

    def add_error(self, msg: str) -> None:
        self.messages.append(f"FAIL: {msg}")
        self.passed = False

    def add_info(self, msg: str) -> None:
        self.messages.append(f"INFO: {msg}")


def validate_phase_output(phase: Phase, project_dir: str | Path) -> ValidationResult:
    """Validate that a phase produced its required artifacts.

    Args:
        phase: The phase that just completed
        project_dir: Path to the project directory

    Returns:
        ValidationResult with pass/fail and messages
    """
    project_dir = Path(project_dir)
    validators = {
        Phase.ENRICH: _validate_enrich,
        Phase.ANALYSIS: _validate_analysis,
        Phase.DESIGN: _validate_design,
        Phase.REVIEW: _validate_review,
        Phase.BUILD: _validate_build,
        Phase.AUDIT: _validate_audit,
        Phase.TEST: _validate_test,
        Phase.DEPLOY: _validate_deploy,
        Phase.VERIFY: _validate_verify,
    }

    validator = validators.get(phase)
    if not validator:
        result = ValidationResult(passed=True, phase=phase)
        result.add_info(f"No validator defined for phase {phase.value}")
        return result

    return validator(project_dir)


def _validate_enrich(project_dir: Path) -> ValidationResult:
    """Validate enricher output: PROMPT.md exists."""
    result = ValidationResult(passed=True, phase=Phase.ENRICH)
    prompt_md = project_dir / "PROMPT.md"

    if not prompt_md.exists():
        result.add_error("PROMPT.md not created by enricher")
        return result

    content = prompt_md.read_text()
    if len(content) < 100:
        result.add_error(f"PROMPT.md too short ({len(content)} chars) — enrichment may have failed")

    result.add_info(f"PROMPT.md exists ({len(content)} chars)")
    return result


def _validate_analysis(project_dir: Path) -> ValidationResult:
    """Validate analyzer output: STACK_DECISION.md with valid stack ID."""
    result = ValidationResult(passed=True, phase=Phase.ANALYSIS)
    stack_file = project_dir / "STACK_DECISION.md"

    if not stack_file.exists():
        result.add_error("STACK_DECISION.md not created by analyzer")
        return result

    content = stack_file.read_text()

    # Extract stack ID
    stack_id = _extract_stack_id(content)
    if stack_id:
        if stack_id in STACKS:
            result.extracted["stack_id"] = stack_id
            result.add_info(f"Stack selected: {stack_id}")
        else:
            result.add_error(f"Unknown stack ID in STACK_DECISION.md: {stack_id}")
    else:
        # Try fallback detection
        for sid in STACKS:
            if sid in content:
                result.extracted["stack_id"] = sid
                result.add_info(f"Stack detected via fallback: {sid}")
                break
        else:
            result.add_error("No valid stack ID found in STACK_DECISION.md")

    return result


def _extract_stack_id(content: str) -> str | None:
    """Extract stack ID from STACK_DECISION.md content."""
    match = re.search(r'\*\*Stack ID\*\*:\s*`?(\S+?)`?\s*$', content, re.MULTILINE)
    if match:
        return match.group(1).strip('`')
    return None


def _validate_design(project_dir: Path) -> ValidationResult:
    """Validate designer output: DESIGN.md with required sections."""
    result = ValidationResult(passed=True, phase=Phase.DESIGN)
    design_file = project_dir / "DESIGN.md"

    if not design_file.exists():
        result.add_error("DESIGN.md not created by designer")
        return result

    content = design_file.read_text()

    if len(content) < 200:
        result.add_error(f"DESIGN.md too short ({len(content)} chars)")

    # Check for key sections (case-insensitive)
    content_lower = content.lower()
    required_sections = ["data model", "route", "auth"]
    for section in required_sections:
        if section in content_lower:
            result.add_info(f"Section found: {section}")
        else:
            result.add_info(f"Section missing (non-critical): {section}")

    return result


def _validate_review(project_dir: Path) -> ValidationResult:
    """Validate reviewer output: REVIEW.md with verdict."""
    result = ValidationResult(passed=True, phase=Phase.REVIEW)
    review_file = project_dir / "REVIEW.md"

    if not review_file.exists():
        # Review might be communicated via other means
        result.add_info("REVIEW.md not found — reviewer may have communicated directly")
        return result

    content = review_file.read_text()
    content_lower = content.lower()

    if "approved" in content_lower:
        result.extracted["approved"] = True
        result.add_info("Design APPROVED")
    elif "needs_revision" in content_lower or "needs revision" in content_lower:
        result.extracted["approved"] = False
        # Extract feedback
        result.extracted["feedback"] = content
        result.add_info("Design NEEDS REVISION")
    else:
        result.add_info("Review verdict unclear — treating as approved")
        result.extracted["approved"] = True

    return result


def _validate_build(project_dir: Path) -> ValidationResult:
    """Validate builder output: source code files exist."""
    result = ValidationResult(passed=True, phase=Phase.BUILD)

    # Check for source directories (web or Swift)
    source_dirs = [
        project_dir / "src",
        project_dir / "app",
        project_dir / "Sources",
        project_dir / "pages",
    ]

    has_source = False
    for src_dir in source_dirs:
        if src_dir.exists() and any(src_dir.rglob("*")):
            has_source = True
            file_count = sum(1 for _ in src_dir.rglob("*") if _.is_file())
            result.add_info(f"Source directory: {src_dir.name}/ ({file_count} files)")

    if not has_source:
        # Check for any code files in project root
        code_extensions = {".ts", ".tsx", ".js", ".jsx", ".py", ".rb", ".swift"}
        code_files = [f for f in project_dir.iterdir()
                      if f.is_file() and f.suffix in code_extensions]
        if code_files:
            has_source = True
            result.add_info(f"Code files in root: {len(code_files)}")

    if not has_source:
        result.add_error("No source code found after build")
        return result

    # Check for package files (indicates dependencies were configured)
    package_files = ["package.json", "Package.swift", "Gemfile", "pyproject.toml"]
    for pf in package_files:
        if (project_dir / pf).exists():
            result.add_info(f"Package file: {pf}")

    return result


def _validate_audit(project_dir: Path) -> ValidationResult:
    """Validate auditor output: SPEC_AUDIT.md with verdict."""
    result = ValidationResult(passed=True, phase=Phase.AUDIT)
    audit_file = project_dir / "SPEC_AUDIT.md"

    if not audit_file.exists():
        result.add_info("SPEC_AUDIT.md not found — audit may have been skipped")
        return result

    content = audit_file.read_text()
    content_lower = content.lower()

    # Extract requirement counts
    match = re.search(r'(\d+)\s*/\s*(\d+)', content)
    if match:
        met, total = int(match.group(1)), int(match.group(2))
        result.extracted["requirements_met"] = met
        result.extracted["requirements_total"] = total
        result.add_info(f"Spec coverage: {met}/{total}")

    if "pass" in content_lower:
        result.extracted["passed"] = True
    elif "fail" in content_lower:
        result.extracted["passed"] = False
        result.add_info("Audit found issues")

    return result


def _validate_test(project_dir: Path) -> ValidationResult:
    """Validate tester output: TEST_RESULTS.md with test counts."""
    result = ValidationResult(passed=True, phase=Phase.TEST)
    test_file = project_dir / "TEST_RESULTS.md"

    if not test_file.exists():
        result.add_error("TEST_RESULTS.md not created by tester")
        return result

    content = test_file.read_text()
    content_lower = content.lower()

    # Extract test counts
    match = re.search(r'(\d+)\s*/\s*(\d+)\s*(passed|passing)', content_lower)
    if match:
        passed, total = int(match.group(1)), int(match.group(2))
        result.extracted["tests_passed"] = passed
        result.extracted["tests_total"] = total
        result.add_info(f"Tests: {passed}/{total} passed")
    else:
        # Try alternative format
        match = re.search(r'(\d+)\s+tests?\s+(passed|passing)', content_lower)
        if match:
            result.extracted["tests_passed"] = int(match.group(1))
            result.add_info(f"Tests: {match.group(1)} passed")

    # Check for pass/fail status
    if "status: passed" in content_lower or "all tests pass" in content_lower:
        result.extracted["all_passed"] = True
    elif "status: failed" in content_lower or "tests failed" in content_lower:
        result.extracted["all_passed"] = False
        result.add_error("Tests FAILED")

    return result


def _validate_deploy(project_dir: Path) -> ValidationResult:
    """Validate deployer output: deployment URL."""
    result = ValidationResult(passed=True, phase=Phase.DEPLOY)

    # Check for DEPLOY_BLOCKED.md
    blocked_file = project_dir / "DEPLOY_BLOCKED.md"
    if blocked_file.exists():
        content = blocked_file.read_text()
        result.add_error(f"Deployment blocked: {content[:200]}")
        return result

    # Look for deployment URL in various places
    url = None

    # Check deployer output files
    for filename in ["DEPLOYMENT.md", "DEPLOY_RESULT.md"]:
        deploy_file = project_dir / filename
        if deploy_file.exists():
            content = deploy_file.read_text()
            url = _extract_url(content)
            if url:
                break

    # Check any .md files for URLs
    if not url:
        for md_file in project_dir.glob("*.md"):
            content = md_file.read_text()
            url = _extract_url(content)
            if url:
                break

    if url:
        result.extracted["url"] = url
        result.add_info(f"Deployed to: {url}")
    else:
        result.add_info("No deployment URL found — may need manual verification")

    return result


def _extract_url(content: str) -> str | None:
    """Extract a deployment URL from text."""
    patterns = [
        r'https?://[\w.-]+\.vercel\.app\b',
        r'https?://[\w.-]+\.railway\.app\b',
        r'https?://[\w.-]+\.fly\.dev\b',
        r'https?://[\w.-]+\.netlify\.app\b',
        r'https?://[\w.-]+\.onrender\.com\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(0)
    return None


def _validate_verify(project_dir: Path) -> ValidationResult:
    """Validate verifier output: VERIFICATION.md."""
    result = ValidationResult(passed=True, phase=Phase.VERIFY)
    verify_file = project_dir / "VERIFICATION.md"

    if not verify_file.exists():
        result.add_info("VERIFICATION.md not found — verification may have been skipped")
        return result

    content = verify_file.read_text()
    content_lower = content.lower()

    if "pass" in content_lower or "success" in content_lower:
        result.extracted["verified"] = True
        result.add_info("Verification PASSED")
    elif "fail" in content_lower:
        result.extracted["verified"] = False
        result.add_error("Verification FAILED")

    return result
