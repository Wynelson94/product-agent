"""Phase output validators for Product Agent v9.0.

Code-level validation between phases. Each validator checks that the
previous phase produced its required artifacts with expected content.

v9.0: Artifacts use YAML front-matter as the primary structured data
contract. Regex parsing is kept as a fallback for backwards compatibility.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .state import Phase
from .stacks.criteria import STACKS


def _parse_frontmatter(content: str) -> dict | None:
    """Parse YAML front-matter from the start of a markdown file.

    Expects the document to start with ``---`` followed by key: value lines
    and closed by another ``---``.  Returns a dict of parsed values or None
    if no valid front-matter is found.

    Handles string, int, float, and boolean values.  Does NOT depend on
    PyYAML — we only need flat key-value pairs.
    """
    content = content.lstrip()
    if not content.startswith("---"):
        return None

    end = content.find("---", 3)
    if end == -1:
        return None

    block = content[3:end].strip()
    if not block:
        return None

    result: dict = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        # Strip optional quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        # Type coercion
        lower = value.lower()
        if lower in ("true", "yes"):
            result[key] = True
        elif lower in ("false", "no"):
            result[key] = False
        elif lower in ("null", "none", "~", ""):
            result[key] = None
        else:
            try:
                result[key] = int(value)
            except ValueError:
                try:
                    result[key] = float(value)
                except ValueError:
                    result[key] = value

    return result if result else None


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

    # Try front-matter first (v9.0)
    fm = _parse_frontmatter(content)
    if fm and fm.get("stack_id"):
        stack_id = str(fm["stack_id"])
        if stack_id in STACKS:
            result.extracted["stack_id"] = stack_id
            result.add_info(f"Stack selected (front-matter): {stack_id}")
            return result
        else:
            result.add_error(f"Unknown stack ID in front-matter: {stack_id}")
            return result

    # Fallback: regex parsing
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


def _extract_design_routes(project_dir: Path) -> list[str]:
    """Extract expected routes from DESIGN.md.

    Parses the Pages/Routes table for route paths like ``/login``,
    ``/dashboard``, ``/api/items``, etc.

    Returns:
        List of route paths (e.g., ["/", "/login", "/dashboard"])
    """
    design_file = project_dir / "DESIGN.md"
    if not design_file.exists():
        return []

    content = design_file.read_text()
    routes: list[str] = []

    # Match markdown table rows with route paths: | /some/route | ...
    for match in re.finditer(r'\|\s*(/[\w/\-\[\]:]*)\s*\|', content):
        route = match.group(1).strip()
        # Exclude /api routes — they don't have page.tsx files in Next.js App Router.
        # API routes are backend endpoints validated separately during build.
        if route and not route.startswith("/api"):
            routes.append(route)

    return routes


def _route_to_page_path(route: str) -> str:
    """Convert a route path to the expected Next.js App Router page file.

    Examples:
        "/" → "src/app/page.tsx"
        "/login" → "src/app/login/page.tsx"
        "/dashboard/[id]" → "src/app/dashboard/[id]/page.tsx"
    """
    if route == "/":
        return "src/app/page.tsx"
    segments = route.strip("/").split("/")
    return f"src/app/{'/'.join(segments)}/page.tsx"


def validate_build_routes(
    project_dir: Path,
    strict: bool = False,
) -> ValidationResult:
    """Validate that expected routes from DESIGN.md have corresponding files.

    Args:
        project_dir: Project directory
        strict: If True, missing routes are errors; otherwise info/warnings

    Returns:
        ValidationResult with missing_routes in extracted dict
    """
    result = ValidationResult(passed=True, phase=Phase.BUILD)
    project_dir = Path(project_dir)

    expected_routes = _extract_design_routes(project_dir)
    if not expected_routes:
        result.add_info("No routes extracted from DESIGN.md — skipping route check")
        # Fall through to Prisma/middleware checks below
    else:
        missing: list[str] = []
        found: list[str] = []

        for route in expected_routes:
            page_path = _route_to_page_path(route)
            if (project_dir / page_path).exists():
                found.append(route)
            elif (project_dir / page_path.replace(".tsx", ".ts")).exists():
                found.append(route)
            elif (project_dir / page_path.replace("src/app/", "app/")).exists():
                found.append(route)
            else:
                missing.append(route)

        result.extracted["expected_routes"] = len(expected_routes)
        result.extracted["found_routes"] = len(found)
        result.extracted["missing_routes"] = missing

        if missing:
            msg = f"Missing {len(missing)}/{len(expected_routes)} routes: {', '.join(missing[:5])}"
            if strict:
                result.add_error(msg)
            else:
                result.add_info(msg)
        else:
            result.add_info(f"All {len(expected_routes)} routes found")

    # Check for Prisma schema (if prisma stack)
    if (project_dir / "prisma").exists():
        schema = project_dir / "prisma" / "schema.prisma"
        if not schema.exists():
            msg = "prisma/ directory exists but schema.prisma is missing"
            if strict:
                result.add_error(msg)
            else:
                result.add_info(msg)
        else:
            schema_content = schema.read_text()
            model_count = len(re.findall(r'^model\s+\w+', schema_content, re.MULTILINE))
            if model_count == 0:
                msg = "schema.prisma has no models defined"
                if strict:
                    result.add_error(msg)
                else:
                    result.add_info(msg)
            else:
                result.add_info(f"Prisma schema: {model_count} models")

    # Check for middleware.ts (auth stacks)
    # If the design mentions "auth", we expect a Next.js middleware file to exist.
    # middleware.ts handles route protection (redirecting unauthenticated users).
    design = project_dir / "DESIGN.md"
    if design.exists() and "auth" in design.read_text().lower():
        for mw_path in ["src/middleware.ts", "middleware.ts", "src/middleware.js"]:
            if (project_dir / mw_path).exists():
                result.add_info(f"Auth middleware: {mw_path}")
                break
        else:
            # Python for/else: the else block runs when the loop finishes WITHOUT
            # hitting break — meaning no middleware file was found in any path.
            msg = "Auth mentioned in design but no middleware.ts found"
            if strict:
                result.add_error(msg)
            else:
                result.add_info(msg)

    return result


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

    # Try front-matter first (v9.0)
    fm = _parse_frontmatter(content)
    if fm and "verdict" in fm:
        verdict = str(fm["verdict"]).lower()
        if verdict == "approved":
            result.extracted["approved"] = True
            result.add_info("Design APPROVED (front-matter)")
        elif verdict in ("needs_revision", "needs revision"):
            result.extracted["approved"] = False
            result.extracted["feedback"] = content
            result.add_info("Design NEEDS REVISION (front-matter)")
        else:
            result.extracted["approved"] = False
            result.extracted["verdict_uncertain"] = True
            result.add_info(f"Unknown verdict in front-matter: {verdict}")
        return result

    # Fallback: keyword search
    if "approved" in content_lower:
        result.extracted["approved"] = True
        result.add_info("Design APPROVED")
    elif "needs_revision" in content_lower or "needs revision" in content_lower:
        result.extracted["approved"] = False
        result.extracted["feedback"] = content
        result.add_info("Design NEEDS REVISION")
    else:
        result.add_info("Review verdict unclear — requires re-review")
        result.extracted["approved"] = False
        result.extracted["verdict_uncertain"] = True

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

    # v10.0: Cross-check DESIGN.md dependencies against package.json
    design_path = project_dir / "DESIGN.md"
    package_path = project_dir / "package.json"
    if design_path.exists() and package_path.exists():
        import json as _json
        design_content = design_path.read_text()
        try:
            pkg = _json.loads(package_path.read_text())
            all_deps: set[str] = set()
            all_deps.update(pkg.get("dependencies", {}).keys())
            all_deps.update(pkg.get("devDependencies", {}).keys())

            # Extract npm package references from DESIGN.md (pattern: @scope/name or bare-name)
            import_pattern = re.compile(r"`(@[\w-]+/[\w.-]+)`")
            design_packages = {m.group(1) for m in import_pattern.finditer(design_content)}

            # Filter to scoped packages (@scope/name) — these are unambiguously npm packages
            missing = design_packages - all_deps
            if missing:
                result.extracted["missing_deps"] = sorted(missing)
                for dep in sorted(missing):
                    result.add_info(f"DESIGN.md references '{dep}' but not in package.json")
        except (ValueError, KeyError):
            pass  # Malformed package.json — don't block on this

    # Post-build functional check: verify expected routes exist (v9.0)
    route_result = validate_build_routes(project_dir, strict=False)
    if route_result.extracted.get("missing_routes"):
        missing_routes = route_result.extracted["missing_routes"]
        result.extracted["missing_routes"] = missing_routes
        for route in missing_routes:
            result.add_info(f"Missing route: {route}")

    return result


def _apply_critical_override(result: ValidationResult, content: str) -> None:
    """Override audit PASS status when CRITICAL discrepancies exist in the body.

    v10.0: The auditor sometimes reports status: PASS despite finding CRITICAL
    issues. This function scans the audit body for CRITICAL markers in
    discrepancy tables and overrides the status to failed.
    """
    if result.extracted.get("passed") is not True:
        return  # Already failing, no override needed

    content_lower = content.lower()
    # Look for CRITICAL in table rows (| CRITICAL |) or structured markers
    has_critical = (
        "| critical |" in content_lower
        or "severity: critical" in content_lower
        or "| critical|" in content_lower
    )
    if has_critical:
        # Count occurrences of "critical" in table row context
        # Each "| CRITICAL |" or "| CRITICAL|" is one finding
        critical_count = content_lower.count("| critical |") + content_lower.count("| critical|")
        if critical_count == 0:
            critical_count = 1  # At least 1 from "severity: critical"
        result.extracted["passed"] = False
        result.extracted["critical_count"] = critical_count
        result.add_info(
            f"Audit overridden: {critical_count} CRITICAL finding(s) "
            f"found despite PASS status"
        )


def _validate_audit(project_dir: Path) -> ValidationResult:
    """Validate auditor output: SPEC_AUDIT.md with verdict."""
    result = ValidationResult(passed=True, phase=Phase.AUDIT)
    audit_file = project_dir / "SPEC_AUDIT.md"

    if not audit_file.exists():
        result.add_error("SPEC_AUDIT.md not found — audit was not completed")
        return result

    content = audit_file.read_text()
    content_lower = content.lower()

    # Try front-matter first (v9.0)
    fm = _parse_frontmatter(content)
    if fm:
        if "requirements_met" in fm and isinstance(fm["requirements_met"], int):
            result.extracted["requirements_met"] = fm["requirements_met"]
            total = fm.get("requirements_total")
            if isinstance(total, int):
                result.extracted["requirements_total"] = total
            result.add_info(f"Spec coverage (front-matter): {fm['requirements_met']}/{total or '?'}")
        if "discrepancies" in fm and isinstance(fm["discrepancies"], int):
            result.extracted["discrepancies"] = fm["discrepancies"]
            result.add_info(f"Discrepancies (front-matter): {fm['discrepancies']}")
        status = str(fm.get("status", "")).lower()
        if status == "needs_fix":
            result.extracted["passed"] = False
            result.add_info("Audit status: NEEDS_FIX (front-matter)")
        elif status == "pass":
            result.extracted["passed"] = True
        elif status == "fail":
            result.extracted["passed"] = False
            result.add_info("Audit found issues (front-matter)")

        # v10.0: Override PASS when CRITICAL discrepancies exist in the audit body
        _apply_critical_override(result, content)
        return result

    # Fallback: regex parsing
    # Extract requirement counts — primary format: "X/Y requirements met"
    match = re.search(r'(\d+)\s*/\s*(\d+)', content)
    if match:
        met, total = int(match.group(1)), int(match.group(2))
        result.extracted["requirements_met"] = met
        result.extracted["requirements_total"] = total
        result.add_info(f"Spec coverage: {met}/{total}")

    # Fallback: "Discrepancies Found: N" (common audit output format)
    disc_match = re.search(r'discrepancies\s*found:\s*(\d+)', content_lower)
    if disc_match:
        result.extracted["discrepancies"] = int(disc_match.group(1))
        result.add_info(f"Discrepancies found: {disc_match.group(1)}")

    # Determine pass/fail status
    if "needs_fix" in content_lower or "status: needs_fix" in content_lower:
        result.extracted["passed"] = False
        result.add_info("Audit status: NEEDS_FIX")
    elif "pass" in content_lower:
        result.extracted["passed"] = True
    elif "fail" in content_lower:
        result.extracted["passed"] = False
        result.add_info("Audit found issues")

    # v10.0: Override PASS when CRITICAL discrepancies exist in the audit body
    _apply_critical_override(result, content)
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

    # Try front-matter first (v9.0)
    fm = _parse_frontmatter(content)
    if fm:
        if "tests_passed" in fm and isinstance(fm["tests_passed"], int):
            result.extracted["tests_passed"] = fm["tests_passed"]
            if "tests_total" in fm and isinstance(fm["tests_total"], int):
                result.extracted["tests_total"] = fm["tests_total"]
            result.add_info(f"Tests (front-matter): {fm['tests_passed']}/{fm.get('tests_total', '?')}")
        if "all_passed" in fm:
            result.extracted["all_passed"] = bool(fm["all_passed"])
            if not fm["all_passed"]:
                result.add_error("Tests FAILED (front-matter)")
        return result

    # Fallback: regex parsing — try multiple formats because Claude's test output
    # varies. Each pattern has a lambda extractor to normalize to (passed, total).
    count_patterns = [
        # "8 / 10 passed" or "8/10 passing" (most common format)
        (r'(\d+)\s*/\s*(\d+)\s*(passed|passing)', lambda m: (int(m.group(1)), int(m.group(2)))),
        # "3 of 10 passed" (natural language format)
        (r'(\d+)\s+of\s+(\d+)\s+(passed|passing)', lambda m: (int(m.group(1)), int(m.group(2)))),
        # "Passed: 8, Failed: 2, Total: 10" (structured test runner format)
        (r'passed:\s*(\d+).*total:\s*(\d+)', lambda m: (int(m.group(1)), int(m.group(2)))),
    ]
    for pattern, extractor in count_patterns:
        match = re.search(pattern, content_lower)
        if match:
            passed, total = extractor(match)
            result.extracted["tests_passed"] = passed
            result.extracted["tests_total"] = total
            result.add_info(f"Tests: {passed}/{total} passed")
            break
    else:
        # for/else: none of the count patterns matched, try simpler format
        # Try simple format: "12 tests passed"
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

    # Check for placeholder/localhost DATABASE_URL in deployment files.
    # A placeholder DATABASE_URL means the app will crash at runtime when it
    # tries to connect to the database. We catch this here to fail fast.
    deploy_md = project_dir / "DEPLOYMENT.md"
    if deploy_md.exists():
        deploy_content = deploy_md.read_text()
        deploy_lower = deploy_content.lower()
        placeholder_patterns = [
            "placeholder", "localhost", "your_database_url",
            "database_url_here", "postgres://user:password@localhost",
        ]
        for pattern in placeholder_patterns:
            # Require BOTH the placeholder keyword AND "database_url" mention.
            # This prevents false positives — "localhost" alone is too generic
            # (could appear in deploy docs without being a database URL).
            if pattern in deploy_lower and "database_url" in deploy_lower:
                result.add_error(
                    f"DATABASE_URL appears to be placeholder/localhost — app will be broken at runtime"
                )
                result.extracted["database_placeholder"] = True
                break

    # Try front-matter from DEPLOYMENT.md first (v9.0)
    if deploy_md.exists():
        fm = _parse_frontmatter(deploy_md.read_text())
        if fm and fm.get("url"):
            url = str(fm["url"])
            result.extracted["url"] = url
            result.add_info(f"Deployed to (front-matter): {url}")
            return result

    # Fallback: regex URL extraction
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
        result.add_error("VERIFICATION.md not found — verifier must produce this artifact")
        return result

    content = verify_file.read_text()
    content_lower = content.lower()

    # Try front-matter first (v9.0)
    fm = _parse_frontmatter(content)
    if fm and "verified" in fm:
        result.extracted["verified"] = bool(fm["verified"])
        if "endpoints_tested" in fm and isinstance(fm["endpoints_tested"], int):
            result.extracted["endpoints_tested"] = fm["endpoints_tested"]
        if "endpoints_passed" in fm and isinstance(fm["endpoints_passed"], int):
            result.extracted["endpoints_passed"] = fm["endpoints_passed"]
        if fm["verified"]:
            result.add_info("Verification PASSED (front-matter)")
        else:
            result.add_error("Verification FAILED (front-matter)")
        return result

    # Fallback: keyword search for pass/fail/success
    if "pass" in content_lower or "success" in content_lower:
        result.extracted["verified"] = True
        result.add_info("Verification PASSED")
    elif "fail" in content_lower:
        result.extracted["verified"] = False
        result.add_error("Verification FAILED")
    else:
        # No keywords found → default to False (not True). This prevents
        # the orchestrator from treating an empty/garbled VERIFICATION.md
        # as a passing verification. Explicit failure is safer than silent pass.
        result.extracted["verified"] = False
        result.add_error("Verification inconclusive — no pass/fail keywords found")

    return result
