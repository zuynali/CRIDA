import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import role_required
from utils.validators import require_fields

logger = logging.getLogger(__name__)
complaint_bp = Blueprint("complaints", __name__)

# Schema reference:
# Complaint: complaint_id, citizen_id, subject, description,
#            status (Open/In Progress/Resolved/Closed),
#            assigned_to, resolution, created_at, updated_at


@complaint_bp.route("/", methods=["GET"])
@token_required
def list_complaints():
    status = request.args.get("status")
    cid = request.args.get("citizen_id")
    sql = """SELECT comp.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
             FROM Complaint comp
             JOIN Citizen c ON comp.citizen_id = c.citizen_id
             WHERE 1=1"""
    params = []
    if cid:
        sql += " AND comp.citizen_id = %s"
        params.append(cid)
    if status:
        sql += " AND comp.status = %s"
        params.append(status)
    sql += " ORDER BY comp.created_at DESC LIMIT 50"
    rows = execute_query(sql, params or None, fetch='all')
    return jsonify({"complaints": rows or []}), 200


@complaint_bp.route("/<int:cid>", methods=["GET"])
@token_required
def get_complaint(cid):
    row = execute_query(
        """SELECT comp.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Complaint comp
           JOIN Citizen c ON comp.citizen_id = c.citizen_id
           WHERE comp.complaint_id = %s""",
        (cid,), fetch='one')
    if not row:
        return jsonify({"error": "Complaint not found"}), 404
    return jsonify({"complaint": row}), 200


@complaint_bp.route("/", methods=["POST"])
@token_required
def submit_complaint():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "subject", "description")
    if not ok:
        return jsonify({"error": err}), 400

    citizen = execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    cid = execute_query(
        """INSERT INTO Complaint (citizen_id, subject, description, status)
           VALUES (%s, %s, %s, 'Open')""",
        (data["citizen_id"], data["subject"], data["description"]))
    return jsonify({"message": "Complaint submitted", "complaint_id": cid}), 201


@complaint_bp.route("/<int:cid>/assign", methods=["PUT"])
@token_required
@role_required("Admin", "Registrar")
def assign_complaint(cid):
    data = request.json or {}
    ok, err = require_fields(data, "officer_id")
    if not ok:
        return jsonify({"error": err}), 400

    complaint = execute_query(
        "SELECT complaint_id FROM Complaint WHERE complaint_id = %s", (cid,), fetch='one')
    if not complaint:
        return jsonify({"error": "Complaint not found"}), 404

    execute_query(
        """UPDATE Complaint
           SET assigned_to = %s, status = 'In Progress'
           WHERE complaint_id = %s""",
        (data["officer_id"], cid))

    # Notify citizen
    try:
        comp = execute_query(
            "SELECT citizen_id FROM Complaint WHERE complaint_id = %s", (cid,), fetch='one')
        from utils.notifications import send_notification
        send_notification(
            citizen_id=comp["citizen_id"],
            title="Complaint Update",
            message=f"Your complaint (ID: {cid}) has been assigned and is now In Progress.",
            notif_type="info", category="system")
    except Exception:
        pass

    return jsonify({"message": "Complaint assigned"}), 200


@complaint_bp.route("/<int:cid>/resolve", methods=["PUT"])
@token_required
def resolve_complaint(cid):
    data = request.json or {}
    ok, err = require_fields(data, "resolution")
    if not ok:
        return jsonify({"error": err}), 400

    complaint = execute_query(
        "SELECT * FROM Complaint WHERE complaint_id = %s", (cid,), fetch='one')
    if not complaint:
        return jsonify({"error": "Complaint not found"}), 404

    execute_query(
        """UPDATE Complaint
           SET status = 'Resolved', resolution = %s
           WHERE complaint_id = %s""",
        (data["resolution"], cid))

    # Notify citizen
    try:
        from utils.notifications import send_notification
        send_notification(
            citizen_id=complaint["citizen_id"],
            title="Complaint Resolved",
            message=f"Your complaint (ID: {cid}) has been resolved. Resolution: {data['resolution']}",
            notif_type="success", category="system")
    except Exception:
        pass

    return jsonify({"message": "Complaint resolved"}), 200


@complaint_bp.route("/<int:cid>/close", methods=["PUT"])
@token_required
@role_required("Admin")
def close_complaint(cid):
    complaint = execute_query(
        "SELECT complaint_id FROM Complaint WHERE complaint_id = %s", (cid,), fetch='one')
    if not complaint:
        return jsonify({"error": "Complaint not found"}), 404
    execute_query(
        "UPDATE Complaint SET status = 'Closed' WHERE complaint_id = %s", (cid,))
    return jsonify({"message": "Complaint closed"}), 200
