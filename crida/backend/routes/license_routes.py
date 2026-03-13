import datetime
import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required
from utils.validators import require_fields

logger = logging.getLogger(__name__)
license_bp = Blueprint("licenses", __name__)

# Schema reference:
# Driving_License_Application: dl_app_id, citizen_id, license_type, submission_date,
#                              status (Pending/Test Scheduled/Test Passed/Test Failed/
#                                      Approved/Rejected),
#                              test_result (Pass/Fail), test_date, office_id
# Driving_License: license_id, citizen_id, license_number, issue_date, expiry_date,
#                  license_type, status (Valid/Expired/Suspended/Revoked)


@license_bp.route("/", methods=["GET"])
@token_required
def list_license_applications():
    page = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit
    citizen_id = request.args.get("citizen_id")
    if citizen_id:
        rows = execute_query(
            """SELECT dla.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM Driving_License_Application dla
               JOIN Citizen c ON dla.citizen_id = c.citizen_id
               WHERE dla.citizen_id = %s
               ORDER BY dla.submission_date DESC LIMIT %s OFFSET %s""",
            (citizen_id, limit, offset), fetch='all')
    else:
        rows = execute_query(
            """SELECT dla.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM Driving_License_Application dla
               JOIN Citizen c ON dla.citizen_id = c.citizen_id
               ORDER BY dla.submission_date DESC LIMIT %s OFFSET %s""",
            (limit, offset), fetch='all')
    return jsonify({"applications": rows or [], "page": page, "limit": limit}), 200


@license_bp.route("/<int:app_id>", methods=["GET"])
@token_required
def get_license_application(app_id):
    row = execute_query(
        """SELECT dla.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Driving_License_Application dla
           JOIN Citizen c ON dla.citizen_id = c.citizen_id
           WHERE dla.dl_app_id = %s""",
        (app_id,), fetch='one')
    if not row:
        return jsonify({"error": "Application not found"}), 404
    return jsonify({"application": row}), 200


@license_bp.route("/", methods=["POST"])
@token_required
@permission_required("manage_license")
def submit_license():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "license_type", "office_id")
    if not ok:
        return jsonify({"error": err}), 400

    valid_types = ('Motorcycle', 'Car', 'Commercial', 'Heavy Vehicle')
    if data["license_type"] not in valid_types:
        return jsonify({"error": f"license_type must be one of {valid_types}"}), 400

    citizen = execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s", (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO Driving_License_Application
               (citizen_id, license_type, status, office_id)
               VALUES (%s, %s, 'Pending', %s)""",
            (data["citizen_id"], data["license_type"], data["office_id"]))
        app_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, new_values, ip_address)
               VALUES (%s, 'INSERT', 'Driving_License_Application', %s, %s, %s)""",
            (g.officer["officer_id"], app_id,
             f"citizen_id={data['citizen_id']}, type={data['license_type']}",
             request.remote_addr))
        return app_id

    new_id = execute_transaction_custom(ops)
    return jsonify({"message": "License application submitted", "dl_app_id": new_id}), 201


@license_bp.route("/<int:app_id>/schedule-test", methods=["PUT"])
@token_required
@permission_required("manage_license")
def schedule_test(app_id):
    data = request.json or {}
    ok, err = require_fields(data, "test_date")
    if not ok:
        return jsonify({"error": err}), 400

    app = execute_query(
        "SELECT * FROM Driving_License_Application WHERE dl_app_id = %s", (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404

    execute_query(
        """UPDATE Driving_License_Application
           SET status = 'Test Scheduled', test_date = %s
           WHERE dl_app_id = %s""",
        (data["test_date"], app_id))
    return jsonify({"message": "Test scheduled"}), 200


@license_bp.route("/<int:app_id>/record-result", methods=["PUT"])
@token_required
@permission_required("manage_license")
def record_test_result(app_id):
    data = request.json or {}
    ok, err = require_fields(data, "test_result")
    if not ok:
        return jsonify({"error": err}), 400
    if data["test_result"] not in ("Pass", "Fail"):
        return jsonify({"error": "test_result must be 'Pass' or 'Fail'"}), 400

    app = execute_query(
        "SELECT * FROM Driving_License_Application WHERE dl_app_id = %s", (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404

    new_status = "Test Passed" if data["test_result"] == "Pass" else "Test Failed"

    def ops(conn, cursor):
        cursor.execute(
            """UPDATE Driving_License_Application
               SET test_result = %s, status = %s
               WHERE dl_app_id = %s""",
            (data["test_result"], new_status, app_id))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'Driving_License_Application', %s, %s)""",
            (g.officer["officer_id"], app_id, request.remote_addr))
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": f"Test result recorded: {data['test_result']}"}), 200


@license_bp.route("/<int:app_id>/issue", methods=["POST"])
@token_required
@permission_required("manage_license")
def issue_license(app_id):
    """
    ACID: Verify Test Passed → Insert Driving_License → Update app status → Audit_Log
    All steps in one transaction — any failure rolls back entirely.
    """
    def ops(conn, cursor):
        # Step 1: verify test passed
        cursor.execute(
            "SELECT * FROM Driving_License_Application WHERE dl_app_id = %s AND status = 'Test Passed'",
            (app_id,))
        app = cursor.fetchone()
        if not app:
            raise ValueError("Application not found or test not passed")

        citizen_id = app["citizen_id"]
        license_type = app["license_type"]

        # Step 2: insert Driving_License
        today = datetime.date.today()
        expiry = datetime.date(today.year + 5, today.month, today.day)
        license_number = f"DL{app_id:07d}"

        cursor.execute(
            """INSERT INTO Driving_License
               (citizen_id, license_number, issue_date, expiry_date, license_type, status)
               VALUES (%s, %s, %s, %s, %s, 'Valid')""",
            (citizen_id, license_number, today, expiry, license_type))
        license_id = cursor.lastrowid

        # Step 3: update application status to Approved
        cursor.execute(
            "UPDATE Driving_License_Application SET status = 'Approved' WHERE dl_app_id = %s",
            (app_id,))

        # Step 4: audit log
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'INSERT', 'Driving_License', %s, %s)""",
            (g.officer["officer_id"], license_id, request.remote_addr))

        return license_id

    try:
        license_id = execute_transaction_custom(ops)
        return jsonify({"message": "Driving license issued", "license_id": license_id}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@license_bp.route("/<int:app_id>/reject", methods=["PUT"])
@token_required
@permission_required("manage_license")
def reject_license(app_id):
    app = execute_query(
        "SELECT * FROM Driving_License_Application WHERE dl_app_id = %s", (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            "UPDATE Driving_License_Application SET status = 'Rejected' WHERE dl_app_id = %s",
            (app_id,))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'Driving_License_Application', %s, %s)""",
            (g.officer["officer_id"], app_id, request.remote_addr))
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "License application rejected"}), 200
