"""Tests for v11.0 pipeline features: AI domain, CI/CD, observability.

Validates:
- AI app domain pattern exists and is mapped correctly
- Deploy templates include CI/CD workflows
- Deploy templates include observability setup
- Deployer prompt mentions post-deploy setup
- Stack selector detects AI app product types
"""

import pytest
from pathlib import Path

from agent.domains import get_domain_for_product_type, get_domain_patterns, list_domains
from agent.stacks.criteria import PRODUCT_TYPE_STACKS
from agent.stacks.selector import analyze_product_idea, select_stack
from agent.agents.definitions import get_agent_prompt, _load_template


# =====================================================================
# 1. AI App Domain
# =====================================================================


class TestAiAppDomain:
    """AI app domain exists and provides patterns."""

    def test_ai_app_in_domain_list(self):
        domains = list_domains()
        assert "ai_app" in domains

    def test_ai_app_patterns_exist(self):
        patterns = get_domain_patterns("ai_app")
        assert patterns is not None
        assert len(patterns) > 500

    def test_ai_app_patterns_contain_sdk(self):
        patterns = get_domain_patterns("ai_app")
        assert "streamText" in patterns
        assert "useChat" in patterns

    def test_ai_app_patterns_contain_gateway(self):
        patterns = get_domain_patterns("ai_app")
        assert "anthropic/claude" in patterns or "AI Gateway" in patterns

    def test_ai_app_patterns_contain_data_model(self):
        patterns = get_domain_patterns("ai_app")
        assert "conversations" in patterns
        assert "messages" in patterns

    def test_ai_app_domain_mapping(self):
        assert get_domain_for_product_type("ai_app") == "ai_app"
        assert get_domain_for_product_type("chatbot") == "ai_app"
        assert get_domain_for_product_type("ai_assistant") == "ai_app"
        assert get_domain_for_product_type("ai_tool") == "ai_app"


class TestAiAppSelection:
    """Stack selector detects AI app ideas."""

    def test_chatbot_keyword_detected(self):
        chars = analyze_product_idea("Build a chatbot for customer support")
        assert "chatbot" in chars["product_types"]

    def test_ai_powered_keyword_detected(self):
        chars = analyze_product_idea("Build an ai-powered writing assistant")
        assert "ai_app" in chars["product_types"] or "ai_assistant" in chars["product_types"]

    def test_ai_app_selects_nextjs(self):
        """AI apps should use Next.js stacks."""
        recommended = PRODUCT_TYPE_STACKS.get("ai_app", [])
        assert "nextjs-supabase" in recommended

    def test_chatbot_selects_nextjs(self):
        recommended = PRODUCT_TYPE_STACKS.get("chatbot", [])
        assert "nextjs-supabase" in recommended


# =====================================================================
# 2. CI/CD in Deploy Templates
# =====================================================================

TEMPLATE_DIR = Path(__file__).parent.parent / "agent" / "stacks" / "templates"


class TestCiCdTemplates:
    """Deploy templates include GitHub Actions workflows."""

    def test_nextjs_supabase_has_ci(self):
        content = (TEMPLATE_DIR / "nextjs-supabase" / "deploy.md").read_text()
        assert "GitHub Actions" in content
        assert ".github/workflows" in content
        assert "npm test" in content

    def test_nextjs_prisma_has_ci(self):
        content = (TEMPLATE_DIR / "nextjs-prisma" / "deploy.md").read_text()
        assert "GitHub Actions" in content
        assert "prisma generate" in content

    def test_sveltekit_has_ci(self):
        content = (TEMPLATE_DIR / "sveltekit" / "deploy.md").read_text()
        assert "GitHub Actions" in content
        assert "npm run build" in content

    def test_ci_uses_node_22(self):
        """CI workflows should use Node.js 22."""
        for stack in ["nextjs-supabase", "nextjs-prisma", "sveltekit"]:
            content = (TEMPLATE_DIR / stack / "deploy.md").read_text()
            assert "node-version: 22" in content, f"{stack} CI should use Node 22"

    def test_ci_uses_actions_v4(self):
        """CI workflows should use latest action versions."""
        for stack in ["nextjs-supabase", "nextjs-prisma", "sveltekit"]:
            content = (TEMPLATE_DIR / stack / "deploy.md").read_text()
            assert "actions/checkout@v4" in content, f"{stack} should use checkout@v4"


# =====================================================================
# 3. Observability in Deploy Templates
# =====================================================================


class TestObservabilityTemplates:
    """Deploy templates include Vercel Analytics and Speed Insights."""

    def test_nextjs_supabase_has_analytics(self):
        content = (TEMPLATE_DIR / "nextjs-supabase" / "deploy.md").read_text()
        assert "@vercel/analytics" in content
        assert "@vercel/speed-insights" in content

    def test_nextjs_prisma_has_analytics(self):
        content = (TEMPLATE_DIR / "nextjs-prisma" / "deploy.md").read_text()
        assert "@vercel/analytics" in content
        assert "@vercel/speed-insights" in content

    def test_analytics_import_pattern(self):
        """Templates show correct import patterns."""
        content = (TEMPLATE_DIR / "nextjs-supabase" / "deploy.md").read_text()
        assert "<Analytics />" in content
        assert "<SpeedInsights />" in content


# =====================================================================
# 4. Deployer Prompt Updates
# =====================================================================


class TestDeployerPromptUpdates:
    """Deployer prompt includes post-deploy setup instructions."""

    def test_deployer_mentions_observability(self):
        prompt = get_agent_prompt("deployer")
        assert "Observability" in prompt or "Analytics" in prompt

    def test_deployer_mentions_cicd(self):
        prompt = get_agent_prompt("deployer")
        assert "CI/CD" in prompt or "GitHub Actions" in prompt

    def test_deployer_mentions_post_deploy(self):
        prompt = get_agent_prompt("deployer")
        assert "Post-Deployment" in prompt or "Post-Deploy" in prompt
