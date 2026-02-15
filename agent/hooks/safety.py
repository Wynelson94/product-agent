"""Safety hooks to block dangerous operations and auto-approve safe ones."""

import re
import shlex
from pathlib import Path
from typing import Any

# Patterns that should ALWAYS be blocked - these are destructive/dangerous
# These are regex patterns for precise matching
BLOCKED_BASH_PATTERNS = [
    r"rm\s+-rf\s+/\s*$",      # rm -rf / (end of command)
    r"rm\s+-rf\s+/\s*;",      # rm -rf /; (followed by another command)
    r"rm\s+-rf\s+/\*",        # rm -rf /*
    r"rm\s+-rf\s+~\s*$",      # rm -rf ~ (end of command)
    r"rm\s+-rf\s+~\s*;",      # rm -rf ~; (followed by another command)
    r"rm\s+-rf\s+~\/\*",      # rm -rf ~/*
    r"rm\s+-rf\s+\$HOME",     # rm -rf $HOME
    # Block writes to all block devices (not just sda)
    r">\s*/dev/(sd[a-z]|nvme\d+n\d+|mmcblk\d+|vd[a-z]|xvd[a-z])",
    r"mkfs",                  # mkfs (any filesystem format)
    r"dd\s+if=/dev/zero",     # dd if=/dev/zero
    r"dd\s+if=/dev/random",   # dd if=/dev/random
    r":\(\)\{.*:\|:.*\};:",   # Fork bomb
    r"chmod\s+-R\s+777\s+/\s*$",   # chmod -R 777 /
    r"chmod\s+-R\s+777\s+~",       # chmod -R 777 ~
    r"sudo\s+rm",             # sudo rm
    r"sudo\s+chmod",          # sudo chmod
    r"sudo\s+chown",          # sudo chown
    r"curl\s+.*\|\s*bash",    # curl ... | bash
    r"curl\s+.*\|\s*sh",      # curl ... | sh
    r"wget\s+.*\|\s*bash",    # wget ... | bash
    r"wget\s+.*\|\s*sh",      # wget ... | sh
    r"\|\s*/bin/bash",        # | /bin/bash (full path)
    r"\|\s*/bin/sh",          # | /bin/sh (full path)
    r"\|\s*bash\s*$",         # | bash (end of command)
    r"\|\s*sh\s*$",           # | sh (end of command)
    r"eval\s+\$\(",           # eval $(...)
    r"base64\s+-d\s*\|",      # base64 -d | (decoded execution)
]

# System directories that should NEVER be modified (prefix match)
PROTECTED_PATH_PREFIXES = [
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/var",
    "/root",
    "/System",   # macOS
    "/Library",  # macOS system
]

# File/directory patterns that should be protected (exact component match)
PROTECTED_PATH_PATTERNS = [
    ".ssh",
    ".aws",
    ".config",
    ".gnupg",
    ".kube",
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
    ".pem",
]

# Stricter safe command patterns using regex (not just prefixes)
SAFE_BASH_COMMANDS = [
    # Package managers - specific safe subcommands only
    r"^npm\s+(install|ci|run|test|build|start|init|version|list|outdated|audit)\b",
    r"^npx\s+[\w@/.-]+\s*",   # npx with package name
    r"^pnpm\s+(install|run|test|build|add|remove|list)\b",
    r"^yarn\s+(install|run|test|build|add|remove|list)\b",
    r"^bun\s+(install|run|test|build|add|remove)\b",
    # Node execution
    r"^node\s+",
    # Git read-only commands
    r"^git\s+(status|log|diff|branch|show|remote|fetch|tag|stash\s+list)\b",
    # Safe shell utilities
    r"^ls(\s|$)",
    r"^pwd\s*$",
    r"^cat\s+",
    r"^head\s+",
    r"^tail\s+",
    r"^wc\s+",
    r"^echo\s+",
    r"^which\s+",
    r"^type\s+",
    r"^mkdir\s+-p\s+",        # mkdir -p for creating directories
    r"^cd\s+",                # change directory
    r"^cp\s+",                # copy (within project)
    # Deployment
    r"^vercel\s+",
    # Build tools
    r"^next\s+",
    r"^vite\s+",
    r"^tsc\s+",
    r"^prisma\s+",
    r"^supabase\s+",
]


def is_path_protected(path: str) -> tuple[bool, str | None]:
    """Check if a path is protected using proper path resolution.

    Uses Path.expanduser() and resolve() for accurate path matching,
    avoiding false positives from substring matching.

    Handles macOS symlinks (e.g., /etc -> /private/etc) by checking
    both the raw path and the resolved path.
    """
    # Expand user home directory
    try:
        expanded = Path(path).expanduser()
        expanded_str = str(expanded)
    except (OSError, ValueError):
        expanded_str = path

    # Also get the resolved path (follows symlinks)
    try:
        resolved = Path(path).expanduser().resolve()
        resolved_str = str(resolved)
    except (OSError, ValueError):
        resolved_str = expanded_str

    # Check system directory prefixes against BOTH expanded and resolved paths
    # This handles macOS where /etc -> /private/etc, /var -> /private/var
    for prefix in PROTECTED_PATH_PREFIXES:
        # Check expanded path (raw path with ~ expanded)
        if expanded_str.startswith(prefix + "/") or expanded_str == prefix:
            return True, prefix
        # Check resolved path (symlinks followed)
        if resolved_str.startswith(prefix + "/") or resolved_str == prefix:
            return True, prefix

    # Check if any path component matches protected patterns
    try:
        parts = expanded.parts
    except (OSError, ValueError):
        parts = Path(path).parts

    for part in parts:
        for pattern in PROTECTED_PATH_PATTERNS:
            # Exact match or ends with pattern (for files like id_rsa.pub)
            if part == pattern or part.endswith(pattern):
                return True, pattern

    return False, None


def is_command_blocked(command: str) -> tuple[bool, str | None]:
    """Check if a bash command should be blocked, including chained commands.

    Splits commands on separators (;, &&, ||, |) and validates each segment
    to prevent attacks like 'safe-cmd; rm -rf /'.
    """
    # First check the full command for patterns that span segments
    for pattern in BLOCKED_BASH_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, pattern

    # Split on command separators to catch chained attacks.
    # Use shell-aware splitting to respect quoted strings.
    segments = _split_command_segments(command)

    # Check each segment individually
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        for pattern in BLOCKED_BASH_PATTERNS:
            if re.search(pattern, segment, re.IGNORECASE):
                return True, f"{pattern} (in segment)"

    return False, None


def _split_command_segments(command: str) -> list[str]:
    """Split a shell command on separators (;, &&, ||) while respecting quotes.

    Uses shlex to validate quoting, then splits unquoted separators using regex.
    Falls back to naive splitting if the command has unbalanced quotes.

    Returns:
        List of command segments
    """
    # Validate quoting — if quotes are balanced, we can do smart splitting
    try:
        shlex.split(command)
    except ValueError:
        # Unbalanced quotes — fall back to naive split (safer: may over-split)
        return _naive_split(command)

    # Replace quoted strings with placeholders to avoid splitting inside them
    placeholders: list[str] = []
    protected = command

    # Replace double-quoted strings
    def _replace_quoted(match: re.Match) -> str:
        placeholders.append(match.group(0))
        return f"__PLACEHOLDER_{len(placeholders) - 1}__"

    protected = re.sub(r'"(?:[^"\\]|\\.)*"', _replace_quoted, protected)
    protected = re.sub(r"'[^']*'", _replace_quoted, protected)

    # Split on unquoted separators
    parts = re.split(r'\s*(?:&&|\|\||;)\s*', protected)

    # Restore placeholders
    segments = []
    for part in parts:
        restored = part
        for i, placeholder in enumerate(placeholders):
            restored = restored.replace(f"__PLACEHOLDER_{i}__", placeholder)
        segments.append(restored)

    return segments


def _naive_split(command: str) -> list[str]:
    """Fall back to naive splitting on separators."""
    separators = [';', '&&', '||']
    segments = [command]
    for sep in separators:
        new_segments = []
        for seg in segments:
            new_segments.extend(seg.split(sep))
        segments = new_segments
    return segments


def is_command_safe(command: str) -> bool:
    """Check if a bash command is known to be safe using regex patterns.

    Uses stricter regex matching instead of simple prefix matching
    to prevent abuse like 'npm exec malicious-package'.
    """
    command_stripped = command.strip()

    for pattern in SAFE_BASH_COMMANDS:
        if re.match(pattern, command_stripped, re.IGNORECASE):
            return True

    return False


async def safety_hook(input_data: dict, tool_use_id: str | None, context: Any) -> dict:
    """Block dangerous operations before they execute.

    Returns a dict that can include:
    - hookSpecificOutput.permissionDecision: "allow" | "deny"
    - hookSpecificOutput.permissionDecisionReason: str
    """
    if input_data.get("hook_event_name") != "PreToolUse":
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Check Bash commands
    if tool_name == "Bash":
        command = tool_input.get("command", "")

        is_blocked, pattern = is_command_blocked(command)
        if is_blocked:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"BLOCKED: Dangerous command pattern '{pattern}'"
                }
            }

    # Check file operations on protected paths
    if tool_name in ["Write", "Edit"]:
        file_path = tool_input.get("file_path", "")

        is_protected, protected_path = is_path_protected(file_path)
        if is_protected:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"BLOCKED: Cannot modify protected path '{protected_path}'"
                }
            }

    # Allow the operation
    return {}


async def auto_approve_hook(input_data: dict, tool_use_id: str | None, context: Any) -> dict:
    """Auto-approve operations that are known to be safe."""
    if input_data.get("hook_event_name") != "PreToolUse":
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Always auto-approve read-only operations
    read_only_tools = ["Read", "Glob", "Grep", "WebSearch", "WebFetch"]
    if tool_name in read_only_tools:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Auto-approved: read-only operation"
            }
        }

    # Auto-approve file writes within project directory
    if tool_name in ["Write", "Edit"]:
        file_path = tool_input.get("file_path", "")
        cwd = input_data.get("cwd", "")

        # If path is relative or within the project directory, approve
        if file_path.startswith("./") or file_path.startswith(cwd) or not file_path.startswith("/"):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Auto-approved: project file operation"
                }
            }

    # Auto-approve safe bash commands
    if tool_name == "Bash":
        command = tool_input.get("command", "")

        if is_command_safe(command):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Auto-approved: safe command"
                }
            }

    # Don't make a decision - let other hooks or defaults handle it
    return {}
