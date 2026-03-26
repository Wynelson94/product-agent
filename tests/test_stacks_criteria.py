"""Tests for stack definitions and criteria (agent/stacks/criteria.py)."""

from agent.stacks.criteria import (
    STACKS,
    StackDefinition,
    PRODUCT_TYPE_STACKS,
    FEATURE_REQUIREMENTS,
)


class TestStackDefinitions:
    """Tests for the STACKS dictionary."""

    def test_all_stacks_exist(self):
        """All expected stacks should be defined."""
        expected = {
            "nextjs-supabase", "nextjs-prisma", "rails",
            "django-htmx", "sveltekit", "astro",
            "expo-supabase", "swift-swiftui",
        }
        assert set(STACKS.keys()) == expected

    def test_stacks_are_stack_definitions(self):
        """Each stack should be a StackDefinition instance."""
        for stack_id, stack in STACKS.items():
            assert isinstance(stack, StackDefinition), f"{stack_id} is not a StackDefinition"

    def test_each_stack_has_required_fields(self):
        """Each stack should have id, name, description, product_types, features."""
        for stack_id, stack in STACKS.items():
            assert stack.id == stack_id, f"Stack id mismatch: {stack.id} != {stack_id}"
            assert stack.name, f"{stack_id} missing name"
            assert stack.description, f"{stack_id} missing description"
            assert len(stack.product_types) > 0, f"{stack_id} has no product types"
            assert len(stack.features) > 0, f"{stack_id} has no features"

    def test_default_stack_exists(self):
        """nextjs-supabase should be the default stack."""
        default = STACKS["nextjs-supabase"]
        assert default.is_default is True

    def test_only_one_default(self):
        """Only one stack should be marked as default."""
        defaults = [s for s in STACKS.values() if s.is_default]
        assert len(defaults) == 1

    def test_deployment_types_valid(self):
        """Each stack should have a valid deployment type."""
        valid_types = {"serverless", "traditional", "mobile", "static"}
        for stack_id, stack in STACKS.items():
            assert stack.deployment_type in valid_types, (
                f"{stack_id} has invalid deployment_type: {stack.deployment_type}"
            )


class TestProductTypeStacks:
    """Tests for the PRODUCT_TYPE_STACKS mapping."""

    def test_is_dict(self):
        """PRODUCT_TYPE_STACKS should be a dict."""
        assert isinstance(PRODUCT_TYPE_STACKS, dict)

    def test_all_values_are_lists_of_valid_stacks(self):
        """Each product type should map to a list of valid stack IDs."""
        for product_type, stack_ids in PRODUCT_TYPE_STACKS.items():
            assert isinstance(stack_ids, list), f"{product_type} should map to a list"
            for sid in stack_ids:
                assert sid in STACKS, f"{product_type} references unknown stack: {sid}"

    def test_no_nocloud_references(self):
        """No NoCloud BS product types should remain."""
        for product_type in PRODUCT_TYPE_STACKS:
            assert "nocloud" not in product_type.lower(), f"Found NoCloud ref: {product_type}"


class TestFeatureRequirements:
    """Tests for the FEATURE_REQUIREMENTS mapping."""

    def test_is_dict(self):
        """FEATURE_REQUIREMENTS should be a dict."""
        assert isinstance(FEATURE_REQUIREMENTS, dict)

    def test_all_values_reference_valid_stacks(self):
        """Each feature should map to valid stack IDs."""
        for feature, stack_ids in FEATURE_REQUIREMENTS.items():
            for sid in stack_ids:
                assert sid in STACKS, f"Feature {feature} references unknown stack: {sid}"
