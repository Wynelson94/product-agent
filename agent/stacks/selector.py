"""Stack selection logic for Product Agent v7.0."""

from .criteria import (
    StackId,
    StackDefinition,
    STACKS,
    PRODUCT_TYPE_STACKS,
    FEATURE_REQUIREMENTS,
    get_default_stack,
)


def analyze_product_idea(idea: str) -> dict:
    """Extract product characteristics from the idea text.

    This is a simple keyword-based analysis. The Analyzer agent
    does more sophisticated analysis using the LLM.
    """
    idea_lower = idea.lower()

    characteristics = {
        "product_types": [],
        "features": [],
        "complexity_hints": [],
    }

    # Product type detection
    type_keywords = {
        "marketplace": ["marketplace", "buy and sell", "buyers and sellers", "two-sided"],
        "mobile_app": ["mobile app", "ios", "android", "native app", "app store"],
        "saas": ["saas", "subscription", "b2b", "software as a service"],
        "dashboard": ["dashboard", "analytics", "metrics", "reporting"],
        "internal_tool": ["internal", "admin", "back office", "employee"],
        "multi_tenant": ["multi-tenant", "organizations", "teams", "workspaces"],
        # v6.0: Content site types
        "content_site": ["website", "site", "rebuild", "redesign"],
        "nonprofit": ["nonprofit", "non-profit", "charity", "donation", "volunteer", "foundation"],
        "portfolio": ["portfolio", "personal site", "showcase"],
        "event_site": ["trips", "events", "schedule", "itinerary", "tours"],
        # v7.0: Native iOS types
        "ios_app": ["swift", "swiftui", "ios", "iphone", "ipad", "xcode", "native ios"],
        "plugin_module": ["plugin", "plug-in", "feature module", "swift package", "module"],
        "native_app": ["native app", "apple", "app store", "testflight"],
        "widget": ["widget", "widgetkit", "home screen widget"],
        "app_clip": ["app clip", "appclip"],
        "utility_app": ["utility", "tool app", "helper app"],
    }

    for product_type, keywords in type_keywords.items():
        if any(kw in idea_lower for kw in keywords):
            characteristics["product_types"].append(product_type)

    # Feature detection
    feature_keywords = {
        "realtime": ["realtime", "real-time", "live", "chat", "notifications"],
        "complex_relations": ["complex", "relationships", "many-to-many", "hierarchy"],
        "push_notifications": ["push notifications", "alerts", "mobile notifications"],
        "offline_first": ["offline", "sync", "works offline"],
        "background_jobs": ["background", "async", "queue", "scheduled"],
        "file_storage": ["upload", "files", "images", "documents", "storage"],
        # v7.0: Swift/iOS features
        "local_storage": ["local storage", "on-device", "device storage", "compress"],
        "compression": ["compression", "compress", "lossless", "decompress"],
        "swift_packages": ["swift package", "spm", "package.swift"],
        "swiftdata": ["swiftdata", "swift data", "persistent model"],
    }

    for feature, keywords in feature_keywords.items():
        if any(kw in idea_lower for kw in keywords):
            characteristics["features"].append(feature)

    # Complexity hints
    complexity_keywords = {
        "high": ["enterprise", "complex", "advanced", "sophisticated"],
        "low": ["simple", "basic", "minimal", "mvp", "quick"],
    }

    for level, keywords in complexity_keywords.items():
        if any(kw in idea_lower for kw in keywords):
            characteristics["complexity_hints"].append(level)

    return characteristics


def score_stack(stack: StackDefinition, characteristics: dict) -> int:
    """Score a stack based on how well it matches the product characteristics."""
    score = 0

    # Product type matching (most important — up to 30 pts per match)
    for product_type in characteristics["product_types"]:
        if product_type in PRODUCT_TYPE_STACKS:
            recommended = PRODUCT_TYPE_STACKS[product_type]
            if stack.id in recommended:
                # Score by position in recommendation list:
                # 1st choice = 30 pts, 2nd = 20 pts, 3rd = 10 pts.
                # First recommendation is strongly preferred.
                position = recommended.index(stack.id)
                score += 30 - (position * 10)

    # Feature matching — 15 pts per matched feature (e.g., "realtime", "offline_first")
    for feature in characteristics["features"]:
        if feature in FEATURE_REQUIREMENTS:
            if stack.id in FEATURE_REQUIREMENTS[feature]:
                score += 15

    # Default stack gets a small bonus as a tie-breaker when scores are close.
    # This ensures nextjs-supabase wins when no strong signal points elsewhere.
    if stack.is_default:
        score += 5

    return score


def select_stack(idea: str, force_stack: StackId | None = None) -> tuple[StackId, str]:
    """Select the best stack for a product idea.

    Args:
        idea: The product idea description
        force_stack: Optional stack ID to force selection

    Returns:
        Tuple of (stack_id, rationale)
    """
    if force_stack:
        stack = STACKS.get(force_stack)
        if stack:
            return force_stack, f"Stack forced to {stack.name} via --stack flag."
        else:
            raise ValueError(f"Unknown stack: {force_stack}")

    characteristics = analyze_product_idea(idea)

    # Score all stacks
    scores: list[tuple[StackId, int, StackDefinition]] = []
    for stack_id, stack in STACKS.items():
        score = score_stack(stack, characteristics)
        scores.append((stack_id, score, stack))

    # Sort by score descending
    scores.sort(key=lambda x: x[1], reverse=True)

    best_id, best_score, best_stack = scores[0]

    # Build rationale
    rationale_parts = [f"Selected {best_stack.name} because:"]

    if characteristics["product_types"]:
        matched_types = [t for t in characteristics["product_types"]
                        if t in best_stack.product_types or
                        (t in PRODUCT_TYPE_STACKS and best_id in PRODUCT_TYPE_STACKS[t])]
        if matched_types:
            rationale_parts.append(f"- Product type matches: {', '.join(matched_types)}")

    if characteristics["features"]:
        matched_features = [f for f in characteristics["features"]
                          if f in best_stack.features or
                          (f in FEATURE_REQUIREMENTS and best_id in FEATURE_REQUIREMENTS[f])]
        if matched_features:
            rationale_parts.append(f"- Required features supported: {', '.join(matched_features)}")

    if best_stack.is_default and best_score < 20:
        rationale_parts.append("- Default stack for general-purpose applications")

    rationale_parts.append(f"- {best_stack.description}")

    return best_id, "\n".join(rationale_parts)


def get_stack_for_analysis(stack_id: StackId) -> dict:
    """Get stack info formatted for the Analyzer agent."""
    stack = STACKS[stack_id]
    return {
        "id": stack.id,
        "name": stack.name,
        "description": stack.description,
        "product_types": stack.product_types,
        "features": stack.features,
        "complexity": stack.complexity,
        "deployment": stack.deployment,
    }


def get_all_stacks_for_prompt() -> str:
    """Format all stacks for inclusion in agent prompts."""
    lines = ["## Available Stacks\n"]

    for stack in STACKS.values():
        default_marker = " (default)" if stack.is_default else ""
        lines.append(f"### {stack.name}{default_marker}")
        lines.append(f"**ID**: `{stack.id}`")
        lines.append(f"**Best for**: {', '.join(stack.product_types)}")
        lines.append(f"**Features**: {', '.join(stack.features)}")
        lines.append(f"**Complexity**: {stack.complexity}")
        lines.append(f"**Deploys to**: {stack.deployment}")
        lines.append(f"\n{stack.description}\n")

    return "\n".join(lines)
