"""
routes/auth_routes.py — Authentication Endpoints
=================================================
Endpoints:
  POST /api/v1/auth/login           — verify credentials, return JWT
  POST /api/v1/auth/citizen-login   — citizen self-service login (NID + citizen_id)
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
import re
import datetime
import logging
import os

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


# ── POST /citizen-login ──────────────────────────────────────────────────
@auth_bp.route("/citizen-login", methods=["POST"])
def citizen_login():
    """
    POST /api/v1/auth/citizen-login
    Body:    { "national_id_number": "1234567890123", "citizen_id": 7 }
    Returns: { "token": "eyJ...", "citizen": {...} }

    Verifies that the NID + citizen_id pair matches the Citizen table.
    Issues a JWT with role = "Citizen" accepted by @token_required.
    No officer account or DB changes needed.
    """
    data = request.json or {}
    nid  = (data.get("national_id_number") or "").strip()
    cid  = data.get("citizen_id")

    if not nid or not cid:
        return jsonify({"error": "national_id_number and citizen_id are required"}), 400

    if not re.match(r'^\d{13}$', nid):
        return jsonify({"error": "National ID must be exactly 13 digits"}), 400

    # Verify NID + citizen_id pair exists
    citizen = execute_query(
        """SELECT citizen_id, first_name, last_name, national_id_number, status
           FROM Citizen
           WHERE citizen_id = %s AND national_id_number = %s""",
        (cid, nid), fetch="one"
    )

    if not citizen:
        return jsonify({"error": "No matching citizen found. Check your NID and Citizen ID."}), 404

    if citizen["status"] == "deceased":
        return jsonify({"error": "This citizen record is marked as deceased."}), 403

    if citizen["status"] == "blacklisted":
        return jsonify({"error": "Access denied. Contact your nearest CRIDA office."}), 403

    # Issue JWT — officer_id field reused as citizen_id so @token_required works
    secret = os.getenv("JWT_SECRET_KEY", Config.JWT_SECRET_KEY)
    expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    token  = jwt.encode(
        {
            "officer_id":  citizen["citizen_id"],
            "role_name":   "Citizen",
            "access_level": 0,
            "citizen_id":  citizen["citizen_id"],
            "exp":         expiry,
        },
        secret,
        algorithm="HS256"
    )

    logger.info(f"Citizen portal login: citizen_id={citizen['citizen_id']}")

    return jsonify({
        "token": token,
        "citizen": {
            "citizen_id":          citizen["citizen_id"],
            "first_name":          citizen["first_name"],
            "last_name":           citizen["last_name"],
            "national_id_number":  citizen["national_id_number"],
            "status":              citizen["status"],
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
