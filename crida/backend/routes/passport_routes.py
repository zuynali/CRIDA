import datetime
import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required
from utils.validators import require_fields

logger = logging.getLogger(__name__)
passport_bp = Blueprint("passports", __name__)

# Schema reference:
# Passport_Application: passport_app_id, citizen_id, application_type, submission_date,
#                       status (Draft/Submitted/Under Review/Approved/Rejected/
#                               Ready for Collection/Collected),
#                       office_id, fee_paid (tinyint, default 0)
# Passport: passport_id, citizen_id, passport_number, issue_date, expiry_date, passport_status


@passport_bp.route("/", methods=["GET"])
@token_required
def list_passport_applications():
    page = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit
    citizen_id = request.args.get("citizen_id")
    if citizen_id:
        rows = execute_query(
            """SELECT pa.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM Passport_Application pa
               JOIN Citizen c ON pa.citizen_id = c.citizen_id
               WHERE pa.citizen_id = %s
               ORDER BY pa.submission_date DESC LIMIT %s OFFSET %s""",
            (citizen_id, limit, offset), fetch='all')
    else:
        rows = execute_query(
            """SELECT pa.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM Passport_Application pa
               JOIN Citizen c ON pa.citizen_id = c.citizen_id
               ORDER BY pa.submission_date DESC LIMIT %s OFFSET %s""",
            (limit, offset), fetch='all')
    return jsonify({"applications": rows or [], "page": page, "limit": limit}), 200


@passport_bp.route("/<int:app_id>", methods=["GET"])
@token_required
def get_passport_application(app_id):
    row = execute_query(
        """SELECT pa.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Passport_Application pa
           JOIN Citizen c ON pa.citizen_id = c.citizen_id
           WHERE pa.passport_app_id = %s""",
        (app_id,), fetch='one')
    if not row:
        return jsonify({"error": "Application not found"}), 404
    return jsonify({"application": row}), 200


@passport_bp.route("/", methods=["POST"])
@token_required
@permission_required("manage_passport")
def submit_passport():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "application_type", "office_id")
    if not ok:
        return jsonify({"error": err}), 400

    valid_types = ('New', 'Renewal', 'Lost Replacement')
    if data["application_type"] not in valid_types:
        return jsonify({"error": f"application_type must be one of {valid_types}"}), 400

    citizen = execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s", (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO Passport_Application
               (citizen_id, application_type, status, office_id, fee_paid)
               VALUES (%s, %s, 'Submitted', %s, 0)""",
            (data["citizen_id"], data["application_type"], data["office_id"]))
        app_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, new_values, ip_address)
               VALUES (%s, 'INSERT', 'Passport_Application', %s, %s, %s)""",
            (g.officer["officer_id"], app_id,
             f"citizen_id={data['citizen_id']}, type={data['application_type']}",
             request.remote_addr))
        return app_id

    new_id = execute_transaction_custom(ops)
    return jsonify({"message": "Passport application submitted", "passport_app_id": new_id}), 201


@passport_bp.route("/<int:app_id>/approve", methods=["PUT"])
@token_required
@permission_required("manage_passport")
def approve_passport(app_id):
    app = execute_query(
        "SELECT * FROM Passport_Application WHERE passport_app_id = %s", (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            "UPDATE Passport_Application SET status = 'Approved' WHERE passport_app_id = %s",
            (app_id,))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'Passport_Application', %s, %s)""",
            (g.officer["officer_id"], app_id, request.remote_addr))
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "Passport application approved"}), 200


@passport_bp.route("/<int:app_id>/reject", methods=["PUT"])
@token_required
@permission_required("manage_passport")
def reject_passport(app_id):
    data = request.json or {}
    app = execute_query(
        "SELECT * FROM Passport_Application WHERE passport_app_id = %s", (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            "UPDATE Passport_Application SET status = 'Rejected' WHERE passport_app_id = %s",
            (app_id,))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'Passport_Application', %s, %s)""",
            (g.officer["officer_id"], app_id, request.remote_addr))
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "Passport application rejected"}), 200


@passport_bp.route("/<int:app_id>/issue", methods=["POST"])
@token_required
@permission_required("manage_passport")
def issue_passport(app_id):
    """
    ACID Transaction Scenario (guide section 3.2):
    Step 1 — Verify application is Approved AND fee_paid = 1
    Step 2 — Check citizen not on Watchlist
    Step 3 — Insert Passport record
    Step 4 — Log to Audit_Log
    All 4 steps succeed or ALL rollback.
    """
    def ops(conn, cursor):
        # Step 1: verify approved + fee paid
        cursor.execute(
            """SELECT * FROM Passport_Application
               WHERE passport_app_id = %s AND status = 'Approved' AND fee_paid = 1""",
            (app_id,))
        app = cursor.fetchone()
        if not app:
            raise ValueError("Application not approved or fee not paid")

        citizen_id = app["citizen_id"]

        # Step 2: watchlist check
        cursor.execute(
            "SELECT watchlist_id FROM Watchlist WHERE citizen_id = %s", (citizen_id,))
        if cursor.fetchone():
            raise ValueError("Cannot issue passport to watchlisted citizen")

        # Step 3: insert Passport
        today = datetime.date.today()
        expiry = datetime.date(today.year + 10, today.month, today.day)
        cursor.execute(
            """INSERT INTO Passport
               (citizen_id, passport_number, issue_date, expiry_date)
               VALUES (%s, %s, %s, %s)""",
            (citizen_id, f"PK{app_id:06d}", today, expiry))
        passport_id = cursor.lastrowid

        # Step 4: audit log
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'INSERT', 'Passport', %s, %s)""",
            (g.officer["officer_id"], passport_id, request.remote_addr))

        # Update application status
        cursor.execute(
            "UPDATE Passport_Application SET status = 'Ready for Collection' WHERE passport_app_id = %s",
            (app_id,))
        return passport_id

    try:
        passport_id = execute_transaction_custom(ops)
        return jsonify({"message": "Passport issued successfully", "passport_id": passport_id}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
