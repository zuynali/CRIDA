"""
middleware/auth.py — JWT Authentication Decorator
==================================================
@token_required validates the Bearer JWT on every protected route.
On success it injects g.officer (dict) with officer profile + role.

Usage:
    from middleware.auth import token_required

    @my_bp.route("/protected")
    @token_required
    def my_view():
        # g.officer is now available
        return jsonify(g.officer)
"""

import jwt
from functools import wraps
from flask import request, jsonify, g

from config import Config
from db import execute_query


def token_required(f):
    """Decorator: validates JWT Bearer token and injects g.officer."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth = request.headers.get("Authorization", "")

        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]

        if not token:
            return jsonify({"error": "Missing token"}), 401

        try:
            payload = jwt.decode(
                token, Config.JWT_SECRET_KEY, algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        # Fetch live officer record (catches deactivated accounts)
        officer = execute_query(
            """SELECT o.officer_id, o.full_name, o.email,
                      r.role_name, r.access_level, o.office_id, o.is_active
               FROM Officer o
               JOIN Role r ON o.role_id = r.role_id
               WHERE o.officer_id = %s AND o.is_active = 1""",
            (payload["officer_id"],), fetch='one'
        )

        if not officer:
            return jsonify({"error": "Officer not found or inactive"}), 401

        g.officer = officer
        return f(*args, **kwargs)

    return decorated
