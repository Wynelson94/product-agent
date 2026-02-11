"""MCP server configurations for external service integration."""

import os
from typing import Any


def get_mcp_servers() -> dict[str, Any]:
    """Get MCP server configurations.

    Returns configurations for:
    - GitHub: Repository management
    - Supabase: Database operations
    - Vercel: Deployments

    Note: These require the respective environment variables to be set.
    If tokens aren't available, the servers won't be configured.
    """
    servers = {}

    # GitHub MCP Server - for repo creation and management
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        servers["github"] = {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_TOKEN": github_token
            }
        }

    # Supabase MCP Server - for database operations
    # Note: Supabase MCP uses OAuth, so we just need to enable it
    supabase_token = os.environ.get("SUPABASE_ACCESS_TOKEN")
    if supabase_token:
        servers["supabase"] = {
            "command": "npx",
            "args": ["-y", "supabase-mcp-server"],
            "env": {
                "SUPABASE_ACCESS_TOKEN": supabase_token
            }
        }

    # Vercel MCP Server - for deployments
    vercel_token = os.environ.get("VERCEL_TOKEN")
    if vercel_token:
        servers["vercel"] = {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/vercel-mcp-server"],
            "env": {
                "VERCEL_TOKEN": vercel_token
            }
        }

    return servers


def get_mcp_config_json() -> dict:
    """Get MCP configuration in JSON format for .mcp.json file."""
    return {
        "mcpServers": {
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {
                    "GITHUB_TOKEN": "${GITHUB_TOKEN}"
                }
            },
            "supabase": {
                "command": "npx",
                "args": ["-y", "supabase-mcp-server"],
                "env": {
                    "SUPABASE_ACCESS_TOKEN": "${SUPABASE_ACCESS_TOKEN}"
                }
            },
            "vercel": {
                "command": "npx",
                "args": ["-y", "@anthropic-ai/vercel-mcp-server"],
                "env": {
                    "VERCEL_TOKEN": "${VERCEL_TOKEN}"
                }
            }
        }
    }
