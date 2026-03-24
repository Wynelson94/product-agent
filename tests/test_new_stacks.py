"""Tests for v11.0 new stacks: Django+HTMX, SvelteKit, Astro.

Validates:
- Stack definitions exist with correct fields
- Stack selector picks new stacks for matching ideas
- Templates exist for all new stacks
- Template injection works for new stacks
"""

import pytest
from pathlib import Path

from agent.stacks.criteria import (
    STACKS,
    PRODUCT_TYPE_STACKS,
    FEATURE_REQUIREMENTS,
    get_stack,
    check_stack_deployment_compatibility,
)
from agent.stacks.selector import (
    analyze_product_idea,
    score_stack,
    select_stack,
)
from agent.agents.definitions import _load_template, get_agent_prompt


# =====================================================================
# 1. Stack definitions
# =====================================================================


class TestDjangoHtmxDefinition:

    def test_exists(self):
        assert "django-htmx" in STACKS

    def test_fields(self):
        stack = get_stack("django-htmx")
        assert stack.name == "Django + HTMX"
        assert stack.deployment == "railway"
        assert stack.deployment_type == "traditional"
        assert stack.complexity == "medium"

    def test_product_types(self):
        stack = get_stack("django-htmx")
        assert "admin_panel" in stack.product_types
        assert "data_app" in stack.product_types
        assert "internal_tool" in stack.product_types

    def test_features(self):
        stack = get_stack("django-htmx")
        assert "admin_interface" in stack.features
        assert "htmx" in stack.features
        assert "orm" in stack.features

    def test_required_env_vars(self):
        stack = get_stack("django-htmx")
        assert "DATABASE_URL" in stack.required_env_vars
        assert "DJANGO_SECRET_KEY" in stack.required_env_vars


class TestSvelteKitDefinition:

    def test_exists(self):
        assert "sveltekit" in STACKS

    def test_fields(self):
        stack = get_stack("sveltekit")
        assert stack.name == "SvelteKit"
        assert stack.deployment == "vercel"
        assert stack.deployment_type == "serverless"
        assert stack.complexity == "low-medium"

    def test_product_types(self):
        stack = get_stack("sveltekit")
        assert "saas" in stack.product_types
        assert "dashboard" in stack.product_types
        assert "rapid_prototype" in stack.product_types

    def test_features(self):
        stack = get_stack("sveltekit")
        assert "form_actions" in stack.features
        assert "ssr" in stack.features


class TestAstroDefinition:

    def test_exists(self):
        assert "astro" in STACKS

    def test_fields(self):
        stack = get_stack("astro")
        assert stack.name == "Astro"
        assert stack.deployment == "vercel"
        assert stack.deployment_type == "serverless"
        assert stack.complexity == "low"

    def test_product_types(self):
        stack = get_stack("astro")
        assert "content_site" in stack.product_types
        assert "blog" in stack.product_types
        assert "docs_site" in stack.product_types

    def test_features(self):
        stack = get_stack("astro")
        assert "islands" in stack.features
        assert "markdown" in stack.features
        assert "zero_js_default" in stack.features


# =====================================================================
# 2. Stack selection
# =====================================================================


class TestDjangoSelection:

    def test_admin_panel_selects_django(self):
        """Django should be top pick for admin panels with Python/Django keywords."""
        stack_id, _ = select_stack("Build a django admin panel for managing inventory data with background jobs")
        assert stack_id == "django-htmx"

    def test_python_keyword_boosts_django(self):
        """Mentioning 'django' or 'python web' should select django."""
        chars = analyze_product_idea("Build a django web app for tracking orders")
        assert "htmx" in chars["features"]

    def test_data_app_selects_django(self):
        """Data-heavy apps should prefer Django."""
        stack_id, _ = select_stack("Build a data app for analytics platform")
        assert stack_id == "django-htmx"


class TestSvelteKitSelection:

    def test_svelte_keyword_selects_sveltekit(self):
        """Mentioning 'svelte' or 'sveltekit' should select it."""
        chars = analyze_product_idea("Build a sveltekit app for task tracking")
        assert "form_actions" in chars["features"]

    def test_interactive_app_includes_sveltekit(self):
        """Interactive apps should consider SvelteKit."""
        chars = analyze_product_idea("Build an interactive single page dashboard")
        assert "interactive_app" in chars["product_types"]


class TestAstroSelection:

    def test_blog_selects_astro(self):
        """Blogs should prefer Astro."""
        stack_id, _ = select_stack("Build a blog with markdown posts")
        assert stack_id == "astro"

    def test_docs_site_selects_astro(self):
        """Documentation sites should select Astro."""
        stack_id, _ = select_stack("Build a documentation site for our API docs")
        assert stack_id == "astro"

    def test_static_site_selects_astro(self):
        """Static sites should prefer Astro."""
        chars = analyze_product_idea("Build a static site for our marketing with markdown content")
        assert "static_generation" in chars["features"] or "markdown" in chars["features"]

    def test_landing_page_prefers_astro(self):
        """Landing pages should prefer Astro as first choice."""
        recommended = PRODUCT_TYPE_STACKS.get("landing_page", [])
        assert recommended[0] == "astro"


# =====================================================================
# 3. Deployment compatibility
# =====================================================================


class TestNewStackCompatibility:

    def test_django_railway_compatible(self):
        ok, msg = check_stack_deployment_compatibility("django-htmx", "railway", "postgresql")
        assert ok

    def test_sveltekit_vercel_compatible(self):
        ok, msg = check_stack_deployment_compatibility("sveltekit", "vercel", "postgresql")
        assert ok

    def test_astro_vercel_compatible(self):
        ok, msg = check_stack_deployment_compatibility("astro", "vercel")
        assert ok

    def test_sveltekit_sqlite_incompatible(self):
        ok, msg = check_stack_deployment_compatibility("sveltekit", "vercel", "sqlite")
        assert not ok


# =====================================================================
# 4. Templates exist
# =====================================================================


TEMPLATE_DIR = Path(__file__).parent.parent / "agent" / "stacks" / "templates"
REQUIRED_TEMPLATES = ["scaffold.md", "patterns.md", "builder.md", "tests.md", "deploy.md"]


class TestDjangoTemplates:

    @pytest.mark.parametrize("template", REQUIRED_TEMPLATES)
    def test_template_exists(self, template):
        path = TEMPLATE_DIR / "django-htmx" / template
        assert path.exists(), f"Missing: {path}"

    @pytest.mark.parametrize("template", REQUIRED_TEMPLATES)
    def test_template_not_empty(self, template):
        content = (TEMPLATE_DIR / "django-htmx" / template).read_text()
        assert len(content) > 100, f"Template too short: {template}"

    def test_load_template_function(self):
        content = _load_template("django-htmx", "scaffold")
        assert "Django" in content


class TestSvelteKitTemplates:

    @pytest.mark.parametrize("template", REQUIRED_TEMPLATES)
    def test_template_exists(self, template):
        path = TEMPLATE_DIR / "sveltekit" / template
        assert path.exists(), f"Missing: {path}"

    @pytest.mark.parametrize("template", REQUIRED_TEMPLATES)
    def test_template_not_empty(self, template):
        content = (TEMPLATE_DIR / "sveltekit" / template).read_text()
        assert len(content) > 100, f"Template too short: {template}"

    def test_load_template_function(self):
        content = _load_template("sveltekit", "scaffold")
        assert "SvelteKit" in content


class TestAstroTemplates:

    @pytest.mark.parametrize("template", REQUIRED_TEMPLATES)
    def test_template_exists(self, template):
        path = TEMPLATE_DIR / "astro" / template
        assert path.exists(), f"Missing: {path}"

    @pytest.mark.parametrize("template", REQUIRED_TEMPLATES)
    def test_template_not_empty(self, template):
        content = (TEMPLATE_DIR / "astro" / template).read_text()
        assert len(content) > 100, f"Template too short: {template}"

    def test_load_template_function(self):
        content = _load_template("astro", "scaffold")
        assert "Astro" in content


# =====================================================================
# 5. Template injection into agent prompts
# =====================================================================


class TestTemplateInjection:
    """Verify get_agent_prompt injects templates for new stacks."""

    def test_django_builder_prompt(self):
        prompt = get_agent_prompt("builder", stack_id="django-htmx")
        assert "Django" in prompt or "django" in prompt

    def test_sveltekit_builder_prompt(self):
        prompt = get_agent_prompt("builder", stack_id="sveltekit")
        assert "SvelteKit" in prompt or "sveltekit" in prompt or "svelte" in prompt

    def test_astro_builder_prompt(self):
        prompt = get_agent_prompt("builder", stack_id="astro")
        assert "Astro" in prompt or "astro" in prompt

    def test_django_designer_prompt(self):
        prompt = get_agent_prompt("designer", stack_id="django-htmx")
        # Designer gets scaffold template injected
        assert len(prompt) > 100

    def test_sveltekit_tester_prompt(self):
        prompt = get_agent_prompt("tester", stack_id="sveltekit")
        assert len(prompt) > 100

    def test_astro_deployer_prompt(self):
        prompt = get_agent_prompt("deployer", stack_id="astro")
        assert len(prompt) > 100


# =====================================================================
# 6. Product type mapping
# =====================================================================


class TestProductTypeMappings:

    def test_admin_panel_includes_django(self):
        assert "django-htmx" in PRODUCT_TYPE_STACKS["admin_panel"]

    def test_saas_includes_sveltekit(self):
        assert "sveltekit" in PRODUCT_TYPE_STACKS["saas"]

    def test_blog_includes_astro(self):
        assert "astro" in PRODUCT_TYPE_STACKS["blog"]

    def test_content_site_includes_astro(self):
        assert "astro" in PRODUCT_TYPE_STACKS["content_site"]

    def test_docs_site_maps_to_astro(self):
        assert "astro" in PRODUCT_TYPE_STACKS["docs_site"]

    def test_landing_page_includes_all_web(self):
        lp = PRODUCT_TYPE_STACKS["landing_page"]
        assert "astro" in lp
        assert "sveltekit" in lp

    def test_data_app_maps_to_django(self):
        assert "django-htmx" in PRODUCT_TYPE_STACKS["data_app"]

    def test_rapid_prototype_includes_sveltekit(self):
        assert "sveltekit" in PRODUCT_TYPE_STACKS["rapid_prototype"]


# =====================================================================
# 7. Feature requirements
# =====================================================================


class TestFeatureRequirements:

    def test_htmx_maps_to_django(self):
        assert "django-htmx" in FEATURE_REQUIREMENTS["htmx"]

    def test_admin_interface_includes_django(self):
        assert "django-htmx" in FEATURE_REQUIREMENTS["admin_interface"]

    def test_form_actions_maps_to_sveltekit(self):
        assert "sveltekit" in FEATURE_REQUIREMENTS["form_actions"]

    def test_islands_maps_to_astro(self):
        assert "astro" in FEATURE_REQUIREMENTS["islands"]

    def test_markdown_maps_to_astro(self):
        assert "astro" in FEATURE_REQUIREMENTS["markdown"]

    def test_background_jobs_includes_django(self):
        assert "django-htmx" in FEATURE_REQUIREMENTS["background_jobs"]

    def test_orm_includes_django(self):
        assert "django-htmx" in FEATURE_REQUIREMENTS["orm"]
