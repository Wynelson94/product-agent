"""Domain-specific patterns for Product Agent v6.0.

Provides specialized templates and patterns for different product types:
- marketplace: Two-sided platforms, buyer/seller interactions
- saas: Multi-tenant SaaS with organizations and subscriptions
- internal_tool: Admin dashboards, back-office tools
- content_site: Nonprofits, portfolios, marketing sites, blogs (v6.0)
"""

from pathlib import Path


DOMAIN_DIR = Path(__file__).parent


def get_domain_patterns(domain: str) -> str | None:
    """Load patterns for a specific domain.

    Args:
        domain: The domain type (marketplace, saas, internal_tool)

    Returns:
        The patterns markdown content or None if not found
    """
    patterns_path = DOMAIN_DIR / domain / "patterns.md"
    if patterns_path.exists():
        return patterns_path.read_text()
    return None


def list_domains() -> list[str]:
    """List available domain types."""
    return [
        d.name for d in DOMAIN_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ]


def get_domain_for_product_type(product_type: str) -> str | None:
    """Map a product type to its domain.

    Args:
        product_type: The product type from stack analysis

    Returns:
        The matching domain or None
    """
    mappings = {
        # Marketplace domain
        "marketplace": "marketplace",
        "two_sided_platform": "marketplace",

        # SaaS domain
        "saas": "saas",
        "multi_tenant": "saas",

        # Internal tool domain
        "internal_tool": "internal_tool",
        "admin_panel": "internal_tool",
        "dashboard": "internal_tool",

        # Content site domain (v6.0)
        "content_site": "content_site",
        "nonprofit": "content_site",
        "marketing_site": "content_site",
        "portfolio": "content_site",
        "blog": "content_site",
        "landing_page": "content_site",
        "event_site": "content_site",
    }
    return mappings.get(product_type)
