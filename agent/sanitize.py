"""Input sanitization for Product Agent v9.0.

Prevents prompt injection by stripping dangerous markers and
control characters from user-provided idea text.
"""

import re

# Maximum allowed length for a product idea
MAX_IDEA_LENGTH = 5000

# Patterns that could be used for prompt injection
_INJECTION_PATTERNS = [
    r'##\s*SYSTEM\s*:',       # Markdown-style system prompt override
    r'<\s*system\s*>',         # XML-style system tag
    r'</\s*system\s*>',
    r'IGNORE\s+(?:ALL\s+)?(?:PREVIOUS|ABOVE)\s+INSTRUCTIONS',
    r'OVERRIDE\s+(?:ALL\s+)?(?:PREVIOUS|ABOVE)\s+INSTRUCTIONS',
    r'YOU\s+ARE\s+NOW\s+(?:A|AN)\s+',  # Role reassignment
    r'FORGET\s+(?:ALL\s+)?(?:PREVIOUS|YOUR)\s+INSTRUCTIONS',
    r'NEW\s+SYSTEM\s+PROMPT',
]

_INJECTION_RE = re.compile(
    '|'.join(_INJECTION_PATTERNS),
    re.IGNORECASE,
)

# Control characters (except newline, tab, carriage return)
_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def sanitize_idea(idea: str) -> str:
    """Sanitize a user-provided product idea.

    - Strips prompt injection markers
    - Removes control characters (preserves newlines/tabs)
    - Caps at MAX_IDEA_LENGTH characters
    - Strips leading/trailing whitespace

    Args:
        idea: Raw user input

    Returns:
        Sanitized idea string
    """
    # Remove control characters
    idea = _CONTROL_CHARS_RE.sub('', idea)

    # Strip injection patterns
    idea = _INJECTION_RE.sub('[removed]', idea)

    # Cap length
    if len(idea) > MAX_IDEA_LENGTH:
        idea = idea[:MAX_IDEA_LENGTH]

    return idea.strip()
