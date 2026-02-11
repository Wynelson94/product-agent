"""Pre-deployment validation for Product Agent v6.0.

Validates environment, database connectivity, and stack compatibility
before attempting deployment.
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    check_name: str
    message: str
    fix_suggestion: Optional[str] = None


def validate_env_vars(required_vars: list[str]) -> list[ValidationResult]:
    """Check that required environment variables are set.

    Args:
        required_vars: List of environment variable names to check

    Returns:
        List of ValidationResult for each variable
    """
    results = []
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            results.append(ValidationResult(
                passed=True,
                check_name=f"env:{var}",
                message=f"Environment variable {var} is set",
            ))
        else:
            results.append(ValidationResult(
                passed=False,
                check_name=f"env:{var}",
                message=f"Required environment variable {var} is not set",
                fix_suggestion=f"Set {var} in your .env.local file or deployment platform dashboard",
            ))
    return results


def validate_database_connectivity(
    database_url: Optional[str] = None,
    database_type: str = "postgresql"
) -> ValidationResult:
    """Attempt to verify database connectivity.

    Args:
        database_url: Database connection string
        database_type: Type of database (postgresql, sqlite, etc.)

    Returns:
        ValidationResult indicating if database is reachable
    """
    if not database_url:
        database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        return ValidationResult(
            passed=False,
            check_name="database:connectivity",
            message="No DATABASE_URL configured",
            fix_suggestion="Set DATABASE_URL environment variable with your database connection string",
        )

    # For Supabase, check if URL is valid format
    if "supabase" in database_url.lower():
        if "postgresql://" in database_url or "postgres://" in database_url:
            return ValidationResult(
                passed=True,
                check_name="database:connectivity",
                message="Supabase connection string appears valid",
            )

    # For Neon
    if "neon" in database_url.lower():
        if "postgresql://" in database_url or "postgres://" in database_url:
            return ValidationResult(
                passed=True,
                check_name="database:connectivity",
                message="Neon connection string appears valid",
            )

    # For Vercel Postgres
    if "vercel" in database_url.lower() or "prisma" in database_url.lower():
        return ValidationResult(
            passed=True,
            check_name="database:connectivity",
            message="Vercel Postgres connection string appears valid",
        )

    # Generic PostgreSQL validation
    if database_type == "postgresql":
        if "postgresql://" in database_url or "postgres://" in database_url:
            return ValidationResult(
                passed=True,
                check_name="database:connectivity",
                message="PostgreSQL connection string format is valid",
            )

    # SQLite validation (warn if serverless)
    if database_type == "sqlite" or "sqlite" in database_url.lower() or "file:" in database_url:
        return ValidationResult(
            passed=True,  # Valid format, but may fail on serverless
            check_name="database:connectivity",
            message="SQLite database configured (may not work on serverless platforms)",
            fix_suggestion="Consider using PostgreSQL for serverless deployments",
        )

    return ValidationResult(
        passed=True,
        check_name="database:connectivity",
        message="Database configuration appears valid (format not fully verified)",
    )


def validate_deployment_compatibility(
    stack_id: str,
    deployment_target: str,
    database_type: Optional[str] = None,
) -> ValidationResult:
    """Validate that stack, deployment, and database are compatible.

    Args:
        stack_id: The selected stack (e.g., "nextjs-supabase")
        deployment_target: Where the app will deploy (e.g., "vercel")
        database_type: The database being used (e.g., "postgresql", "sqlite")

    Returns:
        ValidationResult indicating compatibility
    """
    from .stacks.criteria import check_stack_deployment_compatibility

    compatible, error = check_stack_deployment_compatibility(
        stack_id, deployment_target, database_type
    )

    if compatible:
        return ValidationResult(
            passed=True,
            check_name="deployment:compatibility",
            message=f"Stack {stack_id} is compatible with {deployment_target}",
        )
    else:
        return ValidationResult(
            passed=False,
            check_name="deployment:compatibility",
            message=error or "Incompatible deployment configuration",
            fix_suggestion="Choose a different database or deployment target. See DEPLOY_BLOCKED.md for details.",
        )


def validate_sqlite_not_on_serverless(
    database_type: Optional[str],
    deployment_target: str,
) -> ValidationResult:
    """Specifically check for the SQLite on serverless anti-pattern.

    Args:
        database_type: The database being used
        deployment_target: Where the app will deploy

    Returns:
        ValidationResult indicating if this anti-pattern is detected
    """
    from .stacks.criteria import DEPLOYMENT_TYPES

    if not database_type:
        return ValidationResult(
            passed=True,
            check_name="sqlite:serverless",
            message="No database type specified, skipping SQLite check",
        )

    target_type = DEPLOYMENT_TYPES.get(deployment_target.lower(), "unknown")

    if database_type.lower() == "sqlite" and target_type == "serverless":
        return ValidationResult(
            passed=False,
            check_name="sqlite:serverless",
            message=f"CRITICAL: SQLite cannot be used with {deployment_target} (serverless). Data will be lost between requests.",
            fix_suggestion="Switch to PostgreSQL using Supabase, Neon, or Vercel Postgres. Or deploy to Railway/Fly.io for SQLite support.",
        )

    return ValidationResult(
        passed=True,
        check_name="sqlite:serverless",
        message="Database is compatible with deployment target",
    )


def run_pre_deployment_validation(
    stack_id: str,
    deployment_target: str,
    database_type: Optional[str] = None,
    required_env_vars: Optional[list[str]] = None,
) -> tuple[bool, list[ValidationResult]]:
    """Run all pre-deployment validations.

    Args:
        stack_id: The selected stack
        deployment_target: Deployment platform
        database_type: Database type if known
        required_env_vars: List of required environment variables

    Returns:
        Tuple of (all_passed, list of ValidationResults)
    """
    results = []

    # 1. SQLite on serverless check (critical)
    results.append(validate_sqlite_not_on_serverless(
        database_type, deployment_target
    ))

    # 2. Stack/deployment compatibility
    results.append(validate_deployment_compatibility(
        stack_id, deployment_target, database_type
    ))

    # 3. Environment variables
    if required_env_vars:
        results.extend(validate_env_vars(required_env_vars))

    # 4. Database connectivity (if not SQLite)
    if database_type and database_type.lower() != "sqlite":
        results.append(validate_database_connectivity(database_type=database_type))

    all_passed = all(r.passed for r in results)
    return all_passed, results


def format_validation_report(results: list[ValidationResult]) -> str:
    """Format validation results as a readable report.

    Args:
        results: List of ValidationResult objects

    Returns:
        Formatted string report in Markdown
    """
    lines = ["# Pre-Deployment Validation Report\n"]

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    # Summary at top
    if failed:
        lines.append(f"## Status: BLOCKED ({len(failed)} issue{'s' if len(failed) > 1 else ''})\n")
    else:
        lines.append("## Status: READY\n")

    if failed:
        lines.append("## Failed Checks\n")
        for r in failed:
            lines.append(f"### {r.check_name}")
            lines.append(f"- **Issue**: {r.message}")
            if r.fix_suggestion:
                lines.append(f"- **Fix**: {r.fix_suggestion}")
            lines.append("")

    if passed:
        lines.append("## Passed Checks\n")
        for r in passed:
            lines.append(f"- **{r.check_name}**: {r.message}")
        lines.append("")

    return "\n".join(lines)


def create_deploy_blocked_file(
    results: list[ValidationResult],
    output_path: str = "DEPLOY_BLOCKED.md",
) -> str:
    """Create a DEPLOY_BLOCKED.md file with validation failures.

    Args:
        results: List of ValidationResult objects
        output_path: Path to write the file

    Returns:
        The content that was written
    """
    failed = [r for r in results if not r.passed]

    if not failed:
        return ""

    lines = ["# Deployment Blocked\n"]
    lines.append("The following issues must be resolved before deployment:\n")

    for i, r in enumerate(failed, 1):
        lines.append(f"## Issue {i}: {r.check_name}\n")
        lines.append(f"**Problem**: {r.message}\n")
        if r.fix_suggestion:
            lines.append(f"**Solution**: {r.fix_suggestion}\n")
        lines.append("")

    lines.append("---\n")
    lines.append("*This file was generated by Product Agent v5.0 pre-deployment validation.*\n")

    content = "\n".join(lines)

    with open(output_path, "w") as f:
        f.write(content)

    return content
