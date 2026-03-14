import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required, role_required
from utils.validators import require_fields

logger = logging.getLogger(__name__)
cnic_bp = Blueprint("cnic", __name__)

# Schema reference:
# CNIC_Application: application_id, citizen_id, application_type, submission_date,
#                   status (Pending/Under Review/Approved/Rejected), office_id, rejection_reason
# NOTE: NO fee_paid column on CNIC_Application



@cnic_bp.route("/", methods=["GET"])
@token_required
def list_cnic_applications():
    page = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit
    citizen_id = request.args.get("citizen_id")
    if citizen_id:
        rows = execute_query(
            """SELECT ca.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM CNIC_Application ca
               JOIN Citizen c ON ca.citizen_id = c.citizen_id
               WHERE ca.citizen_id = %s
               ORDER BY ca.submission_date DESC LIMIT %s OFFSET %s""",
            (citizen_id, limit, offset), fetch='all')
    else:
        rows = execute_query(
            """SELECT ca.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM CNIC_Application ca
               JOIN Citizen c ON ca.citizen_id = c.citizen_id
               ORDER BY ca.submission_date DESC LIMIT %s OFFSET %s""",
            (limit, offset), fetch='all')
    return jsonify({"applications": rows or [], "page": page, "limit": limit}), 200


@cnic_bp.route("/<int:app_id>", methods=["GET"])
@token_required
def get_cnic_application(app_id):
    row = execute_query(
        """SELECT ca.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM CNIC_Application ca
           JOIN Citizen c ON ca.citizen_id = c.citizen_id
           WHERE ca.application_id = %s""",
        (app_id,), fetch='one')
    if not row:
        return jsonify({"error": "Application not found"}), 404
    return jsonify({"application": row}), 200


@cnic_bp.route("/", methods=["POST"])
@token_required
@permission_required("manage_cnic")
def submit_cnic():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "application_type", "office_id")
    if not ok:
        return jsonify({"error": err}), 400

    valid_types = ('New', 'Renewal', 'Replacement')
    if data["application_type"] not in valid_types:
        return jsonify({"error": f"application_type must be one of {valid_types}"}), 400

    citizen = execute_query(
        "SELECT citizen_id, status FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO CNIC_Application
               (citizen_id, application_type, status, office_id)
               VALUES (%s, %s, 'Pending', %s)""",
            (data["citizen_id"], data["application_type"], data["office_id"]))
        app_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, new_values, ip_address)
               VALUES (%s, 'INSERT', 'CNIC_Application', %s, %s, %s)""",
            (g.officer["officer_id"], app_id,
             f"citizen_id={data['citizen_id']}, type={data['application_type']}",
             request.remote_addr))
        return app_id

    new_id = execute_transaction_custom(ops)
    return jsonify({"message": "CNIC application submitted", "application_id": new_id}), 201


@cnic_bp.route("/<int:app_id>/approve", methods=["PUT"])
@token_required
@permission_required("manage_cnic")
def approve_cnic(app_id):
    app = execute_query(
        "SELECT * FROM CNIC_Application WHERE application_id = %s", (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] not in ("Pending", "Under Review"):
        return jsonify({"error": f"Cannot approve application with status '{app['status']}'"}), 400

    def ops(conn, cursor):
        # Trigger create_cnic_card_on_approval fires automatically on status=Approved
        cursor.execute(
            "UPDATE CNIC_Application SET status = 'Approved' WHERE application_id = %s",
            (app_id,))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'CNIC_Application', %s, %s)""",
            (g.officer["officer_id"], app_id, request.remote_addr))
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "CNIC application approved. CNIC card created by trigger."}), 200


@cnic_bp.route("/<int:app_id>/reject", methods=["PUT"])
@token_required
@permission_required("manage_cnic")
def reject_cnic(app_id):
    data = request.json or {}
    app = execute_query(
        "SELECT * FROM CNIC_Application WHERE application_id = %s", (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            """UPDATE CNIC_Application
               SET status = 'Rejected', rejection_reason = %s
               WHERE application_id = %s""",
            (data.get("reason", "Rejected by officer"), app_id))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'CNIC_Application', %s, %s)""",
            (g.officer["officer_id"], app_id, request.remote_addr))
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "CNIC application rejected"}), 200
