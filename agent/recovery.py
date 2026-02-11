"""Error recovery strategies for Product Agent v6.0.

Analyzes errors and provides targeted fix suggestions.
Includes SQLite/serverless detection and database migration prompts.
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class ErrorAnalysis:
    """Result of analyzing an error."""
    error_type: str
    action: str
    details: dict
    recovery_prompt: str
    requires_user: bool = False


# Patterns for common build errors
BUILD_ERROR_PATTERNS: dict[str, dict] = {
    # Module/Import errors
    r"Module not found: Can't resolve '([^']+)'": {
        "type": "missing_module",
        "action": "install_package",
    },
    r"Cannot find module '([^']+)'": {
        "type": "missing_module",
        "action": "install_package",
    },
    r"Module not found: Error: Can't resolve '([^']+)'": {
        "type": "missing_module",
        "action": "install_package",
    },

    # TypeScript errors
    r"Type '([^']+)' is not assignable to type '([^']+)'": {
        "type": "type_error",
        "action": "fix_types",
    },
    r"Property '([^']+)' does not exist on type '([^']+)'": {
        "type": "missing_property",
        "action": "fix_types",
    },
    r"'([^']+)' is not defined": {
        "type": "undefined_reference",
        "action": "add_import_or_define",
    },
    r"Cannot find name '([^']+)'": {
        "type": "undefined_reference",
        "action": "add_import_or_define",
    },

    # Syntax errors
    r"SyntaxError: ([^\n]+)": {
        "type": "syntax_error",
        "action": "fix_syntax",
    },
    r"Parsing error: ([^\n]+)": {
        "type": "syntax_error",
        "action": "fix_syntax",
    },

    # Component errors
    r"'([^']+)' cannot be used as a JSX component": {
        "type": "component_error",
        "action": "fix_component",
    },
    r"Error: ([^']+) is not a valid React element": {
        "type": "component_error",
        "action": "fix_component",
    },

    # Build config errors
    r"next\.config\.[jt]s[^\n]*error": {
        "type": "config_error",
        "action": "fix_config",
    },
}

# Patterns for deployment errors
DEPLOY_ERROR_PATTERNS: dict[str, dict] = {
    r"Error: Environment variable ([A-Z_]+) is missing": {
        "type": "missing_env",
        "action": "set_env_var",
        "requires_user": True,
    },
    r"Error: Command failed: vercel": {
        "type": "vercel_error",
        "action": "check_vercel_auth",
    },
    r"Error: Deployment failed": {
        "type": "deployment_failed",
        "action": "analyze_deploy_logs",
    },
    # v5.0: SQLite/serverless patterns
    r"SQLITE_CANTOPEN|unable to open database|no such table": {
        "type": "sqlite_serverless_error",
        "action": "switch_database",
    },
    r"ENOENT.*\.sqlite|sqlite.*ENOENT|\.db.*ENOENT": {
        "type": "sqlite_missing_error",
        "action": "switch_database",
    },
    r"sqlite.*not.*supported|sqlite.*serverless": {
        "type": "sqlite_incompatible",
        "action": "switch_database",
    },
}

# v5.0: Patterns for SQLite/database errors during build
BUILD_ERROR_PATTERNS_SQLITE: dict[str, dict] = {
    r"better-sqlite3|sqlite3.*native": {
        "type": "sqlite_native_error",
        "action": "switch_database_prisma",
    },
    r'provider.*=.*"sqlite".*vercel': {
        "type": "sqlite_vercel_config",
        "action": "switch_database_prisma",
    },
}

# Patterns for database errors
DATABASE_ERROR_PATTERNS: dict[str, dict] = {
    r'relation "([^"]+)" does not exist': {
        "type": "missing_table",
        "action": "run_migrations",
    },
    r"permission denied for table ([a-z_]+)": {
        "type": "rls_error",
        "action": "check_rls_policies",
    },
    r"duplicate key value violates unique constraint": {
        "type": "constraint_error",
        "action": "handle_duplicate",
    },
}


def analyze_error(error_message: str) -> ErrorAnalysis:
    """Analyze an error message and determine recovery strategy.

    Args:
        error_message: The error message to analyze

    Returns:
        ErrorAnalysis with the error type, action, and recovery prompt
    """
    # Check build errors first (most common)
    for pattern, config in BUILD_ERROR_PATTERNS.items():
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            return _create_analysis(config, match, error_message)

    # Check deployment errors
    for pattern, config in DEPLOY_ERROR_PATTERNS.items():
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            return _create_analysis(config, match, error_message)

    # Check database errors
    for pattern, config in DATABASE_ERROR_PATTERNS.items():
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            return _create_analysis(config, match, error_message)

    # Unknown error
    return ErrorAnalysis(
        error_type="unknown",
        action="investigate",
        details={"original_error": error_message},
        recovery_prompt=_get_generic_recovery_prompt(error_message),
    )


def _create_analysis(config: dict, match: re.Match, original_error: str) -> ErrorAnalysis:
    """Create an ErrorAnalysis from a pattern match."""
    error_type = config["type"]
    action = config["action"]
    requires_user = config.get("requires_user", False)

    details = {
        "matches": match.groups(),
        "original_error": original_error,
    }

    recovery_prompt = _get_recovery_prompt(error_type, action, match.groups(), original_error)

    return ErrorAnalysis(
        error_type=error_type,
        action=action,
        details=details,
        recovery_prompt=recovery_prompt,
        requires_user=requires_user,
    )


def _get_recovery_prompt(error_type: str, action: str, matches: tuple, original_error: str) -> str:
    """Generate a recovery prompt based on error type and action."""

    if action == "install_package":
        package = matches[0] if matches else "unknown"
        # Handle scoped packages and common aliases
        if package.startswith("@/"):
            return f"""The import alias '@/' is not resolving correctly.

Check that:
1. tsconfig.json has the correct path alias: "@/*": ["./src/*"]
2. The imported file exists at the expected path
3. The file extension is correct (.ts, .tsx, etc.)

Original error: {original_error}"""
        return f"""Install the missing package: npm install {package}

If it's a type definition, try: npm install -D @types/{package.replace('@', '').split('/')[0]}

Original error: {original_error}"""

    elif action == "fix_types":
        return f"""Fix the TypeScript error by:
1. Check the type definitions for the involved types
2. Add proper type annotations or type guards
3. If using external data, add proper type assertions

Original error: {original_error}"""

    elif action == "add_import_or_define":
        name = matches[0] if matches else "unknown"
        return f"""The identifier '{name}' is not defined.

1. If it's an import, add: import {{ {name} }} from 'appropriate-module'
2. If it's a variable, define it before use
3. If it's a type, import it from the types file

Original error: {original_error}"""

    elif action == "fix_syntax":
        return f"""Fix the syntax error:
1. Check for missing brackets, parentheses, or semicolons
2. Ensure JSX is properly closed
3. Check for typos in keywords

Original error: {original_error}"""

    elif action == "fix_component":
        return f"""Fix the React component error:
1. Ensure the component is a valid function or class component
2. Check that it returns valid JSX
3. Verify 'use client' directive if using hooks

Original error: {original_error}"""

    elif action == "set_env_var":
        var_name = matches[0] if matches else "UNKNOWN"
        return f"""Environment variable {var_name} is required.

This requires manual setup:
1. In Vercel: Settings > Environment Variables > Add {var_name}
2. Locally: Add to .env.local file

Original error: {original_error}"""

    elif action == "check_vercel_auth":
        return f"""Vercel deployment failed. Check:
1. Run 'vercel login' to authenticate
2. Ensure the project is linked: 'vercel link'
3. Check Vercel dashboard for more details

Original error: {original_error}"""

    elif action == "run_migrations":
        table = matches[0] if matches else "unknown"
        return f"""Database table '{table}' does not exist.

For Supabase:
1. Go to Supabase Dashboard > SQL Editor
2. Run the CREATE TABLE statement from DESIGN.md

For Prisma:
1. Run: npx prisma db push
2. Or: npx prisma migrate dev

Original error: {original_error}"""

    elif action == "check_rls_policies":
        return f"""Row Level Security is blocking the operation.

Check that RLS policies allow the current operation:
1. Verify the user is authenticated
2. Check the policy conditions match the user's context
3. Review DESIGN.md for the expected RLS policies

Original error: {original_error}"""

    elif action == "switch_database":
        return get_sqlite_fix_prompt("vercel", original_error)

    elif action == "switch_database_prisma":
        return get_sqlite_fix_prompt("vercel", original_error)

    return _get_generic_recovery_prompt(original_error)


def _get_generic_recovery_prompt(error_message: str) -> str:
    """Generate a generic recovery prompt for unknown errors."""
    return f"""An error occurred that needs investigation.

Steps to debug:
1. Read the full error message carefully
2. Identify the file and line number if provided
3. Check recent changes that might have caused this
4. Search for the error message online if unfamiliar

Error: {error_message}

Try to fix the root cause rather than working around it."""


def get_build_fix_prompt(error_message: str, attempt: int, max_attempts: int) -> str:
    """Generate a prompt for the builder to fix a build error.

    Args:
        error_message: The build error message
        attempt: Current attempt number (1-indexed)
        max_attempts: Maximum allowed attempts

    Returns:
        A prompt instructing the builder how to fix the error
    """
    analysis = analyze_error(error_message)

    return f"""## Build Failed (Attempt {attempt}/{max_attempts})

{analysis.recovery_prompt}

### Instructions
1. Identify the exact cause of the error
2. Make the minimal fix needed
3. Run `npm run build` again to verify

Do not make unrelated changes. Focus only on fixing this error."""


def get_deploy_fix_prompt(error_message: str, attempt: int) -> str:
    """Generate a prompt for the deployer to fix a deployment error.

    Args:
        error_message: The deployment error message
        attempt: Current attempt number

    Returns:
        A prompt instructing the deployer how to fix the error
    """
    analysis = analyze_error(error_message)

    if analysis.requires_user:
        return f"""## Deployment Requires Manual Setup

{analysis.recovery_prompt}

### Instructions
Document this requirement in the deployment output.
The deployment can proceed but will need user configuration."""

    return f"""## Deployment Failed (Attempt {attempt})

{analysis.recovery_prompt}

### Instructions
1. Fix the identified issue
2. Retry the deployment
3. If it fails again with the same error, document it as a known issue"""


def get_sqlite_fix_prompt(deployment_target: str, original_error: str = "") -> str:
    """Generate a detailed prompt for fixing SQLite on serverless issues.

    Args:
        deployment_target: The deployment target (e.g., "vercel")
        original_error: The original error message if available

    Returns:
        Detailed prompt with migration instructions
    """
    return f"""## SQLite Incompatibility Detected (v5.0)

**CRITICAL**: SQLite cannot be used with {deployment_target.title()} (serverless deployment).

### Why This Fails
SQLite stores data in a local file. Serverless platforms like {deployment_target.title()}:
- Run each request in an isolated container
- Do NOT persist filesystem between requests
- Reset state after each invocation

Any data written to SQLite is LOST after the request completes.

### Required Fix

**Option 1: Switch to PostgreSQL (Recommended)**

1. **Update Prisma Schema** (prisma/schema.prisma):
```prisma
datasource db {{
  provider = "postgresql"  // Changed from "sqlite"
  url      = env("DATABASE_URL")
}}
```

2. **Choose a Database Provider**:
   - **Supabase** (free tier): supabase.com
   - **Neon** (serverless PostgreSQL): neon.tech
   - **Vercel Postgres**: vercel.com/storage

3. **Get Connection String** from provider dashboard

4. **Set Environment Variable**:
   - Locally: Add to .env.local
   - Vercel: Settings > Environment Variables

5. **Push Schema**:
```bash
npx prisma db push
```

6. **Seed Database** (if needed):
```bash
npx tsx prisma/seed.ts
```

**Option 2: Switch Deployment Target**

If you need SQLite, deploy to a traditional platform:
- Railway (railway.app)
- Fly.io (fly.io)
- Render (render.com)

These provide persistent filesystem storage.

### Quick Fix Commands
```bash
# 1. Update schema provider
sed -i '' 's/provider = "sqlite"/provider = "postgresql"/' prisma/schema.prisma

# 2. Remove SQLite file reference
sed -i '' 's|file:./dev.db|env("DATABASE_URL")|' prisma/schema.prisma

# 3. Push to database (after setting DATABASE_URL)
npx prisma db push

# 4. Seed if needed
npx tsx prisma/seed.ts
```

{f"### Original Error" if original_error else ""}
{original_error if original_error else ""}
"""


def is_sqlite_serverless_error(error_message: str) -> bool:
    """Check if an error is related to SQLite on serverless.

    Args:
        error_message: The error message to check

    Returns:
        True if this appears to be an SQLite/serverless issue
    """
    sqlite_patterns = [
        r"SQLITE_CANTOPEN",
        r"unable to open database",
        r"no such table",
        r"\.sqlite.*ENOENT",
        r"\.db.*ENOENT",
        r"ENOENT.*\.sqlite",
        r"sqlite.*not.*found",
        r"better-sqlite3",
    ]

    for pattern in sqlite_patterns:
        if re.search(pattern, error_message, re.IGNORECASE):
            return True

    return False
