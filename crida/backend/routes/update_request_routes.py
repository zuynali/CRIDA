import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import role_required
from utils.validators import require_fields

logger = logging.getLogger(__name__)
update_bp = Blueprint("updates", __name__)

# Schema reference:
# Update_Request: request_id, citizen_id, field_name, old_value, new_value, reason,
#                 status (Pending/Approved/Rejected), reviewed_by, reviewed_at,
#                 rejection_reason, created_at

ALLOWED_UPDATABLE_FIELDS = [
    "first_name", "last_name", "dob", "gender", "marital_status", "blood_group"
]


@update_bp.route("/", methods=["GET"])
@token_required
def list_update_requests():
    cid = request.args.get("citizen_id")
    status = request.args.get("status")
    sql = """SELECT ur.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
             FROM Update_Request ur
             JOIN Citizen c ON ur.citizen_id = c.citizen_id
             WHERE 1=1"""
    params = []
    if cid:
        sql += " AND ur.citizen_id = %s"
        params.append(cid)
    if status:
        sql += " AND ur.status = %s"
        params.append(status)
    sql += " ORDER BY ur.created_at DESC"
    rows = execute_query(sql, params or None, fetch='all')
    return jsonify({"requests": rows or []}), 200


@update_bp.route("/<int:rid>", methods=["GET"])
@token_required
def get_update_request(rid):
    row = execute_query(
        """SELECT ur.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Update_Request ur
           JOIN Citizen c ON ur.citizen_id = c.citizen_id
           WHERE ur.request_id = %s""",
        (rid,), fetch='one')
    if not row:
        return jsonify({"error": "Request not found"}), 404
    return jsonify({"request": row}), 200


@update_bp.route("/", methods=["POST"])
@token_required
def submit_update_request():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "field_name", "new_value")
    if not ok:
        return jsonify({"error": err}), 400
    if data["field_name"] not in ALLOWED_UPDATABLE_FIELDS:
        return jsonify({"error": f"Field '{data['field_name']}' is not updatable. Allowed: {ALLOWED_UPDATABLE_FIELDS}"}), 400

    citizen = execute_query(
        f"SELECT {data['field_name']} AS curr FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    rid = execute_query(
        """INSERT INTO Update_Request
           (citizen_id, field_name, old_value, new_value, reason, status)
           VALUES (%s, %s, %s, %s, %s, 'Pending')""",
        (data["citizen_id"], data["field_name"],
         citizen["curr"], data["new_value"],
         data.get("reason", "")))
    return jsonify({"message": "Update request submitted", "request_id": rid}), 201


@update_bp.route("/<int:rid>/approve", methods=["PUT"])
@token_required
@role_required("Admin", "Registrar")
def approve_request(rid):
    req = execute_query(
        "SELECT * FROM Update_Request WHERE request_id = %s AND status = 'Pending'",
        (rid,), fetch='one')
    if not req:
        return jsonify({"error": "Request not found or already processed"}), 404

    def ops(conn, cursor):
        # ACID: update citizen + mark approved + audit — all or nothing
        cursor.execute(
            f"UPDATE Citizen SET {req['field_name']} = %s WHERE citizen_id = %s",
            (req["new_value"], req["citizen_id"]))
        cursor.execute(
            """UPDATE Update_Request
               SET status = 'Approved', reviewed_by = %s, reviewed_at = NOW()
               WHERE request_id = %s""",
            (g.officer["officer_id"], rid))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'Citizen', %s, %s)""",
            (g.officer["officer_id"], req["citizen_id"], request.remote_addr))
        return True

    execute_transaction_custom(ops)

    # Post-commit notification
    try:
        from utils.notifications import send_notification
        send_notification(
            citizen_id=req["citizen_id"],
            title="Update Request Approved",
            message=f"Your request to update '{req['field_name']}' to '{req['new_value']}' has been approved.",
            notif_type="success", category="transaction")
    except Exception:
        pass

    return jsonify({"message": "Request approved and citizen updated"}), 200


@update_bp.route("/<int:rid>/reject", methods=["PUT"])
@token_required
@role_required("Admin", "Registrar")
def reject_request(rid):
    data = request.json or {}
    req = execute_query(
        "SELECT * FROM Update_Request WHERE request_id = %s AND status = 'Pending'",
        (rid,), fetch='one')
    if not req:
        return jsonify({"error": "Request not found or already processed"}), 404

    execute_query(
        """UPDATE Update_Request
           SET status = 'Rejected', reviewed_by = %s,
               reviewed_at = NOW(), rejection_reason = %s
           WHERE request_id = %s""",
        (g.officer["officer_id"], data.get("reason", "Rejected by officer"), rid))

    try:
        from utils.notifications import send_notification
        send_notification(
            citizen_id=req["citizen_id"],
            title="Update Request Rejected",
            message=f"Your update request for '{req['field_name']}' was rejected. Reason: {data.get('reason', 'No reason given')}",
            notif_type="warning", category="transaction")
    except Exception:
        pass

    return jsonify({"message": "Request rejected"}), 200
