"""Progress reporting hooks - show what the agent is doing."""

import sys
from datetime import datetime
from typing import Any


def timestamp() -> str:
    """Get formatted timestamp."""
    return datetime.now().strftime("%H:%M:%S")


async def progress_hook(input_data: dict, tool_use_id: str | None, context: Any) -> dict:
    """Report progress to stderr without requiring approval."""
    event = input_data.get("hook_event_name", "")

    if event == "PreToolUse":
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        if tool_name == "Write":
            file_path = tool_input.get("file_path", "unknown")
            print(f"[{timestamp()}] Creating: {file_path}", file=sys.stderr)

        elif tool_name == "Edit":
            file_path = tool_input.get("file_path", "unknown")
            print(f"[{timestamp()}] Editing: {file_path}", file=sys.stderr)

        elif tool_name == "Bash":
            command = tool_input.get("command", "")
            # Truncate long commands
            display_cmd = command[:60] + "..." if len(command) > 60 else command
            # Clean up newlines for display
            display_cmd = display_cmd.replace("\n", " ")
            print(f"[{timestamp()}] Running: {display_cmd}", file=sys.stderr)

        elif tool_name == "Task":
            subagent = tool_input.get("subagent_type", "unknown")
            desc = tool_input.get("description", "")
            print(f"[{timestamp()}] Delegating to {subagent}: {desc}", file=sys.stderr)

        elif tool_name == "Read":
            file_path = tool_input.get("file_path", "unknown")
            print(f"[{timestamp()}] Reading: {file_path}", file=sys.stderr)

        elif tool_name == "WebFetch":
            url = tool_input.get("url", "unknown")
            print(f"[{timestamp()}] Fetching: {url}", file=sys.stderr)

    elif event == "PostToolUse":
        tool_name = input_data.get("tool_name", "")

        if tool_name == "Task":
            print(f"[{timestamp()}] Subagent completed", file=sys.stderr)

        elif tool_name == "Bash":
            # Could check for errors here
            pass

    elif event == "Stop":
        reason = input_data.get("stop_reason", "unknown")
        print(f"[{timestamp()}] Agent stopped: {reason}", file=sys.stderr)

    # Never block - just observe
    return {}


