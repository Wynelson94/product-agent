"""Tests for stack selection logic and criteria (v7.0)."""

import pytest

from agent.stacks.selector import (
    analyze_product_idea,
    score_stack,
    select_stack,
    get_stack_for_analysis,
    get_all_stacks_for_prompt,
)
from agent.stacks.criteria import (
    STACKS,
    PRODUCT_TYPE_STACKS,
    FEATURE_REQUIREMENTS,
    StackDefinition,
    get_default_stack,
    get_stack,
    list_stacks,
    check_stack_deployment_compatibility,
)


class TestAnalyzeProductIdea:
    """Tests for keyword-based product idea analysis."""

    def test_marketplace_keyword(self):
        """Test that 'marketplace' is detected as a marketplace product type."""
        result = analyze_product_idea("Build an online marketplace for handmade goods")
        assert "marketplace" in result["product_types"]

    def test_mobile_app_keyword(self):
        """Test that 'mobile app' is detected as a mobile_app product type."""
        result = analyze_product_idea("Create a mobile app for fitness tracking")
        assert "mobile_app" in result["product_types"]

    def test_swift_keyword_detects_ios_app(self):
        """Test that 'swift' triggers ios_app product type."""
        result = analyze_product_idea("Build a swift utility for file management")
        assert "ios_app" in result["product_types"]

    def test_ios_keyword_detects_ios_app(self):
        """Test that 'ios' triggers both ios_app and mobile_app product types."""
        result = analyze_product_idea("Build an iOS application")
        assert "ios_app" in result["product_types"]
        assert "mobile_app" in result["product_types"]

    def test_widget_keyword(self):
        """Test that 'widget' triggers widget product type."""
        result = analyze_product_idea("Build a home screen widget for weather")
        assert "widget" in result["product_types"]

    def test_saas_subscription_keywords(self):
        """Test that 'saas subscription' triggers saas product type."""
        result = analyze_product_idea("Build a saas subscription platform for teams")
        assert "saas" in result["product_types"]

    def test_nonprofit_website_keywords(self):
        """Test that 'nonprofit website' triggers both nonprofit and content_site."""
        result = analyze_product_idea("Rebuild a nonprofit website for a local charity")
        assert "nonprofit" in result["product_types"]
        assert "content_site" in result["product_types"]

    def test_feature_realtime_chat(self):
        """Test that 'realtime chat' triggers realtime feature detection."""
        result = analyze_product_idea("Build an app with realtime chat functionality")
        assert "realtime" in result["features"]

    def test_feature_compression(self):
        """Test that 'compression' triggers compression feature detection."""
        result = analyze_product_idea("Create a tool with lossless compression support")
        assert "compression" in result["features"]

    def test_feature_swiftdata(self):
        """Test that 'swiftdata' triggers swiftdata feature detection."""
        result = analyze_product_idea("Use swiftdata for persistent model storage")
        assert "swiftdata" in result["features"]

    def test_complexity_enterprise(self):
        """Test that 'enterprise' triggers high complexity hint."""
        result = analyze_product_idea("Build an enterprise resource planning system")
        assert "high" in result["complexity_hints"]

    def test_complexity_simple_mvp(self):
        """Test that 'simple mvp' triggers low complexity hint."""
        result = analyze_product_idea("Build a simple mvp for a todo app")
        assert "low" in result["complexity_hints"]

    def test_empty_idea_returns_empty_lists(self):
        """Test that a generic idea with no keywords returns empty lists."""
        result = analyze_product_idea("Build something")
        assert result["product_types"] == []
        assert result["features"] == []
        assert result["complexity_hints"] == []


class TestScoreStack:
    """Tests for stack scoring based on product characteristics."""

    def test_marketplace_scores_highest_for_nextjs_prisma(self):
        """Test that a marketplace idea scores highest for nextjs-prisma."""
        characteristics = analyze_product_idea("Build an online marketplace")
        scores = {}
        for stack_id, stack in STACKS.items():
            scores[stack_id] = score_stack(stack, characteristics)
        assert scores["nextjs-prisma"] > scores["nextjs-supabase"]
        assert scores["nextjs-prisma"] > scores["expo-supabase"]

    def test_mobile_app_scores_highest_for_expo(self):
        """Test that a mobile app idea scores highest for expo-supabase."""
        characteristics = analyze_product_idea("Create a mobile app for users")
        scores = {}
        for stack_id, stack in STACKS.items():
            scores[stack_id] = score_stack(stack, characteristics)
        assert scores["expo-supabase"] == max(scores.values())

    def test_ios_swift_scores_highest_for_swift_swiftui(self):
        """Test that an iOS/swift idea scores highest for swift-swiftui."""
        characteristics = analyze_product_idea("Build a native iOS swift utility app")
        scores = {}
        for stack_id, stack in STACKS.items():
            scores[stack_id] = score_stack(stack, characteristics)
        assert scores["swift-swiftui"] == max(scores.values())

    def test_generic_idea_default_wins_via_tiebreaker(self):
        """Test that a generic idea selects the default stack via tie-breaker bonus."""
        characteristics = analyze_product_idea("Build something cool")
        scores = {}
        for stack_id, stack in STACKS.items():
            scores[stack_id] = score_stack(stack, characteristics)
        # Default stack gets +5 bonus, all others get 0
        assert scores["nextjs-supabase"] == 5
        non_default_scores = [s for sid, s in scores.items() if sid != "nextjs-supabase"]
        assert all(s == 0 for s in non_default_scores)

    def test_feature_matching_adds_points(self):
        """Test that matching features contribute to the score."""
        characteristics = {
            "product_types": [],
            "features": ["realtime"],
            "complexity_hints": [],
        }
        score_supabase = score_stack(STACKS["nextjs-supabase"], characteristics)
        score_prisma = score_stack(STACKS["nextjs-prisma"], characteristics)
        # realtime maps to nextjs-supabase, not nextjs-prisma
        assert score_supabase > score_prisma

    def test_first_recommendation_scores_higher_than_second(self):
        """Test that being the first recommended stack gives a higher score."""
        # For "marketplace", nextjs-prisma is first, rails is second
        characteristics = {
            "product_types": ["marketplace"],
            "features": [],
            "complexity_hints": [],
        }
        score_prisma = score_stack(STACKS["nextjs-prisma"], characteristics)
        score_rails = score_stack(STACKS["rails"], characteristics)
        assert score_prisma > score_rails


class TestSelectStack:
    """Tests for the top-level stack selection function."""

    def test_marketplace_selects_nextjs_prisma(self):
        """Test that a marketplace idea selects nextjs-prisma."""
        stack_id, _ = select_stack("Build a marketplace for buying and selling art")
        assert stack_id == "nextjs-prisma"

    def test_mobile_app_selects_expo(self):
        """Test that a mobile app idea selects expo-supabase."""
        stack_id, _ = select_stack("Build a mobile app for food delivery")
        assert stack_id == "expo-supabase"

    def test_ios_plugin_selects_swift_swiftui(self):
        """Test that an iOS plugin idea selects swift-swiftui."""
        stack_id, _ = select_stack("Build an iOS plugin for compression")
        assert stack_id == "swift-swiftui"

    def test_generic_idea_selects_default(self):
        """Test that a generic todo app selects the default stack."""
        stack_id, _ = select_stack("Build a todo app")
        assert stack_id == "nextjs-supabase"

    def test_force_stack_overrides_selection(self):
        """Test that force_stack bypasses analysis and returns the forced stack."""
        stack_id, rationale = select_stack("Build a marketplace", force_stack="rails")
        assert stack_id == "rails"
        assert "forced" in rationale.lower()

    def test_force_stack_invalid_raises_value_error(self):
        """Test that an invalid force_stack raises ValueError."""
        with pytest.raises(ValueError, match="Unknown stack"):
            select_stack("Build something", force_stack="nonexistent-stack")

    def test_rationale_is_non_empty(self):
        """Test that the rationale string is always non-empty."""
        _, rationale = select_stack("Build a dashboard for analytics")
        assert len(rationale) > 0

    def test_rationale_mentions_product_type_matches(self):
        """Test that rationale includes product type match information."""
        _, rationale = select_stack("Build a marketplace with complex relationships")
        assert "Product type matches" in rationale
        assert "marketplace" in rationale


class TestCriteriaHelpers:
    """Tests for criteria helper functions."""

    def test_get_default_stack_returns_nextjs_supabase(self):
        """Test that the default stack is nextjs-supabase."""
        default = get_default_stack()
        assert default.id == "nextjs-supabase"
        assert default.is_default is True

    def test_get_stack_nextjs_supabase(self):
        """Test retrieving nextjs-supabase by ID."""
        stack = get_stack("nextjs-supabase")
        assert stack.id == "nextjs-supabase"
        assert stack.name == "Next.js + Supabase"

    def test_get_stack_nextjs_prisma(self):
        """Test retrieving nextjs-prisma by ID."""
        stack = get_stack("nextjs-prisma")
        assert stack.id == "nextjs-prisma"
        assert stack.name == "Next.js + Prisma + PostgreSQL"

    def test_get_stack_rails(self):
        """Test retrieving rails by ID."""
        stack = get_stack("rails")
        assert stack.id == "rails"
        assert stack.name == "Ruby on Rails"

    def test_get_stack_expo_supabase(self):
        """Test retrieving expo-supabase by ID."""
        stack = get_stack("expo-supabase")
        assert stack.id == "expo-supabase"
        assert stack.name == "Expo (React Native) + Supabase"

    def test_get_stack_swift_swiftui(self):
        """Test retrieving swift-swiftui by ID."""
        stack = get_stack("swift-swiftui")
        assert stack.id == "swift-swiftui"
        assert stack.name == "Swift + SwiftUI"

    def test_list_stacks_returns_all(self):
        """Test that list_stacks returns all 8 stacks."""
        stacks = list_stacks()
        assert len(stacks) == 8
        ids = {s.id for s in stacks}
        assert ids == {
            "nextjs-supabase", "nextjs-prisma", "rails", "expo-supabase", "swift-swiftui",
            "django-htmx", "sveltekit", "astro",
        }

    def test_deployment_compat_vercel_postgresql(self):
        """Test that nextjs-supabase + vercel + postgresql is compatible."""
        compatible, error = check_stack_deployment_compatibility(
            "nextjs-supabase", "vercel", "postgresql"
        )
        assert compatible is True
        assert error is None

    def test_deployment_compat_vercel_sqlite_incompatible(self):
        """Test that nextjs-supabase + vercel + sqlite is incompatible."""
        compatible, error = check_stack_deployment_compatibility(
            "nextjs-supabase", "vercel", "sqlite"
        )
        assert compatible is False
        assert error is not None
        assert "incompatible" in error.lower()

    def test_deployment_compat_rails_railway_sqlite(self):
        """Test that rails + railway + sqlite is compatible."""
        compatible, error = check_stack_deployment_compatibility(
            "rails", "railway", "sqlite"
        )
        assert compatible is True
        assert error is None

    def test_deployment_compat_unknown_stack(self):
        """Test that an unknown stack returns incompatible."""
        compatible, error = check_stack_deployment_compatibility(
            "nonexistent-stack", "vercel", "postgresql"
        )
        assert compatible is False
        assert "Unknown stack" in error


class TestStackCompleteness:
    """Tests to ensure stack definitions are complete and internally consistent."""

    def test_all_stacks_have_product_types(self):
        """Test that every stack has at least one product type."""
        for stack_id, stack in STACKS.items():
            assert len(stack.product_types) > 0, f"Stack {stack_id} has no product_types"

    def test_all_stacks_have_features(self):
        """Test that every stack has at least one feature."""
        for stack_id, stack in STACKS.items():
            assert len(stack.features) > 0, f"Stack {stack_id} has no features"

    def test_product_type_stacks_reference_valid_ids(self):
        """Test that all stack IDs in PRODUCT_TYPE_STACKS are valid."""
        valid_ids = set(STACKS.keys())
        for product_type, stack_ids in PRODUCT_TYPE_STACKS.items():
            for sid in stack_ids:
                assert sid in valid_ids, (
                    f"PRODUCT_TYPE_STACKS['{product_type}'] references "
                    f"invalid stack ID '{sid}'"
                )

    def test_feature_requirements_reference_valid_ids(self):
        """Test that all stack IDs in FEATURE_REQUIREMENTS are valid."""
        valid_ids = set(STACKS.keys())
        for feature, stack_ids in FEATURE_REQUIREMENTS.items():
            for sid in stack_ids:
                assert sid in valid_ids, (
                    f"FEATURE_REQUIREMENTS['{feature}'] references "
                    f"invalid stack ID '{sid}'"
                )

    def test_swift_swiftui_has_at_least_five_product_types(self):
        """Test that swift-swiftui has >= 5 product types."""
        swift_stack = STACKS["swift-swiftui"]
        assert len(swift_stack.product_types) >= 5, (
            f"swift-swiftui should have >= 5 product types, "
            f"got {len(swift_stack.product_types)}: {swift_stack.product_types}"
        )

    def test_swift_swiftui_has_at_least_five_features(self):
        """Test that swift-swiftui has >= 5 features."""
        swift_stack = STACKS["swift-swiftui"]
        assert len(swift_stack.features) >= 5, (
            f"swift-swiftui should have >= 5 features, "
            f"got {len(swift_stack.features)}: {swift_stack.features}"
        )


class TestStackForAnalysis:
    """Tests for get_stack_for_analysis output format."""

    def test_returns_expected_fields(self):
        """Test that get_stack_for_analysis returns all expected keys."""
        result = get_stack_for_analysis("nextjs-supabase")
        expected_keys = {"id", "name", "description", "product_types", "features", "complexity", "deployment"}
        assert set(result.keys()) == expected_keys

    def test_values_match_stack_definition(self):
        """Test that returned values match the underlying StackDefinition."""
        result = get_stack_for_analysis("swift-swiftui")
        stack = STACKS["swift-swiftui"]
        assert result["id"] == stack.id
        assert result["name"] == stack.name
        assert result["description"] == stack.description
        assert result["product_types"] == stack.product_types
        assert result["features"] == stack.features
        assert result["complexity"] == stack.complexity
        assert result["deployment"] == stack.deployment


class TestAllStacksForPrompt:
    """Tests for get_all_stacks_for_prompt formatting."""

    def test_contains_all_stack_names(self):
        """Test that the prompt output contains every stack name."""
        output = get_all_stacks_for_prompt()
        for stack in STACKS.values():
            assert stack.name in output, f"Stack name '{stack.name}' not found in prompt output"

    def test_default_stack_is_marked(self):
        """Test that the default stack is explicitly marked in the prompt output."""
        output = get_all_stacks_for_prompt()
        assert "(default)" in output
        # Verify the default marker appears near the default stack name
        default_stack = get_default_stack()
        assert f"{default_stack.name} (default)" in output
