"""Tests for MCP server configurations (agent/mcp/servers.py)."""

import os
from unittest.mock import patch

from agent.mcp.servers import get_mcp_servers, get_mcp_config_json


class TestGetMcpServers:
    """Tests for dynamic MCP server configuration."""

    def test_returns_dict(self):
        """get_mcp_servers should always return a dict."""
        result = get_mcp_servers()
        assert isinstance(result, dict)

    @patch.dict(os.environ, {}, clear=True)
    def test_empty_when_no_tokens(self):
        """No servers configured when no tokens are set."""
        result = get_mcp_servers()
        assert result == {}

    @patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test123"})
    def test_github_server_when_token_set(self):
        """GitHub server configured when GITHUB_TOKEN is set."""
        result = get_mcp_servers()
        assert "github" in result
        assert result["github"]["env"]["GITHUB_TOKEN"] == "ghp_test123"

    @patch.dict(os.environ, {"SUPABASE_ACCESS_TOKEN": "sbp_test456"})
    def test_supabase_server_when_token_set(self):
        """Supabase server configured when SUPABASE_ACCESS_TOKEN is set."""
        result = get_mcp_servers()
        assert "supabase" in result
        assert result["supabase"]["env"]["SUPABASE_ACCESS_TOKEN"] == "sbp_test456"

    @patch.dict(os.environ, {"VERCEL_TOKEN": "vt_test789"})
    def test_vercel_server_when_token_set(self):
        """Vercel server configured when VERCEL_TOKEN is set."""
        result = get_mcp_servers()
        assert "vercel" in result
        assert result["vercel"]["env"]["VERCEL_TOKEN"] == "vt_test789"

    @patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test", "VERCEL_TOKEN": "vt_test"})
    def test_multiple_servers(self):
        """Multiple servers configured when multiple tokens set."""
        result = get_mcp_servers()
        assert "github" in result
        assert "vercel" in result
        assert "supabase" not in result


class TestGetMcpConfigJson:
    """Tests for static MCP config JSON generation."""

    def test_returns_dict_with_mcp_servers_key(self):
        """Config should have mcpServers top-level key."""
        result = get_mcp_config_json()
        assert "mcpServers" in result

    def test_has_all_three_servers(self):
        """Config should define github, supabase, and vercel servers."""
        servers = get_mcp_config_json()["mcpServers"]
        assert "github" in servers
        assert "supabase" in servers
        assert "vercel" in servers

    def test_uses_env_var_placeholders(self):
        """Config should use ${VAR} placeholders, not real values."""
        servers = get_mcp_config_json()["mcpServers"]
        assert servers["github"]["env"]["GITHUB_TOKEN"] == "${GITHUB_TOKEN}"
        assert servers["supabase"]["env"]["SUPABASE_ACCESS_TOKEN"] == "${SUPABASE_ACCESS_TOKEN}"
        assert servers["vercel"]["env"]["VERCEL_TOKEN"] == "${VERCEL_TOKEN}"

    def test_all_servers_use_npx(self):
        """All servers should use npx as the command."""
        servers = get_mcp_config_json()["mcpServers"]
        for name, config in servers.items():
            assert config["command"] == "npx", f"{name} should use npx"
