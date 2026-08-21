"""
Shared utility functions for the Tackle Hunger validation pipeline.

Centralizes helpers used by multiple modules (ai_validate, aggregate_summary, etc.)
to avoid duplication and ensure consistent behavior.
"""

from __future__ import annotations

import re
from typing import Any, Optional


def phone_digits(value: Any) -> Optional[str]:
    """
    Return only the digits of a phone string for equivalence comparison.

    Examples:
      "(555) 010-0123" -> "5550100123"
      "555-010-0123"    -> "5550100123"
      None / blank      -> None
    """
    if value is None:
        return None
    digits = re.sub(r"\D+", "", str(value))
    return digits or None


def canonical_url(value: Any) -> Optional[str]:
    """
    Return a canonical form of a URL suitable for equivalence comparison only.

    Rules:
      - strip http:// or https:// scheme
      - strip a leading 'www.'
      - strip trailing slashes
      - lowercase

    NOTE: this is for comparison ONLY. Display values are never replaced
    with this canonical form.
    """
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    s = re.sub(r"^https?://", "", s)
    if s.startswith("www."):
        s = s[4:]
    s = s.rstrip("/")
    return s or None
