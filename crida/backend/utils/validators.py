"""
utils/validators.py — Input Validation Helpers
===============================================
Used across all route files to validate and sanitise request data
before it ever touches a SQL query.

Functions:
  validate_national_id(nid)      → bool  — exactly 13 digits
  validate_phone(phone)          → bool  — exactly 11 digits
  validate_email(email)          → bool  — basic email format
  validate_date(d_str)           → bool  — YYYY-MM-DD
  require_fields(data, *fields)  → (bool, str|None)
  sanitize_string(s, max_len)    → str   — stripped, truncated
"""

import re
from datetime import date


def validate_national_id(nid):
    """Pakistan CNIC: exactly 13 numeric digits."""
    return bool(re.fullmatch(r'[0-9]{13}', str(nid or "")))


def validate_phone(phone):
    """Pakistan phone number: exactly 11 numeric digits."""
    return bool(re.fullmatch(r'[0-9]{11}', str(phone or "")))


def validate_email(email):
    """Basic email format check."""
    return bool(re.fullmatch(r'[^@]+@[^@]+\.[^@]+', str(email or "")))


def validate_date(d_str):
    """Accept ISO date strings: YYYY-MM-DD."""
    try:
        date.fromisoformat(str(d_str))
        return True
    except (ValueError, TypeError):
        return False


def require_fields(data, *fields):
    """
    Verify all required fields are present and non-empty.

    Returns (True, None) on success.
    Returns (False, error_message) listing missing fields.

    Usage:
        ok, err = require_fields(request.json, 'name', 'email')
        if not ok:
            return jsonify({"error": err}), 400
    """
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    return True, None


def sanitize_string(s, max_len=255):
    """Strip whitespace and truncate to max_len characters."""
    return str(s or "").strip()[:max_len]
