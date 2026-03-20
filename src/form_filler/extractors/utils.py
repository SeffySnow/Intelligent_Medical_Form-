"""Shared extraction utilities.

Pure functions — no I/O, no side-effects — so they are trivially testable.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def parse_date(date_str: str) -> dict[str, str]:
    """Parse ISO date string (YYYY-MM-DD) into day/month/year components."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return {
            "day": f"{dt.day:02d}",
            "month": f"{dt.month:02d}",
            "year": str(dt.year),
        }
    except ValueError:
        return {"day": "", "month": "", "year": ""}


def parse_phone(phone_str: str) -> dict[str, str]:
    """Parse phone number into area_code / first3 / last4 parts.

    Handles:
      10-digit: AAAFIRSTLAST  (6136565890)
      11-digit: 1AAAFIRSTLAST (16136565890)
      Dashed:   613-6565-890  (non-standard Canadian format)
    """
    digits = re.sub(r"\D", "", phone_str)

    if len(digits) == 10:
        return {"area_code": digits[:3], "first3": digits[3:6], "last4": digits[6:]}

    if len(digits) == 11:
        return {"area_code": digits[1:4], "first3": digits[4:7], "last4": digits[7:]}

    # Try dashed format: e.g. "613-6565-890"
    parts = phone_str.split("-")
    if len(parts) == 3:
        area_code = re.sub(r"\D", "", parts[0])
        remaining = re.sub(r"\D", "", "".join(parts[1:]))
        if len(remaining) >= 7:
            return {
                "area_code": area_code,
                "first3": remaining[:3],
                "last4": remaining[3:7],
            }

    return {"area_code": "", "first3": "", "last4": ""}


def format_address(address_obj: dict[str, Any]) -> str:
    """Format address dict into a single comma-separated string."""
    parts = [
        address_obj.get("street", ""),
        address_obj.get("city", ""),
        address_obj.get("province", ""),
        address_obj.get("postal_code", ""),
    ]
    return ", ".join(p for p in parts if p)


def is_filled(field_key: str, already_filled: dict[str, Any] | None) -> bool:
    """Return True if *field_key* has a non-empty value in *already_filled*."""
    if not already_filled:
        return False
    obj = already_filled.get(field_key)
    if not isinstance(obj, dict):
        return False
    value = obj.get("value")
    return value is not None and str(value).strip() != ""


def make_entry(
    value: Any,
    source: str,
    reasoning: str,
    confidence: float,
    evidence: str | None = None,
) -> dict[str, Any]:
    """Build a standardised answer-entry dict."""
    return {
        "value": value,
        "source": source,
        "reasoning": reasoning,
        "confidence": float(confidence),
        "evidence": evidence,
    }
