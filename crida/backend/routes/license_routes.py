"""
routes/license_routes.py — Driving License Application & Issuance
==================================================================
GET  /              — list DL applications (paginated)
GET  /<id>          — get single application
POST /              — submit application (ACID)
PUT  /<id>/approve  — approve (ACID)
PUT  /<id>/reject   — reject (ACID)
POST /<id>/issue    — issue license (ACID: insert Driving_License)
"""

import datetime
import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required, role_required

logger     = logging.getLogger(__name__)
license_bp = Blueprint("licenses", __name__)


@license_bp.route("/", methods=["GET"])
@token_required
def list_licenses():
    page   = int(request.args.get("page", 1))
    limit  = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit
    rows   = execute_query(
        """SELECT da.dl_app_id, da.citizen_id,
                  CONCAT(c.first_name,' ',c.last_name) AS citizen_name,
                  da.license_type, da.status, da.fee_paid,
                  da.submitted_at, da.office_id
           FROM DL_Application da
           JOIN Citizen c ON da.citizen_id = c.citizen_id
           ORDER BY da.dl_app_id DESC LIMIT %s OFFSET %s""",
        (limit, offset), fetch='all'
    )
    total = execute_query(
        "SELECT COUNT(*) AS cnt FROM DL_Application", fetch='one'
    )
    return jsonify({"applications": rows or [], "total": total["cnt"],
                    "page": page, "limit": limit}), 200


@license_bp.route("/<int:app_id>", methods=["GET"])
@token_required
def get_license_app(app_id):
    row = execute_query(
        """SELECT da.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM DL_Application da
           JOIN Citizen c ON da.citizen_id = c.citizen_id
           WHERE da.dl_app_id = %s""",
        (app_id,), fetch='one'
    )
    if not row:
        return jsonify({"error": "Application not found"}), 404
    return jsonify({"application": row}), 200


@license_bp.route("/", methods=["POST"])
@token_required
@permission_required("manage_license")
def submit_license():
    data = request.json or {}
    if not data.get("citizen_id") or not data.get("license_type"):
        return jsonify({"error": "citizen_id and license_type are required"}), 400

    if not execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s AND status='active'",
        (data["citizen_id"],), fetch='one'
    ):
        return jsonify({"error": "Active citizen not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO DL_Application
                   (citizen_id, license_type, status, fee_paid, office_id)
               VALUES (%s, %s, 'Pending', 0, %s)""",
            (data["citizen_id"], data["license_type"],
             data.get("office_id", g.officer["office_id"]))
        )
        aid = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'INSERT','DL_Application',%s,%s)""",
            (g.officer["officer_id"], aid, request.remote_addr or "unknown")
        )
        return aid

    new_id = execute_transaction_custom(ops)
    return jsonify({"message": "License application submitted",
                    "dl_app_id": new_id}), 201


@license_bp.route("/<int:app_id>/approve", methods=["PUT"])
@token_required
@role_required("Admin", "License_Officer")
def approve_license(app_id):
    app = execute_query(
        "SELECT * FROM DL_Application WHERE dl_app_id = %s",
        (app_id,), fetch='one'
    )
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] != "Pending":
        return jsonify({"error": f"Cannot approve — status is '{app['status']}'"}), 400

    def ops(conn, cursor):
        cursor.execute(
            """UPDATE DL_Application
               SET status='Approved', processed_by=%s, processed_at=NOW()
               WHERE dl_app_id=%s""",
            (g.officer["officer_id"], app_id)
        )
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'UPDATE','DL_Application',%s,%s)""",
            (g.officer["officer_id"], app_id, request.remote_addr or "unknown")
        )
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "License application approved"}), 200


@license_bp.route("/<int:app_id>/reject", methods=["PUT"])
@token_required
@role_required("Admin", "License_Officer")
def reject_license(app_id):
    data = request.json or {}
    if not data.get("rejection_reason"):
        return jsonify({"error": "rejection_reason is required"}), 400

    app = execute_query(
        "SELECT status FROM DL_Application WHERE dl_app_id = %s",
        (app_id,), fetch='one'
    )
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] != "Pending":
        return jsonify({"error": f"Cannot reject — status is '{app['status']}'"}), 400

    def ops(conn, cursor):
        cursor.execute(
            """UPDATE DL_Application
               SET status='Rejected', processed_by=%s,
                   processed_at=NOW(), rejection_reason=%s
               WHERE dl_app_id=%s""",
            (g.officer["officer_id"], data["rejection_reason"], app_id)
        )
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'UPDATE','DL_Application',%s,%s)""",
            (g.officer["officer_id"], app_id, request.remote_addr or "unknown")
        )
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "License application rejected"}), 200


@license_bp.route("/<int:app_id>/issue", methods=["POST"])
@token_required
@role_required("Admin", "License_Officer")
def issue_license(app_id):
    """
    ACID: Verify Approved+fee_paid → Insert Driving_License → Audit_Log
    All steps succeed or all rollback.
    """
    def ops(conn, cursor):
        cursor.execute(
            """SELECT * FROM DL_Application
               WHERE dl_app_id = %s AND status='Approved' AND fee_paid=1""",
            (app_id,)
        )
        app = cursor.fetchone()
        if not app:
            raise ValueError("Application not approved or fee not paid")

        today  = datetime.date.today()
        expiry = datetime.date(today.year + 5, today.month, today.day)
        cursor.execute(
            """INSERT INTO Driving_License
                   (citizen_id, license_number, license_class,
                    issue_date, expiry_date, status)
               VALUES (%s, %s, %s, %s, %s, 'Valid')""",
            (app["citizen_id"],
             f"DL{app_id:07d}",
             app.get("license_type", "B"),
             today, expiry)
        )
        lic_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'INSERT','Driving_License',%s,%s)""",
            (g.officer["officer_id"], lic_id, request.remote_addr or "unknown")
        )
        return lic_id

    try:
        lid = execute_transaction_custom(ops)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Driving license issued", "license_id": lid}), 201
