"""Stack selection system for Product Agent v6.0."""

from .criteria import (
    StackId,
    StackDefinition,
    STACKS,
    get_default_stack,
    get_stack,
    list_stacks,
)
from .selector import (
    select_stack,
    analyze_product_idea,
    get_stack_for_analysis,
    get_all_stacks_for_prompt,
)

__all__ = [
    "StackId",
    "StackDefinition",
    "STACKS",
    "get_default_stack",
    "get_stack",
    "list_stacks",
    "select_stack",
    "analyze_product_idea",
    "get_stack_for_analysis",
    "get_all_stacks_for_prompt",
]
