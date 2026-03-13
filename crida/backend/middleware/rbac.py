"""
middleware/rbac.py — Role-Based Access Control Decorators
==========================================================
Three levels of authorisation enforced as view decorators:

  1. @role_required("Admin", "Registrar")
       → officer's role_name must be in the given list

  2. @permission_required("manage_citizens", "manage_cnic")
       → Admin always passes; others need at least one matching row
         in the Permission table (set up via setup_database.sql)

  3. @access_level_required(4)
       → officer's numeric access_level must be >= the threshold

Decorators must be applied AFTER @token_required (which populates g.officer).

Example:
    @bp.route("/approve/<int:id>", methods=["PUT"])
    @token_required
    @role_required("Admin", "Registrar")
    def approve(id):
        ...
"""

from functools import wraps
from flask import jsonify, g

from db import execute_query


# ── Role check ─────────────────────────────────────────────────────────────
def role_required(*roles):
    """Allow only officers whose role_name is in the given list."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.officer["role_name"] not in roles:
                return jsonify({"error": "Insufficient role privileges"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Granular permission check ──────────────────────────────────────────────
def permission_required(*perms):
    """
    Allow if officer has Admin role OR has ANY of the listed permissions.
    Permissions are stored in the Permission table (Phase 2 extra table).
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Admin always bypasses granular permission checks
            if g.officer["role_name"] == "Admin":
                return f(*args, **kwargs)

            # Check Permission table for at least one matching permission
            placeholders = ",".join(["%s"] * len(perms))
            row = execute_query(
                f"""SELECT COUNT(*) AS cnt
                    FROM Permission
                    WHERE officer_id = %s
                      AND permission_name IN ({placeholders})""",
                (g.officer["officer_id"], *perms), fetch='one'
            )

            if not row or row["cnt"] == 0:
                return jsonify({"error": "Permission denied"}), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Numeric access level check ─────────────────────────────────────────────
def access_level_required(min_level):
    """Allow only officers with access_level >= min_level."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.officer["access_level"] < min_level:
                return jsonify({"error": f"Requires access level {min_level}+"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
