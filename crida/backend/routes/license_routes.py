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
#   CHECK: when status IN ('Test Passed','Test Failed') → test_result IS NOT NULL AND test_date IS NOT NULL
# Driving_License: license_id, citizen_id, license_number, issue_date, expiry_date,
#                  license_type, status (Valid/Expired/Suspended/Revoked)


def _add_years(d, years):
    """Add years to a date, safely handling Feb-29 on non-leap target years."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # Feb 29 → Feb 28 on non-leap year
        return d.replace(year=d.year + years, day=28)


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


@license_bp.route("/citizen-apply", methods=["POST"])
@token_required
def citizen_apply_license():
    import datetime as _dt
    if g.officer.get("role_name") != "Citizen":
        return jsonify({"error": "Only citizens can use this endpoint"}), 403

    data = request.json or {}
    citizen_id = g.officer["citizen_id"]
    license_type = data.get("license_type", "Car")
    office_id = data.get("office_id", 1)  # Default to Head Office

    valid_types = ('Motorcycle', 'Car', 'Commercial', 'Heavy Vehicle')
    if license_type not in valid_types:
        return jsonify({"error": f"license_type must be one of {valid_types}"}), 400

    # Age check: must be at least 18 years old for a Driving License
    citizen = execute_query(
        "SELECT dob FROM Citizen WHERE citizen_id = %s", (citizen_id,), fetch='one')
    if citizen and citizen.get("dob"):
        try:
            dob = _dt.datetime.strptime(str(citizen["dob"])[:10], "%Y-%m-%d").date()
            age_years = (_dt.date.today() - dob).days // 365
            if age_years < 18:
                return jsonify({"error": f"You must be at least 18 years old to apply for a Driving License. Your current age is {age_years} year(s)."}), 400
        except ValueError:
            pass

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO Driving_License_Application
               (citizen_id, license_type, status, office_id)
               VALUES (%s, %s, 'Pending', %s)""",
            (citizen_id, license_type, office_id))
        new_app_id = cursor.lastrowid

        # Notify License_Officer / Admin about the new driving license application
        cursor.execute(
            """SELECT officer_id FROM Officer o
               JOIN Role r ON o.role_id = r.role_id
               WHERE r.role_name IN ('License_Officer', 'Admin') AND o.is_active = 1
               LIMIT 5"""
        )
        officers = cursor.fetchall()
        for off in (officers or []):
            try:
                cursor.execute(
                    """INSERT INTO Notification (citizen_id, officer_id, title, message, notification_type, category)
                       VALUES (NULL, %s, 'New Driving License Application', %s, 'info', 'document')""",
                    (off["officer_id"],
                     f"Citizen ID {citizen_id} has submitted a new Driving License ({license_type}) application. Please review it in the Officer Portal under Doc Applications.")
                )
            except Exception:
                pass
        return new_app_id

    new_id = execute_transaction_custom(ops)
    return jsonify({"message": "License application submitted", "dl_app_id": new_id}), 201


@license_bp.route("/<int:app_id>/request-biometric", methods=["PUT"])
@token_required
def request_biometric_license(app_id):
    """Move to 'Test Scheduled'. Allowed for License_Officer and Admin by role."""
    if g.officer.get("role_name") not in ("Admin", "License_Officer"):
        return jsonify({"error": "Only License_Officer or Admin can schedule a test visit"}), 403
    app = execute_query(
        "SELECT * FROM Driving_License_Application WHERE dl_app_id = %s", (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] not in ("Pending", "Test Scheduled"):
        return jsonify({"error": f"Cannot start biometric/test process from '{app['status']}'"}), 400

    def ops(conn, cursor):
        cursor.execute(
            "UPDATE Driving_License_Application SET status = 'Test Scheduled' WHERE dl_app_id = %s",
            (app_id,))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'Driving_License_Application', %s, %s)""",
            (g.officer["officer_id"], app_id, request.remote_addr))
        cursor.execute(
            """INSERT INTO Notification (citizen_id, title, message, notification_type, category)
               VALUES (%s, 'Biometric & Test Visit Required', 'Your Driving License application has been reviewed. Please visit your nearest CRIDA office for biometric capture and driving test.', 'info', 'appointment')""",
            (app["citizen_id"],))
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "Application moved to Test Scheduled — citizen notified to visit office."}), 200


@license_bp.route("/<int:app_id>/submit-to-admin", methods=["PUT"])
@token_required
def submit_to_admin_license(app_id):
    """After biometric/test captured, set status to Test Passed and then issue the license.
    This is the 'Done — Submit to Admin' step in the officer workflow.
    """
    app = execute_query(
        "SELECT * FROM Driving_License_Application WHERE dl_app_id = %s", (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] not in ("Test Scheduled",):
        return jsonify({"error": f"Application must be Test Scheduled. Current: '{app['status']}'"}), 400

    today = datetime.date.today()
    expiry = _add_years(today, 5)
    license_number = f"DL{app_id:07d}"
    citizen_id = app["citizen_id"]
    license_type = app["license_type"]

    def ops(conn, cursor):
        # Transition through Test Passed then directly Approved + issue license
        cursor.execute(
            """UPDATE Driving_License_Application
               SET test_result = 'Pass', status = 'Test Passed', test_date = %s
               WHERE dl_app_id = %s""",
            (str(today), app_id))
        cursor.execute(
            """INSERT INTO Driving_License
               (citizen_id, license_number, issue_date, expiry_date, license_type, status)
               VALUES (%s, %s, %s, %s, %s, 'Valid')""",
            (citizen_id, license_number, today, expiry, license_type))
        license_id = cursor.lastrowid
        cursor.execute(
            "UPDATE Driving_License_Application SET status = 'Approved' WHERE dl_app_id = %s",
            (app_id,))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'INSERT', 'Driving_License', %s, %s)""",
            (g.officer["officer_id"], license_id, request.remote_addr))
        cursor.execute(
            """INSERT INTO Notification (citizen_id, title, message, notification_type, category)
               VALUES (%s, 'Driving License Approved', 'Your driving license application has been approved and your license is now active. You can download it from your portal.', 'success', 'document')""",
            (citizen_id,))
        return license_id

    license_id = execute_transaction_custom(ops)
    return jsonify({"message": "Driving license issued successfully.", "license_id": license_id}), 200


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
    """
    Records the test result.
    Sets test_date to today if not already set — required by the DB CHECK constraint:
      (status IN ('Test Passed','Test Failed') → test_result IS NOT NULL AND test_date IS NOT NULL)
    """
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
    # Use provided test_date, fall back to existing, then today — satisfies NOT NULL constraint
    test_date = (data.get("test_date")
                 or (str(app["test_date"]) if app.get("test_date") else None)
                 or str(datetime.date.today()))

    def ops(conn, cursor):
        cursor.execute(
            """UPDATE Driving_License_Application
               SET test_result = %s, status = %s, test_date = %s
               WHERE dl_app_id = %s""",
            (data["test_result"], new_status, test_date, app_id))
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
    Final Admin approval: issues the Driving License and marks application Approved.
    Application must be in 'Pending Admin Approval' state.
    """
    def ops(conn, cursor):
        cursor.execute(
            "SELECT * FROM Driving_License_Application WHERE dl_app_id = %s AND status = 'Pending Admin Approval'",
            (app_id,))
        app = cursor.fetchone()
        if not app:
            raise ValueError("Application not found or not in Pending Admin Approval state")

        citizen_id = app["citizen_id"]
        license_type = app["license_type"]
        today = datetime.date.today()
        expiry = _add_years(today, 5)
        license_number = f"DL{app_id:07d}"

        cursor.execute(
            """INSERT INTO Driving_License
               (citizen_id, license_number, issue_date, expiry_date, license_type, status)
               VALUES (%s, %s, %s, %s, %s, 'Valid')""",
            (citizen_id, license_number, today, expiry, license_type))
        license_id = cursor.lastrowid

        cursor.execute(
            "UPDATE Driving_License_Application SET status = 'Approved' WHERE dl_app_id = %s",
            (app_id,))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'INSERT', 'Driving_License', %s, %s)""",
            (g.officer["officer_id"], license_id, request.remote_addr))
        cursor.execute(
            """INSERT INTO Notification (citizen_id, title, message, notification_type, category)
               VALUES (%s, 'Driving License Approved', 'Your driving license application has been approved and your license is now active. You can download it from your portal.', 'success', 'document')""",
            (citizen_id,))
        return license_id

    try:
        license_id = execute_transaction_custom(ops)
        return jsonify({"message": "Driving license issued", "license_id": license_id}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@license_bp.route("/<int:app_id>/reject", methods=["PUT"])
@token_required
def reject_license(app_id):
    """Any authenticated officer (non-Citizen) may reject a License application."""
    if g.officer.get("role_name") == "Citizen":
        return jsonify({"error": "Citizens cannot perform this action"}), 403
    data = request.json or {}
    app = execute_query(
        "SELECT * FROM Driving_License_Application WHERE dl_app_id = %s", (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] in ("Approved",):
        return jsonify({"error": "Cannot reject an already approved application"}), 400

    def ops(conn, cursor):
        cursor.execute(
            "UPDATE Driving_License_Application SET status = 'Rejected' WHERE dl_app_id = %s",
            (app_id,))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'Driving_License_Application', %s, %s)""",
            (g.officer["officer_id"], app_id, request.remote_addr))
        # Notify citizen
        try:
            cursor.execute(
                """INSERT INTO Notification (citizen_id, title, message, notification_type, category)
                   VALUES (%s, 'Driving License Application Rejected', %s, 'error', 'document')""",
                (app["citizen_id"],
                 f"Your Driving License application has been rejected. Reason: {data.get('reason', 'No reason provided')}")
            )
        except Exception:
            pass
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "License application rejected"}), 200