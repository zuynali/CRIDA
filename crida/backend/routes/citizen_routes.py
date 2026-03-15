import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required
from utils.validators import validate_national_id, require_fields

logger = logging.getLogger(__name__)
citizen_bp = Blueprint("citizens", __name__)


@citizen_bp.route("/", methods=["GET"])
@token_required
def list_citizens():
    page = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit
    search = request.args.get("search", "").strip()
    if search:
        like = f"%{search}%"
        rows = execute_query(
            """SELECT citizen_id, national_id_number,
                      CONCAT(first_name,' ',last_name) AS full_name,
                      dob, gender, marital_status, blood_group, status
               FROM Citizen
               WHERE first_name LIKE %s OR last_name LIKE %s
                  OR national_id_number LIKE %s
               ORDER BY citizen_id LIMIT %s OFFSET %s""",
            (like, like, like, limit, offset), fetch='all')
    else:
        rows = execute_query(
            """SELECT citizen_id, national_id_number,
                      CONCAT(first_name,' ',last_name) AS full_name,
                      dob, gender, marital_status, blood_group, status
               FROM Citizen ORDER BY citizen_id LIMIT %s OFFSET %s""",
            (limit, offset), fetch='all')
    total = execute_query("SELECT COUNT(*) AS cnt FROM Citizen", fetch='one')
    return jsonify({
        "citizens": rows or [],
        "total": total["cnt"],
        "page": page,
        "limit": limit
    }), 200


@citizen_bp.route("/<int:cid>", methods=["GET"])
@token_required
def get_citizen(cid):
    row = execute_query(
        "SELECT * FROM CitizenProfile_View WHERE citizen_id = %s", (cid,), fetch='one'
    )
    if not row:
        return jsonify({"error": "Citizen not found"}), 404
    return jsonify({"citizen": row}), 200


@citizen_bp.route("/", methods=["POST"])
@token_required
@permission_required("manage_citizens")
def create_citizen():
    data = request.json or {}
    ok, err = require_fields(data, "national_id_number", "first_name", "last_name",
                             "dob", "gender")
    if not ok:
        return jsonify({"error": err}), 400
    if not validate_national_id(data["national_id_number"]):
        return jsonify({"error": "national_id_number must be exactly 13 digits"}), 400

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO Citizen
               (national_id_number, first_name, last_name, dob, gender,
                marital_status, blood_group, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (data["national_id_number"], data["first_name"], data["last_name"],
             data["dob"], data["gender"],
             data.get("marital_status", "Single"),
             data.get("blood_group"),
             data.get("status", "active")))
        new_cid = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, new_values, ip_address)
               VALUES (%s, 'INSERT', 'Citizen', %s, %s, %s)""",
            (g.officer["officer_id"], new_cid, str(data), request.remote_addr))
        return new_cid

    new_id = execute_transaction_custom(ops)
    return jsonify({"message": "Citizen created", "citizen_id": new_id}), 201


@citizen_bp.route("/<int:cid>", methods=["PUT"])
@token_required
@permission_required("manage_citizens")
def update_citizen(cid):
    data = request.json or {}
    allowed = ["first_name", "last_name", "dob", "gender",
               "marital_status", "blood_group", "status"]
    sets = [f"{k} = %s" for k in data if k in allowed]
    if not sets:
        return jsonify({"error": "No updatable fields provided"}), 400
    vals = [data[k] for k in data if k in allowed]
    vals.append(cid)

    def ops(conn, cursor):
        cursor.execute(
            f"UPDATE Citizen SET {', '.join(sets)} WHERE citizen_id = %s", vals)
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'Citizen', %s, %s)""",
            (g.officer["officer_id"], cid, request.remote_addr))
        return cursor.rowcount

    execute_transaction_custom(ops)
    return jsonify({"message": "Citizen updated"}), 200


@citizen_bp.route("/<int:cid>", methods=["DELETE"])
@token_required
@permission_required("manage_citizens")
def delete_citizen(cid):
    existing = execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s", (cid,), fetch='one')
    if not existing:
        return jsonify({"error": "Citizen not found"}), 404

    def ops(conn, cursor):
        # 'blacklisted' is the correct ENUM value for deactivation
        # ENUM('active','deceased','blacklisted') — 'inactive' does not exist
        cursor.execute(
            "UPDATE Citizen SET status = 'blacklisted' WHERE citizen_id = %s", (cid,))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'DELETE', 'Citizen', %s, %s)""",
            (g.officer["officer_id"], cid, request.remote_addr))
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "Citizen blacklisted"}), 200