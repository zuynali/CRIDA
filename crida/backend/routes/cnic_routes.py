"""
routes/cnic_routes.py — CNIC Application Lifecycle
===================================================
GET  /              — list all CNIC applications (paginated)
GET  /<id>          — get single application
POST /              — submit new application (ACID)
PUT  /<id>/approve  — approve application (ACID; trigger creates CNIC_Card)
PUT  /<id>/reject   — reject with reason (ACID)

NOTE: create_cnic_card_on_approval trigger fires on status='Approved'.
      Route does NOT insert CNIC_Card — trigger handles it.
      Route DOES wrap UPDATE in execute_transaction_custom for ACID.
"""

import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required, role_required

logger  = logging.getLogger(__name__)
cnic_bp = Blueprint("cnic", __name__)


@cnic_bp.route("/", methods=["GET"])
@token_required
def list_cnic():
    page   = int(request.args.get("page", 1))
    limit  = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit
    rows   = execute_query(
        """SELECT ca.cnic_app_id, ca.citizen_id,
                  CONCAT(c.first_name,' ',c.last_name) AS citizen_name,
                  ca.application_type, ca.status, ca.fee_paid,
                  ca.submitted_at, ca.office_id
           FROM CNIC_Application ca
           JOIN Citizen c ON ca.citizen_id = c.citizen_id
           ORDER BY ca.cnic_app_id DESC LIMIT %s OFFSET %s""",
        (limit, offset), fetch='all'
    )
    total = execute_query(
        "SELECT COUNT(*) AS cnt FROM CNIC_Application", fetch='one'
    )
    return jsonify({"applications": rows or [], "total": total["cnt"],
                    "page": page, "limit": limit}), 200


@cnic_bp.route("/<int:app_id>", methods=["GET"])
@token_required
def get_cnic(app_id):
    row = execute_query(
        """SELECT ca.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM CNIC_Application ca
           JOIN Citizen c ON ca.citizen_id = c.citizen_id
           WHERE ca.cnic_app_id = %s""",
        (app_id,), fetch='one'
    )
    if not row:
        return jsonify({"error": "Application not found"}), 404
    return jsonify({"application": row}), 200


@cnic_bp.route("/", methods=["POST"])
@token_required
@permission_required("manage_cnic")
def submit_cnic():
    data = request.json or {}
    if not data.get("citizen_id") or not data.get("application_type"):
        return jsonify({"error": "citizen_id and application_type are required"}), 400

    # Confirm citizen exists
    if not execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one'
    ):
        return jsonify({"error": "Citizen not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO CNIC_Application
                   (citizen_id, application_type, status, fee_paid, office_id)
               VALUES (%s, %s, 'Pending', 0, %s)""",
            (data["citizen_id"], data["application_type"],
             data.get("office_id", g.officer["office_id"]))
        )
        aid = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'INSERT','CNIC_Application',%s,%s)""",
            (g.officer["officer_id"], aid, request.remote_addr or "unknown")
        )
        return aid

    new_id = execute_transaction_custom(ops)
    return jsonify({"message": "CNIC application submitted",
                    "cnic_app_id": new_id}), 201


@cnic_bp.route("/<int:app_id>/approve", methods=["PUT"])
@token_required
@role_required("Admin", "Registrar")
def approve_cnic(app_id):
    """
    ACID: UPDATE CNIC_Application status='Approved' + Audit_Log.
    Trigger create_cnic_card_on_approval fires automatically.
    """
    app = execute_query(
        "SELECT * FROM CNIC_Application WHERE cnic_app_id = %s",
        (app_id,), fetch='one'
    )
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] != "Pending":
        return jsonify({"error": f"Cannot approve — status is '{app['status']}'"}), 400

    def ops(conn, cursor):
        cursor.execute(
            """UPDATE CNIC_Application
               SET status='Approved', processed_by=%s, processed_at=NOW()
               WHERE cnic_app_id=%s""",
            (g.officer["officer_id"], app_id)
        )
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'UPDATE','CNIC_Application',%s,%s)""",
            (g.officer["officer_id"], app_id, request.remote_addr or "unknown")
        )
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "CNIC application approved",
                    "note": "CNIC card created by trigger"}), 200


@cnic_bp.route("/<int:app_id>/reject", methods=["PUT"])
@token_required
@role_required("Admin", "Registrar")
def reject_cnic(app_id):
    data = request.json or {}
    if not data.get("rejection_reason"):
        return jsonify({"error": "rejection_reason is required"}), 400

    app = execute_query(
        "SELECT status FROM CNIC_Application WHERE cnic_app_id = %s",
        (app_id,), fetch='one'
    )
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] != "Pending":
        return jsonify({"error": f"Cannot reject — status is '{app['status']}'"}), 400

    def ops(conn, cursor):
        cursor.execute(
            """UPDATE CNIC_Application
               SET status='Rejected', processed_by=%s,
                   processed_at=NOW(), rejection_reason=%s
               WHERE cnic_app_id=%s""",
            (g.officer["officer_id"], data["rejection_reason"], app_id)
        )
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'UPDATE','CNIC_Application',%s,%s)""",
            (g.officer["officer_id"], app_id, request.remote_addr or "unknown")
        )
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "CNIC application rejected"}), 200
