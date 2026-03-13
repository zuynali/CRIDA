from flask import Blueprint, request, jsonify, g
from db import execute_query
from middleware.auth import token_required
from middleware.rbac import role_required

audit_bp = Blueprint("audit", __name__)

# Schema reference:
# Audit_Log: log_id, officer_id, action_type, table_name, record_id,
#            old_values, new_values, ip_address, timestamp


@audit_bp.route("/", methods=["GET"])
@token_required
@role_required("Admin", "Security_Officer")
def list_audit_logs():
    page = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = (page - 1) * limit

    officer_id = request.args.get("officer_id")
    table_name = request.args.get("table_name")
    action_type = request.args.get("action_type")

    sql = """SELECT al.*, o.full_name AS officer_name
             FROM Audit_Log al
             JOIN Officer o ON al.officer_id = o.officer_id
             WHERE 1=1"""
    params = []

    if officer_id:
        sql += " AND al.officer_id = %s"
        params.append(officer_id)
    if table_name:
        sql += " AND al.table_name = %s"
        params.append(table_name)
    if action_type:
        sql += " AND al.action_type = %s"
        params.append(action_type)

    sql += " ORDER BY al.timestamp DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    rows = execute_query(sql, params, fetch='all')
    total = execute_query("SELECT COUNT(*) AS cnt FROM Audit_Log", fetch='one')

    return jsonify({
        "logs": rows or [],
        "total": total["cnt"],
        "page": page,
        "limit": limit
    }), 200


@audit_bp.route("/<int:lid>", methods=["GET"])
@token_required
@role_required("Admin", "Security_Officer")
def get_audit_log(lid):
    row = execute_query(
        """SELECT al.*, o.full_name AS officer_name
           FROM Audit_Log al
           JOIN Officer o ON al.officer_id = o.officer_id
           WHERE al.log_id = %s""",
        (lid,), fetch='one')
    if not row:
        return jsonify({"error": "Log entry not found"}), 404
    return jsonify({"log": row}), 200
