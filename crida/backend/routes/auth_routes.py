"""
routes/auth_routes.py — Authentication Endpoints
=================================================
Endpoints:
  POST /api/v1/auth/login           — verify credentials, return JWT
  GET  /api/v1/auth/me              — return logged-in officer profile
  PUT  /api/v1/auth/change-password — change own password (bcrypt)

ACID:
  Login:           Audit_Log INSERT (auto-commit, non-blocking)
  Change-password: UPDATE Officer + Audit_Log in one transaction
                   → both succeed or both rollback

Password strategy:
  New hashes  → bcrypt ($2b$ prefix) — always stored after change
  Legacy seed → plaintext equality   — seed data uses 'hash' string
"""

import jwt
import datetime
import logging

from flask import Blueprint, request, jsonify, g
from flask_bcrypt import Bcrypt

from config import Config
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from utils.validators import require_fields

logger  = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)
bcrypt  = Bcrypt()


# ── Password verifier (supports bcrypt + legacy plaintext) ────────────────
def _check_password(stored: str, plain: str) -> bool:
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        try:
            return bcrypt.check_password_hash(stored, plain)
        except Exception:
            return False
    return stored == plain          # legacy plaintext from seed data


# ── POST /login ─────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    """
    POST /api/v1/auth/login
    Body:    { "email": "...", "password": "..." }
    Returns: { "token": "eyJ...", "officer": {...} }
    """
    data = request.json or {}
    ok, err = require_fields(data, "email", "password")
    if not ok:
        return jsonify({"error": err}), 400

    officer = execute_query(
        """SELECT o.officer_id, o.full_name, o.email, o.password_hash,
                  o.office_id, o.is_active,
                  r.role_name, r.access_level, r.role_id
           FROM Officer o
           JOIN Role r ON o.role_id = r.role_id
           WHERE o.email = %s AND o.is_active = 1""",
        (data["email"],), fetch='one'
    )

    if not officer or not _check_password(officer["password_hash"], data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    expiry = datetime.datetime.utcnow() + datetime.timedelta(
        hours=Config.JWT_EXPIRY_HOURS
    )
    token = jwt.encode(
        {
            "officer_id":   officer["officer_id"],
            "role_name":    officer["role_name"],
            "access_level": officer["access_level"],
            "exp":          expiry,
        },
        Config.JWT_SECRET_KEY,
        algorithm="HS256"
    )

    # Audit log — non-blocking
    try:
        execute_query(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, ip_address)
               VALUES (%s, 'LOGIN', 'Officer', %s)""",
            (officer["officer_id"], request.remote_addr or "unknown")
        )
    except Exception as e:
        logger.warning(f"Audit log on login failed (non-critical): {e}")

    return jsonify({
        "token": token,
        "officer": {
            "officer_id":   officer["officer_id"],
            "full_name":    officer["full_name"],
            "email":        officer["email"],
            "role_name":    officer["role_name"],
            "access_level": officer["access_level"],
            "office_id":    officer["office_id"],
        }
    }), 200


# ── GET /me ──────────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    """GET /api/v1/auth/me — returns profile of authenticated officer."""
    return jsonify({"officer": g.officer}), 200


# ── PUT /change-password ─────────────────────────────────────────────────
@auth_bp.route("/change-password", methods=["PUT"])
@token_required
def change_password():
    """
    PUT /api/v1/auth/change-password
    Body: { "current_password": "...", "new_password": "..." }

    ACID transaction:
      Step 1 — UPDATE Officer SET password_hash = new_bcrypt_hash
      Step 2 — INSERT Audit_Log
      Both commit or both rollback.
    """
    data = request.json or {}
    ok, err = require_fields(data, "current_password", "new_password")
    if not ok:
        return jsonify({"error": err}), 400

    if len(data["new_password"]) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    row = execute_query(
        "SELECT password_hash FROM Officer WHERE officer_id = %s",
        (g.officer["officer_id"],), fetch='one'
    )
    if not row:
        return jsonify({"error": "Officer not found"}), 404

    if not _check_password(row["password_hash"], data["current_password"]):
        return jsonify({"error": "Current password is incorrect"}), 400

    new_hash = bcrypt.generate_password_hash(data["new_password"]).decode("utf-8")

    def ops(conn, cursor):
        cursor.execute(
            "UPDATE Officer SET password_hash = %s WHERE officer_id = %s",
            (new_hash, g.officer["officer_id"])
        )
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name,
                    record_id, new_values, ip_address)
               VALUES (%s, 'UPDATE', 'Officer', %s, 'password_changed', %s)""",
            (g.officer["officer_id"],
             g.officer["officer_id"],
             request.remote_addr or "unknown")
        )
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "Password updated successfully"}), 200
