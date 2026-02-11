"""CLI runner for Claude Code - uses Claude Pro subscription instead of API credits."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def run_claude(
    prompt: str,
    system_prompt: str | None = None,
    allowed_tools: list[str] | None = None,
    agents_config: dict[str, Any] | None = None,
    cwd: str | None = None,
    max_turns: int = 50,
    timeout: int = 600,
    mcp_config_path: str | None = None,
) -> dict[str, Any]:
    """Run Claude Code CLI and return JSON response.

    Args:
        prompt: The prompt to send to Claude
        system_prompt: Custom system prompt (replaces default)
        allowed_tools: List of tools to pre-approve (e.g., ["Read", "Write", "Bash"])
        agents_config: Dict of subagent definitions for --agents flag
        cwd: Working directory for the command
        max_turns: Maximum conversation turns
        timeout: Timeout in seconds (default 10 minutes)
        mcp_config_path: Path to MCP configuration file

    Returns:
        Dict with response data or error information
    """
    cmd = ["claude", "-p", prompt, "--output-format", "json"]

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    if allowed_tools:
        # Format: --allowedTools "Read,Write,Bash"
        cmd.extend(["--allowedTools", ",".join(allowed_tools)])

    cmd.extend(["--max-turns", str(max_turns)])

    if mcp_config_path:
        cmd.extend(["--mcp-config", mcp_config_path])

    # Handle agents config - write to temp file if provided
    agents_file = None
    if agents_config:
        agents_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        )
        json.dump(agents_config, agents_file)
        agents_file.close()
        cmd.extend(["--agents", agents_file.name])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )

        # Clean up temp file
        if agents_file:
            Path(agents_file.name).unlink(missing_ok=True)

        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr or "Unknown error",
                "exit_code": result.returncode,
                "stdout": result.stdout,
            }

        # Parse JSON output
        try:
            output = json.loads(result.stdout)
            output["success"] = True
            return output
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse JSON output: {e}",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

    except subprocess.TimeoutExpired:
        if agents_file:
            Path(agents_file.name).unlink(missing_ok=True)
        return {
            "success": False,
            "error": f"Command timed out after {timeout} seconds",
            "exit_code": -1,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Claude CLI not found. Make sure 'claude' is installed and in PATH.",
            "exit_code": -1,
        }
    except Exception as e:
        if agents_file:
            Path(agents_file.name).unlink(missing_ok=True)
        return {
            "success": False,
            "error": str(e),
            "exit_code": -1,
        }


def check_claude_cli() -> tuple[bool, str]:
    """Check if Claude CLI is available and return version.

    Returns:
        Tuple of (is_available, version_or_error)
    """
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr or "Unknown error"
    except FileNotFoundError:
        return False, "Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
    except Exception as e:
        return False, str(e)
