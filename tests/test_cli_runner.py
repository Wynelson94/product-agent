"""Tests for agent/cli_runner.py - Claude CLI subprocess runner."""

import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from agent.cli_runner import check_claude_cli, run_claude


class TestRunClaudeSuccess:
    """Tests for successful run_claude invocations."""

    @patch("agent.cli_runner.subprocess.run")
    def test_successful_run_returns_parsed_json(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"result": "App deployed"}),
            stderr="",
        )
        result = run_claude("Build a todo app")
        assert result["success"] is True
        assert result["result"] == "App deployed"

    @patch("agent.cli_runner.subprocess.run")
    def test_command_includes_prompt(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        run_claude("my prompt")
        cmd = mock_run.call_args[0][0]
        assert "-p" in cmd
        assert "my prompt" in cmd

    @patch("agent.cli_runner.subprocess.run")
    def test_command_includes_output_format_json(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        run_claude("test")
        cmd = mock_run.call_args[0][0]
        assert "--output-format" in cmd
        assert "json" in cmd

    @patch("agent.cli_runner.subprocess.run")
    def test_system_prompt_added_to_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        run_claude("test", system_prompt="Be helpful")
        cmd = mock_run.call_args[0][0]
        assert "--system-prompt" in cmd
        assert "Be helpful" in cmd

    @patch("agent.cli_runner.subprocess.run")
    def test_allowed_tools_joined(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        run_claude("test", allowed_tools=["Read", "Write", "Bash"])
        cmd = mock_run.call_args[0][0]
        assert "--allowedTools" in cmd
        assert "Read,Write,Bash" in cmd

    @patch("agent.cli_runner.subprocess.run")
    def test_max_turns_included(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        run_claude("test", max_turns=100)
        cmd = mock_run.call_args[0][0]
        assert "--max-turns" in cmd
        assert "100" in cmd

    @patch("agent.cli_runner.subprocess.run")
    def test_mcp_config_path_included(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        run_claude("test", mcp_config_path="/path/to/config.json")
        cmd = mock_run.call_args[0][0]
        assert "--mcp-config" in cmd
        assert "/path/to/config.json" in cmd

    @patch("agent.cli_runner.subprocess.run")
    def test_cwd_passed_to_subprocess(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        run_claude("test", cwd="/my/project")
        assert mock_run.call_args[1]["cwd"] == "/my/project"


class TestRunClaudeErrors:
    """Tests for error handling in run_claude."""

    @patch("agent.cli_runner.subprocess.run")
    def test_nonzero_exit_code(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error occurred"
        )
        result = run_claude("test")
        assert result["success"] is False
        assert "Error occurred" in result["error"]

    @patch("agent.cli_runner.subprocess.run")
    def test_invalid_json_output(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="not json", stderr=""
        )
        result = run_claude("test")
        assert result["success"] is False
        assert "JSON" in result["error"]

    @patch("agent.cli_runner.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="claude", timeout=600
        )
        result = run_claude("test")
        assert result["success"] is False
        assert "timed out" in result["error"]

    @patch("agent.cli_runner.subprocess.run")
    def test_cli_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = run_claude("test")
        assert result["success"] is False
        assert "not found" in result["error"]

    @patch("agent.cli_runner.subprocess.run")
    def test_generic_exception(self, mock_run):
        mock_run.side_effect = OSError("Permission denied")
        result = run_claude("test")
        assert result["success"] is False
        assert "Permission denied" in result["error"]


class TestRunClaudeAgentsConfig:
    """Tests for agents_config temp file handling in run_claude."""

    @patch("agent.cli_runner.subprocess.run")
    def test_agents_config_written_to_temp_file(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        agents = {
            "builder": {
                "description": "test",
                "prompt": "test",
                "tools": ["Read"],
            }
        }
        run_claude("test", agents_config=agents)
        cmd = mock_run.call_args[0][0]
        assert "--agents" in cmd

    @patch("agent.cli_runner.subprocess.run")
    def test_agents_temp_file_cleaned_up_on_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        agents = {
            "builder": {
                "description": "test",
                "prompt": "test",
                "tools": [],
            }
        }
        run_claude("test", agents_config=agents)
        # The temp file path is extracted from the --agents flag value
        cmd = mock_run.call_args[0][0]
        agents_idx = cmd.index("--agents")
        temp_path = cmd[agents_idx + 1]
        assert not os.path.exists(temp_path)


class TestCheckClaudeCli:
    """Tests for check_claude_cli version checking."""

    @patch("agent.cli_runner.subprocess.run")
    def test_cli_available(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="1.0.0", stderr=""
        )
        available, info = check_claude_cli()
        assert available is True
        assert "1.0.0" in info

    @patch("agent.cli_runner.subprocess.run")
    def test_cli_not_available_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="not found"
        )
        available, info = check_claude_cli()
        assert available is False

    @patch("agent.cli_runner.subprocess.run")
    def test_cli_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        available, info = check_claude_cli()
        assert available is False
        assert "not found" in info.lower()

    @patch("agent.cli_runner.subprocess.run")
    def test_cli_exception(self, mock_run):
        mock_run.side_effect = OSError("fail")
        available, info = check_claude_cli()
        assert available is False
