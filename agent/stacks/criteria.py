"""Stack definitions and selection criteria for Product Agent v7.0."""

from dataclasses import dataclass, field
from typing import Literal


StackId = Literal[
    "nextjs-supabase", "nextjs-prisma", "rails", "expo-supabase", "swift-swiftui",
    "django-htmx", "sveltekit", "astro",  # v11.0: New stacks
]


@dataclass
class StackDefinition:
    """Definition of a technology stack."""
    id: StackId
    name: str
    description: str
    product_types: list[str]
    features: list[str]
    complexity: str  # low, medium, high
    deployment: str  # vercel, railway, fly.io, etc.
    is_default: bool = False
    # v5.0: Deployment-aware fields
    deployment_type: str = "serverless"  # "serverless" | "traditional"
    incompatible_databases: list[str] = field(default_factory=list)
    required_env_vars: list[str] = field(default_factory=list)


# v5.0: Deployment target to type mapping
DEPLOYMENT_TYPES: dict[str, str] = {
    "vercel": "serverless",
    "netlify": "serverless",
    "cloudflare": "serverless",
    "railway": "traditional",
    "fly.io": "traditional",
    "render": "traditional",
    "heroku": "traditional",
    "expo": "mobile",
    "testflight": "mobile",
    "app_store": "mobile",
}


# v5.0: Database compatibility with deployment types
DATABASE_DEPLOYMENT_COMPATIBILITY: dict[str, list[str]] = {
    "sqlite": ["traditional"],  # Only works with persistent filesystem
    "postgresql": ["serverless", "traditional", "mobile"],
    "mysql": ["serverless", "traditional"],
    "mongodb": ["serverless", "traditional"],
    "supabase": ["serverless", "traditional", "mobile"],
}


STACKS: dict[StackId, StackDefinition] = {
    "nextjs-supabase": StackDefinition(
        id="nextjs-supabase",
        name="Next.js + Supabase",
        description="Full-stack React with serverless Postgres. Best for most SaaS apps.",
        product_types=["saas", "internal_tool", "dashboard", "landing_page"],
        features=["auth", "realtime", "file_storage", "edge_functions", "rls"],
        complexity="low-medium",
        deployment="vercel",
        is_default=True,
        # v5.0 fields
        deployment_type="serverless",
        incompatible_databases=["sqlite", "file-based"],
        required_env_vars=["NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY"],
    ),
    "nextjs-prisma": StackDefinition(
        id="nextjs-prisma",
        name="Next.js + Prisma + PostgreSQL",
        description="Full-stack React with type-safe ORM. Best for complex data models.",
        product_types=["marketplace", "multi_tenant", "complex_crud", "enterprise"],
        features=["complex_relations", "transactions", "migrations", "seeding"],
        complexity="medium-high",
        deployment="vercel",
        # v5.0 fields
        deployment_type="serverless",
        incompatible_databases=["sqlite", "file-based"],
        required_env_vars=["DATABASE_URL"],
    ),
    "rails": StackDefinition(
        id="rails",
        name="Ruby on Rails",
        description="Convention over configuration. Best for rapid prototyping.",
        product_types=["marketplace", "admin_heavy", "rapid_prototype", "content_site"],
        features=["admin_interface", "background_jobs", "mailers", "active_storage"],
        complexity="medium",
        deployment="railway",
        # v5.0 fields
        deployment_type="traditional",
        incompatible_databases=[],  # Traditional deployment can use any database
        required_env_vars=["DATABASE_URL", "RAILS_MASTER_KEY"],
    ),
    "expo-supabase": StackDefinition(
        id="expo-supabase",
        name="Expo (React Native) + Supabase",
        description="Cross-platform mobile apps. Best for mobile-first products.",
        product_types=["mobile_app", "mobile_first", "consumer_app"],
        features=["push_notifications", "offline_first", "native_features", "app_store"],
        complexity="medium",
        deployment="expo",
        # v5.0 fields
        deployment_type="mobile",
        incompatible_databases=["sqlite"],  # Mobile apps should use Supabase
        required_env_vars=["EXPO_PUBLIC_SUPABASE_URL", "EXPO_PUBLIC_SUPABASE_ANON_KEY"],
    ),
    # v7.0: Native iOS with Swift Package plugin architecture
    "swift-swiftui": StackDefinition(
        id="swift-swiftui",
        name="Swift + SwiftUI",
        description="Native iOS with SwiftUI. Best for iOS apps, widgets, and utilities.",
        product_types=["ios_app", "native_app", "widget", "app_clip", "utility_app"],
        features=["local_storage", "swift_packages", "swiftui", "xctest", "swiftdata"],
        complexity="medium-high",
        deployment="testflight",
        # v7.0 fields
        deployment_type="mobile",
        incompatible_databases=[],  # Local storage is native to iOS
        required_env_vars=[],  # No env vars required for Swift builds
    ),
    # v11.0: Django + HTMX — Python web with server-rendered interactivity
    "django-htmx": StackDefinition(
        id="django-htmx",
        name="Django + HTMX",
        description="Python web framework with server-rendered interactivity. Best for data-heavy apps, admin panels, and Python-native teams.",
        product_types=["admin_panel", "data_app", "internal_tool", "api_backend", "rapid_prototype"],
        features=["admin_interface", "background_jobs", "orm", "auth", "rest_api", "htmx"],
        complexity="medium",
        deployment="railway",
        deployment_type="traditional",
        incompatible_databases=[],
        required_env_vars=["DATABASE_URL", "DJANGO_SECRET_KEY"],
    ),
    # v11.0: SvelteKit — lightweight modern JS alternative
    "sveltekit": StackDefinition(
        id="sveltekit",
        name="SvelteKit",
        description="Lightweight modern JS framework with excellent DX. Best for fast, interactive web apps with less boilerplate than React.",
        product_types=["saas", "dashboard", "landing_page", "interactive_app", "rapid_prototype"],
        features=["ssr", "auth", "form_actions", "api_routes", "progressive_enhancement"],
        complexity="low-medium",
        deployment="vercel",
        deployment_type="serverless",
        incompatible_databases=["sqlite", "file-based"],
        required_env_vars=[],
    ),
    # v11.0: Astro — content-first with islands architecture
    "astro": StackDefinition(
        id="astro",
        name="Astro",
        description="Content-first framework with islands architecture. Best for blogs, docs, marketing sites, and content-heavy pages with minimal JS.",
        product_types=["content_site", "blog", "docs_site", "landing_page", "marketing_site", "portfolio"],
        features=["static_generation", "islands", "markdown", "cms_integration", "zero_js_default"],
        complexity="low",
        deployment="vercel",
        deployment_type="serverless",
        incompatible_databases=["sqlite", "file-based"],
        required_env_vars=[],
    ),
}


# Product type to stack mapping (primary recommendations)
PRODUCT_TYPE_STACKS: dict[str, list[StackId]] = {
    # SaaS and tools
    "saas": ["nextjs-supabase", "nextjs-prisma", "sveltekit"],
    "internal_tool": ["nextjs-supabase", "django-htmx", "rails"],
    "dashboard": ["nextjs-supabase", "sveltekit"],
    "admin_panel": ["django-htmx", "rails", "nextjs-supabase"],

    # Marketplaces and platforms
    "marketplace": ["nextjs-prisma", "rails"],
    "two_sided_platform": ["nextjs-prisma", "rails"],
    "multi_tenant": ["nextjs-prisma"],

    # Mobile
    "mobile_app": ["expo-supabase"],
    "mobile_first": ["expo-supabase"],
    "consumer_app": ["expo-supabase", "nextjs-supabase"],

    # Content and simple
    "landing_page": ["astro", "nextjs-supabase", "sveltekit"],
    "blog": ["astro", "nextjs-supabase", "rails"],
    "rapid_prototype": ["sveltekit", "rails", "nextjs-supabase"],

    # Content sites (v6.0 + v11.0)
    "content_site": ["astro", "nextjs-supabase"],
    "nonprofit": ["astro", "nextjs-supabase"],
    "portfolio": ["astro", "nextjs-supabase"],
    "marketing_site": ["astro", "nextjs-supabase"],
    "event_site": ["nextjs-supabase", "astro"],
    "docs_site": ["astro"],

    # v11.0: Data-heavy and Python
    "data_app": ["django-htmx"],
    "api_backend": ["django-htmx", "rails"],
    "interactive_app": ["sveltekit", "nextjs-supabase"],

    # v11.0: AI-powered apps
    "ai_app": ["nextjs-supabase", "nextjs-prisma", "sveltekit"],
    "chatbot": ["nextjs-supabase", "nextjs-prisma"],
    "ai_assistant": ["nextjs-supabase", "nextjs-prisma"],
    "ai_tool": ["nextjs-supabase", "sveltekit"],

    # Native iOS (v7.0)
    "ios_app": ["swift-swiftui"],
    "native_app": ["swift-swiftui"],
    "widget": ["swift-swiftui"],
    "app_clip": ["swift-swiftui"],
    "utility_app": ["swift-swiftui"],

}


# Feature requirements that influence stack choice
FEATURE_REQUIREMENTS: dict[str, list[StackId]] = {
    # Database features
    "complex_relations": ["nextjs-prisma", "rails", "django-htmx"],
    "transactions": ["nextjs-prisma", "rails", "django-htmx"],
    "migrations": ["nextjs-prisma", "rails", "django-htmx"],
    "orm": ["django-htmx", "nextjs-prisma", "rails"],

    # Auth and realtime
    "realtime": ["nextjs-supabase", "expo-supabase", "sveltekit"],
    "social_auth": ["nextjs-supabase", "expo-supabase", "rails", "django-htmx"],
    "rls": ["nextjs-supabase", "expo-supabase"],
    "auth": ["django-htmx", "rails", "nextjs-supabase", "sveltekit"],

    # Mobile
    "push_notifications": ["expo-supabase"],
    "offline_first": ["expo-supabase"],
    "native_features": ["expo-supabase"],

    # Backend heavy
    "background_jobs": ["django-htmx", "rails", "nextjs-prisma"],
    "mailers": ["django-htmx", "rails", "nextjs-prisma"],
    "admin_interface": ["django-htmx", "rails"],
    "rest_api": ["django-htmx", "rails", "nextjs-prisma"],

    # Storage
    "file_storage": ["nextjs-supabase", "expo-supabase", "rails", "django-htmx"],

    # v11.0: Framework-specific features
    "htmx": ["django-htmx"],
    "ssr": ["sveltekit", "nextjs-supabase", "nextjs-prisma"],
    "form_actions": ["sveltekit"],
    "progressive_enhancement": ["sveltekit", "astro"],
    "static_generation": ["astro", "nextjs-supabase"],
    "islands": ["astro"],
    "markdown": ["astro"],
    "cms_integration": ["astro", "nextjs-supabase"],
    "zero_js_default": ["astro"],
    "api_routes": ["sveltekit", "nextjs-supabase", "nextjs-prisma"],

    # Native iOS (v7.0)
    "local_storage": ["swift-swiftui"],
    "compression": ["swift-swiftui"],
    "swift_packages": ["swift-swiftui"],
    "swiftdata": ["swift-swiftui"],
}


def get_default_stack() -> StackDefinition:
    """Return the default stack."""
    for stack in STACKS.values():
        if stack.is_default:
            return stack
    return STACKS["nextjs-supabase"]


def get_stack(stack_id: StackId) -> StackDefinition:
    """Get a stack by ID."""
    return STACKS[stack_id]


def list_stacks() -> list[StackDefinition]:
    """List all available stacks."""
    return list(STACKS.values())


def check_stack_deployment_compatibility(
    stack_id: StackId,
    deployment_target: str | None = None,
    database_type: str | None = None,
) -> tuple[bool, str | None]:
    """Check if a stack is compatible with the deployment target and database.

    Args:
        stack_id: The selected stack
        deployment_target: Where the app will deploy (e.g., "vercel")
        database_type: The database being used (e.g., "postgresql", "sqlite")

    Returns:
        Tuple of (is_compatible, error_message if not compatible)
    """
    stack = STACKS.get(stack_id)
    if not stack:
        return False, f"Unknown stack: {stack_id}"

    # Use stack's deployment if target not specified
    if not deployment_target:
        deployment_target = stack.deployment

    target_type = DEPLOYMENT_TYPES.get(deployment_target.lower(), "unknown")

    # Two-stage compatibility check:
    # Stage 1: Check if the database is explicitly incompatible with THIS stack
    #          (e.g., sqlite is incompatible with nextjs-supabase's serverless deployment)
    # Stage 2: Check if the database works with the deployment TYPE in general
    #          (e.g., sqlite doesn't work with any "serverless" deployment type)
    if database_type:
        db_lower = database_type.lower()
        # Stage 1: Stack-specific incompatibility
        if db_lower in stack.incompatible_databases:
            return False, (
                f"Database '{database_type}' is incompatible with {stack.deployment} deployment. "
                f"{stack.deployment.title()} uses {stack.deployment_type} infrastructure which "
                f"cannot persist {database_type} data between requests. "
                f"Use PostgreSQL with a managed service like Supabase, Neon, or Vercel Postgres instead."
            )

        # Stage 2: Deployment type compatibility (general, not stack-specific)
        compatible_types = DATABASE_DEPLOYMENT_COMPATIBILITY.get(db_lower, [])
        if target_type not in compatible_types and compatible_types:
            return False, (
                f"Database '{database_type}' is not compatible with {target_type} deployments. "
                f"Supported deployment types for {database_type}: {', '.join(compatible_types)}."
            )

    return True, None


def get_incompatible_database_error(database_type: str, deployment_target: str) -> str:
    """Generate a detailed error message for incompatible database/deployment combo.

    Args:
        database_type: The incompatible database (e.g., "sqlite")
        deployment_target: The deployment target (e.g., "vercel")

    Returns:
        Detailed error message with suggestions
    """
    return f"""## Database Incompatibility Detected

**{database_type.upper()} cannot be used with {deployment_target.title()}** (serverless deployment).

### Why This Fails
{database_type.title()} stores data in a local file. Serverless platforms like {deployment_target.title()}:
- Run each request in an isolated container
- Do not persist filesystem between requests
- Reset state after each invocation

### Solutions

1. **Use Supabase** (Recommended)
   - Free tier available at supabase.com
   - Managed PostgreSQL with auth, storage, and realtime
   - Update: `provider = "postgresql"`

2. **Use Neon** (Serverless PostgreSQL)
   - Free tier at neon.tech
   - Scales to zero when idle
   - Update: `provider = "postgresql"`

3. **Use Vercel Postgres**
   - Integrated with Vercel dashboard
   - Create at vercel.com/storage
   - Update: `provider = "postgresql"`

4. **Switch to Railway** (if you need SQLite)
   - Traditional deployment with persistent storage
   - `railway up` instead of `vercel --prod`

### Required Changes
```prisma
datasource db {{
  provider = "postgresql"  // Changed from "{database_type}"
  url      = env("DATABASE_URL")
}}
```
"""
