"""
routes/permission_routes.py — Granular Permission Management
=============================================================
Endpoints (all under /api/v1/permissions/):

  GET  /           — list all granted permissions (Admin only)
  POST /grant      — grant a permission to an officer (Admin only)
  DELETE /revoke   — revoke a permission (Admin only)
  GET  /my-permissions — return caller's own permissions

RBAC note:
  Admin role ALWAYS bypasses permission checks (see rbac.py).
  All other roles need explicit rows in the Permission table.

Available permission_name values (12 total):
  manage_citizens, manage_cnic, manage_passport, manage_license,
  manage_registrations, manage_security, manage_complaints,
  view_reports, manage_officers, manage_payments,
  generate_pdf, manage_biometric
"""

import logging

from flask import Blueprint, request, jsonify, g

from db import execute_query
from middleware.auth import token_required
from middleware.rbac import role_required

logger        = logging.getLogger(__name__)
permission_bp = Blueprint("permissions", __name__)

VALID_PERMISSIONS = [
    'manage_citizens', 'manage_cnic', 'manage_passport', 'manage_license',
    'manage_registrations', 'manage_security', 'manage_complaints',
    'view_reports', 'manage_officers', 'manage_payments',
    'generate_pdf', 'manage_biometric',
]


# ── GET / — list all permissions ─────────────────────────────────────────
@permission_bp.route("/", methods=["GET"])
@token_required
@role_required("Admin")
def list_permissions():
    """
    GET /api/v1/permissions/
    Returns every permission row joined with officer name and role.
    Admin only.
    """
    rows = execute_query(
        """SELECT p.permission_id, p.permission_name,
                  p.granted_at, p.granted_by,
                  o.officer_id, o.full_name,
                  r.role_name
           FROM Permission p
           JOIN Officer o ON p.officer_id = o.officer_id
           JOIN Role    r ON o.role_id    = r.role_id
           ORDER BY o.full_name, p.permission_name""",
        fetch='all'
    )
    return jsonify({"permissions": rows or []}), 200


# ── POST /grant ───────────────────────────────────────────────────────────
@permission_bp.route("/grant", methods=["POST"])
@token_required
@role_required("Admin")
def grant_permission():
    """
    POST /api/v1/permissions/grant
    Body: { "officer_id": 2, "permission_name": "manage_citizens" }

    Uses INSERT IGNORE so granting an already-granted permission is
    idempotent (no 400 error, just a no-op).
    """
    data = request.json or {}

    if not data.get("officer_id") or not data.get("permission_name"):
        return jsonify({"error": "officer_id and permission_name are required"}), 400

    if data["permission_name"] not in VALID_PERMISSIONS:
        return jsonify({
            "error": f"Invalid permission_name. Valid values: {VALID_PERMISSIONS}"
        }), 400

    # Confirm the target officer exists
    target = execute_query(
        "SELECT officer_id, full_name FROM Officer WHERE officer_id = %s",
        (data["officer_id"],), fetch='one'
    )
    if not target:
        return jsonify({"error": "Target officer not found"}), 404

    execute_query(
        """INSERT IGNORE INTO Permission
               (officer_id, permission_name, granted_by)
           VALUES (%s, %s, %s)""",
        (data["officer_id"],
         data["permission_name"],
         g.officer["officer_id"])
    )

    logger.info(
        f"Admin {g.officer['officer_id']} granted '{data['permission_name']}'"
        f" to officer {data['officer_id']}"
    )
    return jsonify({
        "message": f"Permission '{data['permission_name']}' granted "
                   f"to {target['full_name']}"
    }), 201


# ── DELETE /revoke ────────────────────────────────────────────────────────
@permission_bp.route("/revoke", methods=["DELETE"])
@token_required
@role_required("Admin")
def revoke_permission():
    """
    DELETE /api/v1/permissions/revoke
    Body: { "officer_id": 2, "permission_name": "manage_citizens" }
    """
    data = request.json or {}

    if not data.get("officer_id") or not data.get("permission_name"):
        return jsonify({"error": "officer_id and permission_name are required"}), 400

    execute_query(
        "DELETE FROM Permission WHERE officer_id = %s AND permission_name = %s",
        (data["officer_id"], data["permission_name"])
    )

    logger.info(
        f"Admin {g.officer['officer_id']} revoked '{data['permission_name']}'"
        f" from officer {data['officer_id']}"
    )
    return jsonify({"message": "Permission revoked"}), 200


# ── GET /my-permissions ───────────────────────────────────────────────────
@permission_bp.route("/my-permissions", methods=["GET"])
@token_required
def my_permissions():
    """
    GET /api/v1/permissions/my-permissions
    Returns the caller's role and their list of granted permissions.
    Admin role returns all valid permissions (bypasses table check).
    """
    if g.officer["role_name"] == "Admin":
        # Admin has all permissions implicitly — return the full list
        return jsonify({
            "role":        g.officer["role_name"],
            "permissions": VALID_PERMISSIONS,
            "note":        "Admin role implicitly has all permissions"
        }), 200

    rows = execute_query(
        "SELECT permission_name FROM Permission WHERE officer_id = %s",
        (g.officer["officer_id"],), fetch='all'
    )
    return jsonify({
        "role":        g.officer["role_name"],
        "permissions": [r["permission_name"] for r in (rows or [])]
    }), 200
