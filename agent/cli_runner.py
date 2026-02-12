"""CLI runner for Claude Code — v8.0.

Uses claude-code-sdk for phase-by-phase orchestration. Keeps the legacy
subprocess-based run_claude() for backwards compatibility.
"""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# v8.0: SDK-based phase runner
# ---------------------------------------------------------------------------

@dataclass
class PhaseCallResult:
    """Result from a single SDK phase call."""
    success: bool
    result_text: str = ""
    error: str = ""
    duration_s: float = 0.0
    num_turns: int = 0
    cost_usd: float | None = None
    session_id: str = ""


async def run_phase_call(
    prompt: str,
    system_prompt: str,
    allowed_tools: list[str],
    cwd: str | Path,
    max_turns: int = 50,
    model: str | None = None,
) -> PhaseCallResult:
    """Run a single phase using claude-code-sdk.

    Each phase gets its own focused Claude call with specific tools
    and turn limits. This replaces the old monolithic subprocess call.

    Args:
        prompt: The task-specific prompt for this phase
        system_prompt: The agent's system prompt (from definitions.py)
        allowed_tools: Tools to pre-approve for this phase
        cwd: Working directory (project directory)
        max_turns: Maximum turns for this phase
        model: Optional model override

    Returns:
        PhaseCallResult with success status, output text, and metrics
    """
    from claude_code_sdk import query, ClaudeCodeOptions, ResultMessage, AssistantMessage, TextBlock

    start_time = time.time()
    result_text_parts: list[str] = []

    options = ClaudeCodeOptions(
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        max_turns=max_turns,
        cwd=str(cwd),
        permission_mode="bypassPermissions",
    )
    if model:
        options.model = model

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                duration = time.time() - start_time
                return PhaseCallResult(
                    success=not message.is_error,
                    result_text=message.result or "\n".join(result_text_parts),
                    error="" if not message.is_error else (message.result or "Phase failed"),
                    duration_s=duration,
                    num_turns=message.num_turns,
                    cost_usd=message.total_cost_usd,
                    session_id=message.session_id,
                )
            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result_text_parts.append(block.text)

        # Stream ended without ResultMessage (shouldn't happen but handle it)
        duration = time.time() - start_time
        return PhaseCallResult(
            success=True,
            result_text="\n".join(result_text_parts),
            duration_s=duration,
        )

    except Exception as e:
        duration = time.time() - start_time
        return PhaseCallResult(
            success=False,
            error=str(e),
            duration_s=duration,
        )


# ---------------------------------------------------------------------------
# Legacy subprocess runner (kept for --legacy mode and backwards compat)
# ---------------------------------------------------------------------------

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
    """Run Claude Code CLI via subprocess and return JSON response.

    This is the v7.0 legacy runner. v8.0 uses run_phase_call() instead.
    Kept for --legacy mode and backwards compatibility.

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
    import tempfile

    cmd = ["claude", "-p", prompt, "--output-format", "json"]

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    if allowed_tools:
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
