import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required
from utils.validators import require_fields

logger = logging.getLogger(__name__)
security_bp = Blueprint("security", __name__)

# Schema reference:
# Criminal_Record: record_id, citizen_id, case_number, offense, offense_date,
#                  conviction_date, sentence, status, court_name
# Watchlist: watchlist_id, citizen_id, reason, added_date (DEFAULT), added_by (NOT NULL),
#            watchlist_type ENUM('Security','Fraud','Immigration','Court Order') NOT NULL,
#            expiry_date NULL


@security_bp.route("/criminal-records", methods=["GET"])
@token_required
def list_criminal_records():
    cid = request.args.get("citizen_id")
    if cid:
        rows = execute_query(
            """SELECT cr.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM Criminal_Record cr
               JOIN Citizen c ON cr.citizen_id = c.citizen_id
               WHERE cr.citizen_id = %s ORDER BY cr.offense_date DESC""",
            (cid,), fetch='all')
    else:
        rows = execute_query(
            """SELECT cr.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM Criminal_Record cr
               JOIN Citizen c ON cr.citizen_id = c.citizen_id
               ORDER BY cr.offense_date DESC LIMIT 50""",
            fetch='all')
    return jsonify({"records": rows or []}), 200


@security_bp.route("/criminal-records/<int:rid>", methods=["GET"])
@token_required
def get_criminal_record(rid):
    row = execute_query(
        """SELECT cr.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Criminal_Record cr
           JOIN Citizen c ON cr.citizen_id = c.citizen_id
           WHERE cr.record_id = %s""",
        (rid,), fetch='one')
    if not row:
        return jsonify({"error": "Record not found"}), 404
    return jsonify({"record": row}), 200


@security_bp.route("/criminal-records", methods=["POST"])
@token_required
@permission_required("manage_security")
def add_criminal_record():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "offense", "offense_date", "status")
    if not ok:
        return jsonify({"error": err}), 400

    valid_statuses = ('Charged', 'On Trial', 'Convicted', 'Acquitted')
    if data["status"] not in valid_statuses:
        return jsonify({"error": f"status must be one of {valid_statuses}"}), 400

    citizen = execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO Criminal_Record
               (citizen_id, case_number, offense, offense_date,
                conviction_date, sentence, status, court_name)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (data["citizen_id"], data.get("case_number"),
             data["offense"], data["offense_date"],
             data.get("conviction_date"), data.get("sentence"),
             data["status"], data.get("court_name")))
        rid = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'INSERT', 'Criminal_Record', %s, %s)""",
            (g.officer["officer_id"], rid, request.remote_addr))
        return rid

    rid = execute_transaction_custom(ops)
    return jsonify({"message": "Criminal record added", "record_id": rid}), 201


@security_bp.route("/criminal-records/<int:rid>", methods=["PUT"])
@token_required
@permission_required("manage_security")
def update_criminal_record(rid):
    data = request.json or {}
    allowed = ["status", "conviction_date", "sentence", "court_name"]
    sets = [f"{k} = %s" for k in data if k in allowed]
    if not sets:
        return jsonify({"error": "No updatable fields provided"}), 400
    vals = [data[k] for k in data if k in allowed]
    vals.append(rid)
    execute_query(
        f"UPDATE Criminal_Record SET {', '.join(sets)} WHERE record_id = %s", vals)
    return jsonify({"message": "Record updated"}), 200


@security_bp.route("/watchlist", methods=["GET"])
@token_required
@permission_required("manage_security")
def get_watchlist():
    rows = execute_query(
        """SELECT w.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Watchlist w
           JOIN Citizen c ON w.citizen_id = c.citizen_id
           ORDER BY w.added_date DESC""",
        fetch='all')
    return jsonify({"watchlist": rows or []}), 200


@security_bp.route("/watchlist", methods=["POST"])
@token_required
@permission_required("manage_security")
def add_to_watchlist():
    data = request.json or {}
    # watchlist_type is NOT NULL with no default — must be supplied
    ok, err = require_fields(data, "citizen_id", "reason", "watchlist_type")
    if not ok:
        return jsonify({"error": err}), 400

    valid_types = ('Security', 'Fraud', 'Immigration', 'Court Order')
    if data["watchlist_type"] not in valid_types:
        return jsonify({"error": f"watchlist_type must be one of {valid_types}"}), 400

    citizen = execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    wid = execute_query(
        """INSERT INTO Watchlist
               (citizen_id, reason, added_by, watchlist_type, expiry_date)
           VALUES (%s, %s, %s, %s, %s)""",
        (data["citizen_id"], data["reason"], g.officer["officer_id"],
         data["watchlist_type"], data.get("expiry_date")))

    return jsonify({"message": "Added to watchlist", "watchlist_id": wid}), 201