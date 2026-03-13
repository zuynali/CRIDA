"""
routes/passport_routes.py — Passport Application & Issuance
============================================================
GET  /              — list applications (paginated)
GET  /<id>          — get single application
POST /              — submit application (ACID)
PUT  /<id>/approve  — approve (ACID)
PUT  /<id>/reject   — reject with reason (ACID)
POST /<id>/issue    — issue passport (ACID: verify fee+approval, insert Passport)

ACID pattern for issue: same multi-step transaction as guide section 3.2
"""

import datetime
import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required, role_required

logger      = logging.getLogger(__name__)
passport_bp = Blueprint("passports", __name__)


@passport_bp.route("/", methods=["GET"])
@token_required
def list_passports():
    page   = int(request.args.get("page", 1))
    limit  = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit
    rows   = execute_query(
        """SELECT pa.passport_app_id, pa.citizen_id,
                  CONCAT(c.first_name,' ',c.last_name) AS citizen_name,
                  pa.application_type, pa.status, pa.fee_paid,
                  pa.submitted_at, pa.office_id
           FROM Passport_Application pa
           JOIN Citizen c ON pa.citizen_id = c.citizen_id
           ORDER BY pa.passport_app_id DESC LIMIT %s OFFSET %s""",
        (limit, offset), fetch='all'
    )
    total = execute_query(
        "SELECT COUNT(*) AS cnt FROM Passport_Application", fetch='one'
    )
    return jsonify({"applications": rows or [], "total": total["cnt"],
                    "page": page, "limit": limit}), 200


@passport_bp.route("/<int:app_id>", methods=["GET"])
@token_required
def get_passport_app(app_id):
    row = execute_query(
        """SELECT pa.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Passport_Application pa
           JOIN Citizen c ON pa.citizen_id = c.citizen_id
           WHERE pa.passport_app_id = %s""",
        (app_id,), fetch='one'
    )
    if not row:
        return jsonify({"error": "Application not found"}), 404
    return jsonify({"application": row}), 200


@passport_bp.route("/", methods=["POST"])
@token_required
@permission_required("manage_passport")
def submit_passport():
    data = request.json or {}
    if not data.get("citizen_id") or not data.get("application_type"):
        return jsonify({"error": "citizen_id and application_type are required"}), 400

    if not execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s AND status='active'",
        (data["citizen_id"],), fetch='one'
    ):
        return jsonify({"error": "Active citizen not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO Passport_Application
                   (citizen_id, application_type, status, fee_paid, office_id)
               VALUES (%s, %s, 'Pending', 0, %s)""",
            (data["citizen_id"], data["application_type"],
             data.get("office_id", g.officer["office_id"]))
        )
        aid = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'INSERT','Passport_Application',%s,%s)""",
            (g.officer["officer_id"], aid, request.remote_addr or "unknown")
        )
        return aid

    new_id = execute_transaction_custom(ops)
    return jsonify({"message": "Passport application submitted",
                    "passport_app_id": new_id}), 201


@passport_bp.route("/<int:app_id>/approve", methods=["PUT"])
@token_required
@role_required("Admin", "Passport_Officer")
def approve_passport(app_id):
    app = execute_query(
        "SELECT * FROM Passport_Application WHERE passport_app_id = %s",
        (app_id,), fetch='one'
    )
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] != "Pending":
        return jsonify({"error": f"Cannot approve — status is '{app['status']}'"}), 400

    def ops(conn, cursor):
        cursor.execute(
            """UPDATE Passport_Application
               SET status='Approved', processed_by=%s, processed_at=NOW()
               WHERE passport_app_id=%s""",
            (g.officer["officer_id"], app_id)
        )
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'UPDATE','Passport_Application',%s,%s)""",
            (g.officer["officer_id"], app_id, request.remote_addr or "unknown")
        )
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "Passport application approved"}), 200


@passport_bp.route("/<int:app_id>/reject", methods=["PUT"])
@token_required
@role_required("Admin", "Passport_Officer")
def reject_passport(app_id):
    data = request.json or {}
    if not data.get("rejection_reason"):
        return jsonify({"error": "rejection_reason is required"}), 400

    app = execute_query(
        "SELECT status FROM Passport_Application WHERE passport_app_id = %s",
        (app_id,), fetch='one'
    )
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] != "Pending":
        return jsonify({"error": f"Cannot reject — status is '{app['status']}'"}), 400

    def ops(conn, cursor):
        cursor.execute(
            """UPDATE Passport_Application
               SET status='Rejected', processed_by=%s,
                   processed_at=NOW(), rejection_reason=%s
               WHERE passport_app_id=%s""",
            (g.officer["officer_id"], data["rejection_reason"], app_id)
        )
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'UPDATE','Passport_Application',%s,%s)""",
            (g.officer["officer_id"], app_id, request.remote_addr or "unknown")
        )
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "Passport application rejected"}), 200


@passport_bp.route("/<int:app_id>/issue", methods=["POST"])
@token_required
@role_required("Admin", "Passport_Officer")
def issue_passport(app_id):
    """
    ACID multi-step transaction (guide section 3.2 pattern):
      Step 1 — Verify application is Approved AND fee_paid=1
      Step 2 — Check citizen not on Watchlist
      Step 3 — Insert Passport record
      Step 4 — Insert Audit_Log
    All succeed or all rollback.
    """
    def ops(conn, cursor):
        # Step 1 — Verify approval and fee
        cursor.execute(
            """SELECT * FROM Passport_Application
               WHERE passport_app_id = %s AND status='Approved' AND fee_paid=1""",
            (app_id,)
        )
        app = cursor.fetchone()
        if not app:
            raise ValueError("Application not approved or fee not paid")

        # Step 2 — Watchlist check
        cursor.execute(
            "SELECT watchlist_id FROM Watchlist WHERE citizen_id = %s",
            (app["citizen_id"],)
        )
        if cursor.fetchone():
            raise ValueError("Cannot issue passport to watchlisted citizen")

        # Step 3 — Insert Passport
        today   = datetime.date.today()
        expiry  = datetime.date(today.year + 10, today.month, today.day)
        cursor.execute(
            """INSERT INTO Passport
                   (citizen_id, passport_number, issue_date, expiry_date)
               VALUES (%s, %s, %s, %s)""",
            (app["citizen_id"], f"PK{app_id:06d}", today, expiry)
        )
        passport_id = cursor.lastrowid

        # Step 4 — Audit
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'INSERT','Passport',%s,%s)""",
            (g.officer["officer_id"], passport_id, request.remote_addr or "unknown")
        )
        return passport_id

    try:
        pid = execute_transaction_custom(ops)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Passport issued", "passport_id": pid}), 201
