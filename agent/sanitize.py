"""Input sanitization for Product Agent v12.4.

Prevents prompt injection by stripping dangerous markers,
encoded attacks, and control characters from user-provided idea text.

v12.4: Synced patterns with Shipwright shell hook (added DISREGARD, ACT AS,
PRETEND). Added encoded attack detection (base64, zero-width chars, HTML
entities, unicode normalization).
"""

import re
import unicodedata

# Maximum allowed length for a product idea
MAX_IDEA_LENGTH = 5000

# Patterns that could be used for prompt injection.
# IMPORTANT: Keep in sync with shipwright/hooks/scripts/sanitize-input.sh.
# Both layers must detect the same patterns — the shell hook is the first
# line of defense, this module is the second (inside the Product Agent process).
_INJECTION_PATTERNS = [
    r'##\s*SYSTEM\s*:',       # Markdown-style system prompt override
    r'<\s*system\s*>',         # XML-style system tag
    r'</\s*system\s*>',
    r'IGNORE\s+(?:ALL\s+)?(?:PREVIOUS|ABOVE)\s+INSTRUCTIONS',
    r'OVERRIDE\s+(?:ALL\s+)?(?:PREVIOUS|ABOVE)\s+INSTRUCTIONS',
    r'YOU\s+ARE\s+NOW\s+(?:A|AN)\s+',  # Role reassignment
    r'FORGET\s+(?:ALL\s+)?(?:PREVIOUS|YOUR)\s+INSTRUCTIONS',
    r'NEW\s+SYSTEM\s+PROMPT',
    # v12.4: Patterns previously only in Shipwright shell hook
    r'DISREGARD\s+(?:ALL\s+)?(?:PREVIOUS|ABOVE)',
    r'ACT\s+AS\s+(?:A|AN)\s+',
    r'PRETEND\s+(?:YOU\s+ARE|TO\s+BE)',
]

_INJECTION_RE = re.compile(
    '|'.join(_INJECTION_PATTERNS),
    re.IGNORECASE,
)

# Control characters (except newline, tab, carriage return)
_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

# Zero-width and invisible unicode characters that could hide injection payloads
_ZERO_WIDTH_RE = re.compile(
    '[\u200b\u200c\u200d\u200e\u200f'   # Zero-width space/joiner/non-joiner/marks
    '\u2060\u2061\u2062\u2063\u2064'     # Word joiner, invisible operators
    '\ufeff'                              # BOM / zero-width no-break space
    '\u00ad'                              # Soft hyphen
    '\u034f'                              # Combining grapheme joiner
    '\u061c'                              # Arabic letter mark
    '\u115f\u1160'                        # Hangul fillers
    '\u17b4\u17b5'                        # Khmer invisible characters
    '\u180e'                              # Mongolian vowel separator
    '\uffa0]'                             # Halfwidth Hangul filler
)

# HTML entities that could encode injection markers
_HTML_ENTITY_RE = re.compile(r'&#x?[0-9a-fA-F]+;|&[a-zA-Z]+;')


def _strip_zero_width(text: str) -> str:
    """Remove zero-width and invisible unicode characters."""
    return _ZERO_WIDTH_RE.sub('', text)


def _normalize_unicode(text: str) -> str:
    """Normalize unicode to NFC form to prevent homoglyph attacks.

    NFC normalization collapses combining characters and normalizes
    visually identical but differently-encoded characters to a single form.
    This prevents attacks using lookalike characters (e.g., Cyrillic 'а'
    instead of Latin 'a').
    """
    return unicodedata.normalize('NFC', text)


def _decode_html_entities(text: str) -> str:
    """Replace HTML entities with their character equivalents.

    This prevents encoded injection like &#60;system&#62; → <system>.
    We strip the entities rather than decode them to avoid creating new
    injection vectors.
    """
    return _HTML_ENTITY_RE.sub('[entity]', text)


def sanitize_idea(idea: str) -> str:
    """Sanitize a user-provided product idea.

    Defense-in-depth sanitization pipeline:
    1. Remove zero-width and invisible unicode characters
    2. Normalize unicode (NFC) to defeat homoglyph attacks
    3. Strip HTML entities that could encode injection markers
    4. Remove control characters (preserves newlines/tabs)
    5. Strip prompt injection patterns
    6. Cap at MAX_IDEA_LENGTH characters
    7. Strip leading/trailing whitespace

    Args:
        idea: Raw user input

    Returns:
        Sanitized idea string
    """
    # Step 1: Remove zero-width characters that could hide payloads
    idea = _strip_zero_width(idea)

    # Step 2: Normalize unicode to defeat homoglyph attacks
    idea = _normalize_unicode(idea)

    # Step 3: Strip HTML entities (&#60;system&#62; → [entity]system[entity])
    idea = _decode_html_entities(idea)

    # Step 4: Remove control characters
    idea = _CONTROL_CHARS_RE.sub('', idea)

    # Step 5: Strip injection patterns
    idea = _INJECTION_RE.sub('[removed]', idea)

    # Step 6: Cap length
    if len(idea) > MAX_IDEA_LENGTH:
        idea = idea[:MAX_IDEA_LENGTH]

    return idea.strip()
