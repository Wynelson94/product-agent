"""Test validation and result parsing for Product Agent v6.0.

Validates test generation and execution, and parses test results
from different test runners (vitest, minitest, jest).
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import re
import json


@dataclass
class TestResults:
    """Results from running tests."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    coverage: Optional[float] = None
    status: str = "unknown"  # "passed", "failed", "no_tests"
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "coverage": self.coverage,
            "status": self.status,
            "error_message": self.error_message,
        }


def parse_test_results_md(content: str) -> TestResults:
    """Parse TEST_RESULTS.md content and extract test results.

    Args:
        content: The content of TEST_RESULTS.md

    Returns:
        TestResults with parsed data
    """
    results = TestResults()

    # Parse status
    status_match = re.search(r'Status:\s*(PASSED|FAILED|NO_TESTS)', content, re.IGNORECASE)
    if status_match:
        results.status = status_match.group(1).lower()

    # Parse test counts
    tests_run_match = re.search(r'Tests Run:\s*(\d+)', content)
    if tests_run_match:
        results.total = int(tests_run_match.group(1))

    passed_match = re.search(r'Passed:\s*(\d+)', content)
    if passed_match:
        results.passed = int(passed_match.group(1))

    failed_match = re.search(r'Failed:\s*(\d+)', content)
    if failed_match:
        results.failed = int(failed_match.group(1))

    skipped_match = re.search(r'Skipped:\s*(\d+)', content)
    if skipped_match:
        results.skipped = int(skipped_match.group(1))

    # Parse coverage
    coverage_match = re.search(r'Coverage:\s*([\d.]+)%', content)
    if coverage_match:
        results.coverage = float(coverage_match.group(1))

    return results


def parse_vitest_output(output: str) -> TestResults:
    """Parse vitest CLI output.

    Args:
        output: Raw output from vitest run

    Returns:
        TestResults with parsed data
    """
    results = TestResults()

    # Look for test summary line
    # Example: "Tests  3 passed | 1 failed (4)"
    # Example: "Tests  3 passed (3)"
    tests_match = re.search(
        r'Tests\s+(?:(\d+)\s+passed)?(?:\s*\|\s*(\d+)\s+failed)?',
        output
    )
    if tests_match:
        results.passed = int(tests_match.group(1) or 0)
        results.failed = int(tests_match.group(2) or 0)
        results.total = results.passed + results.failed

    # Alternative format: "Test Files  1 passed (1)"
    if results.total == 0:
        files_match = re.search(r'Test Files\s+(\d+)\s+passed', output)
        if files_match:
            # Just mark as having tests if we see this
            results.passed = 1
            results.total = 1

    # Coverage from vitest
    # Example: "All files     |   85.5 |   75.0 |   90.0 |   85.5"
    coverage_match = re.search(r'All files\s+\|\s+([\d.]+)', output)
    if coverage_match:
        results.coverage = float(coverage_match.group(1))

    # Determine status
    if results.total == 0:
        results.status = "no_tests"
    elif results.failed > 0:
        results.status = "failed"
    else:
        results.status = "passed"

    return results


def parse_minitest_output(output: str) -> TestResults:
    """Parse Rails minitest output.

    Args:
        output: Raw output from rails test

    Returns:
        TestResults with parsed data
    """
    results = TestResults()

    # Example: "10 runs, 15 assertions, 0 failures, 0 errors, 0 skips"
    match = re.search(
        r'(\d+)\s+runs,\s+\d+\s+assertions,\s+(\d+)\s+failures,\s+(\d+)\s+errors,\s+(\d+)\s+skips',
        output
    )
    if match:
        results.total = int(match.group(1))
        failures = int(match.group(2))
        errors = int(match.group(3))
        results.skipped = int(match.group(4))
        results.failed = failures + errors
        results.passed = results.total - results.failed - results.skipped

    # Determine status
    if results.total == 0:
        results.status = "no_tests"
    elif results.failed > 0:
        results.status = "failed"
    else:
        results.status = "passed"

    return results


def parse_jest_output(output: str) -> TestResults:
    """Parse Jest output (for Expo).

    Args:
        output: Raw output from jest

    Returns:
        TestResults with parsed data
    """
    results = TestResults()

    # Example: "Tests:       2 failed, 8 passed, 10 total"
    match = re.search(
        r'Tests:\s+(?:(\d+)\s+failed,\s+)?(\d+)\s+passed,\s+(\d+)\s+total',
        output
    )
    if match:
        results.failed = int(match.group(1) or 0)
        results.passed = int(match.group(2))
        results.total = int(match.group(3))

    # Coverage: "All files | 85.5 |"
    coverage_match = re.search(r'All files\s+\|\s+([\d.]+)', output)
    if coverage_match:
        results.coverage = float(coverage_match.group(1))

    # Determine status
    if results.total == 0:
        results.status = "no_tests"
    elif results.failed > 0:
        results.status = "failed"
    else:
        results.status = "passed"

    return results


def check_tests_exist(project_path: Path, stack_id: str) -> tuple[bool, list[str]]:
    """Check if test files exist in the project.

    Args:
        project_path: Path to the project
        stack_id: The stack being used

    Returns:
        Tuple of (tests_exist, list of test files found)
    """
    test_patterns = {
        "nextjs-supabase": ["**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts", "**/*.spec.tsx"],
        "nextjs-prisma": ["**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts", "**/*.spec.tsx"],
        "rails": ["test/**/*_test.rb", "spec/**/*_spec.rb"],
        "expo-supabase": ["**/*.test.ts", "**/*.test.tsx", "__tests__/**/*.ts", "__tests__/**/*.tsx"],
    }

    patterns = test_patterns.get(stack_id, ["**/*.test.*", "**/*.spec.*"])
    test_files = []

    for pattern in patterns:
        test_files.extend(project_path.glob(pattern))

    # Filter out node_modules and other irrelevant directories
    excluded_dirs = ["node_modules", ".next", "dist", "build", ".git"]
    test_files = [
        f for f in test_files
        if not any(excluded in str(f) for excluded in excluded_dirs)
    ]

    return len(test_files) > 0, [str(f) for f in test_files]


def validate_test_infrastructure(project_path: Path, stack_id: str) -> tuple[bool, str]:
    """Validate that test infrastructure is set up correctly.

    Args:
        project_path: Path to the project
        stack_id: The stack being used

    Returns:
        Tuple of (is_valid, error_message if not valid)
    """
    if stack_id in ["nextjs-supabase", "nextjs-prisma"]:
        # Check for vitest.config.ts
        if not (project_path / "vitest.config.ts").exists():
            return False, "Missing vitest.config.ts - test infrastructure not set up"

        # Check for test script in package.json
        package_json = project_path / "package.json"
        if package_json.exists():
            with open(package_json) as f:
                pkg = json.load(f)
            if "test" not in pkg.get("scripts", {}):
                return False, "Missing 'test' script in package.json"

    elif stack_id == "rails":
        # Check for test directory
        if not (project_path / "test").exists():
            return False, "Missing test/ directory"

        # Check for test_helper.rb
        if not (project_path / "test" / "test_helper.rb").exists():
            return False, "Missing test/test_helper.rb"

    elif stack_id == "expo-supabase":
        # Check for jest.config.js
        if not (project_path / "jest.config.js").exists():
            return False, "Missing jest.config.js - test infrastructure not set up"

    return True, ""


def should_block_deployment(results: TestResults, require_passing: bool = True) -> tuple[bool, str]:
    """Determine if deployment should be blocked based on test results.

    Args:
        results: The test results
        require_passing: Whether passing tests are required for deployment

    Returns:
        Tuple of (should_block, reason)
    """
    if not require_passing:
        return False, ""

    if results.status == "no_tests":
        return True, "No tests were found or executed"

    if results.status == "failed":
        return True, f"Tests failed: {results.failed} of {results.total} tests failed"

    return False, ""


def generate_test_results_md(results: TestResults, test_files: list[str]) -> str:
    """Generate TEST_RESULTS.md content.

    Args:
        results: The test results
        test_files: List of test file paths

    Returns:
        Markdown content for TEST_RESULTS.md
    """
    status_emoji = {
        "passed": "PASSED",
        "failed": "FAILED",
        "no_tests": "NO_TESTS",
        "unknown": "UNKNOWN",
    }

    coverage_str = f"{results.coverage:.1f}%" if results.coverage is not None else "N/A"

    files_section = "\n".join(
        f"- [{'x' if results.status == 'passed' else ' '}] {f}"
        for f in test_files
    )

    return f"""# Test Results

## Summary
- **Tests Run**: {results.total}
- **Passed**: {results.passed}
- **Failed**: {results.failed}
- **Skipped**: {results.skipped}
- **Coverage**: {coverage_str}

## Test Files
{files_section if files_section else "No test files found"}

## Status: {status_emoji.get(results.status, 'UNKNOWN')}
"""
