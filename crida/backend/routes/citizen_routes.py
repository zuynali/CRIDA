import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required
from utils.validators import (
    validate_national_id, validate_phone, validate_email,
    validate_date, sanitize_string, require_fields
)

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
    return jsonify({"citizens": rows or [], "total": total["cnt"], "page": page, "limit": limit}), 200


@citizen_bp.route("/apply", methods=["POST"])
def apply_citizen():
    data = request.json or {}
    ok, err = require_fields(
        data,
        "first_name", "last_name",
        "dob", "gender", "city", "province"
    )
    if not ok:
        return jsonify({"error": err}), 400

    if not validate_date(data["dob"]):
        return jsonify({"error": "dob must be a valid date in YYYY-MM-DD format"}), 400
    if data.get("phone") and not validate_phone(data["phone"]):
        return jsonify({"error": "phone must be exactly 11 digits"}), 400
    if data.get("email") and not validate_email(data["email"]):
        return jsonify({"error": "email is not valid"}), 400

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO Citizen_Application
               (first_name, last_name, dob, gender,
                marital_status, blood_group, house_no, street, city, province,
                postal_code, phone, email)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                sanitize_string(data["first_name"], 50),
                sanitize_string(data["last_name"], 50),
                data["dob"],
                data["gender"],
                data.get("marital_status", "Single"),
                data.get("blood_group"),
                sanitize_string(data.get("house_no"), 20),
                sanitize_string(data.get("street"), 100),
                sanitize_string(data["city"], 50),
                sanitize_string(data["province"], 50),
                sanitize_string(data.get("postal_code"), 10),
                sanitize_string(data.get("phone"), 20),
                sanitize_string(data.get("email"), 100)
            )
        )
        return cursor.lastrowid

    application_id = execute_transaction_custom(ops)
    return jsonify({"message": "Application submitted successfully.", "application_id": application_id}), 201


@citizen_bp.route("/applications/status", methods=["GET"])
def get_application_status():
    first = (request.args.get("first_name") or "").strip()
    last = (request.args.get("last_name") or "").strip()
    dob = request.args.get("dob")
    if not first or not last or not dob:
        return jsonify({"error": "first_name, last_name, and dob are required"}), 400

    app = execute_query(
        """SELECT application_id, first_name, last_name, dob,
                          gender, marital_status, blood_group, city, province,
                          status, rejection_reason, citizen_id, cnic_number,
                          submission_date, approved_at
           FROM Citizen_Application
           WHERE LOWER(first_name) = LOWER(%s) AND LOWER(last_name) = LOWER(%s) AND dob = %s
           ORDER BY submission_date DESC LIMIT 1""",
        (first.lower(), last.lower(), dob), fetch='one')
    if not app:
        return jsonify({"error": "No registration application found for these details."}), 404
    return jsonify({"application": app}), 200


@citizen_bp.route("/applications", methods=["GET"])
@token_required
@permission_required("manage_citizens")
def list_citizen_applications():
    page = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 50)), 100)
    offset = (page - 1) * limit
    citizen_id = request.args.get("citizen_id")
    status = request.args.get("status")

    where_clauses = []
    params = []
    if citizen_id:
        where_clauses.append("ca.citizen_id = %s")
        params.append(citizen_id)
    if status:
        where_clauses.append("ca.status = %s")
        params.append(status)

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    rows = execute_query(
        f"""SELECT ca.*, CONCAT(ca.first_name, ' ', ca.last_name) AS applicant_name
               FROM Citizen_Application ca
               {where_sql}
               ORDER BY ca.submission_date DESC
               LIMIT %s OFFSET %s""",
        (*params, limit, offset), fetch='all')
    return jsonify({"applications": rows or [], "page": page, "limit": limit}), 200


@citizen_bp.route("/applications/<int:app_id>", methods=["GET"])
@token_required
@permission_required("manage_citizens")
def get_citizen_application(app_id):
    app = execute_query(
        """SELECT ca.*, CONCAT(ca.first_name, ' ', ca.last_name) AS applicant_name
           FROM Citizen_Application ca
           WHERE ca.application_id = %s""",
        (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404
    return jsonify({"application": app}), 200


@citizen_bp.route("/applications/<int:app_id>/approve", methods=["PUT"])
@token_required
@permission_required("manage_citizens")
def approve_citizen_application(app_id):
    app = execute_query(
        "SELECT * FROM Citizen_Application WHERE application_id = %s",
        (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] not in ("Pending", "Under Review"):
        return jsonify({"error": f"Cannot approve application with status '{app['status']}'"}), 400

    # The application does not carry a national_id_number until approval,
    # so we skip a duplicate NID check here and generate a new CNIC record.
    def ops(conn, cursor):
        # Get next citizen_id to generate CNIC
        cursor.execute("SELECT COALESCE(MAX(citizen_id), 0) + 1 AS next_id FROM Citizen")
        next_id = cursor.fetchone()["next_id"]
        card_number = str(9000000000000 + next_id)

        cursor.execute(
            """INSERT INTO Citizen
               (national_id_number, first_name, last_name, dob, gender,
                marital_status, blood_group, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')""",
            (
                card_number,
                app["first_name"], app["last_name"],
                app["dob"], app["gender"], app["marital_status"] or "Single",
                app["blood_group"]
            )
        )
        new_cid = cursor.lastrowid

        cursor.execute(
            "INSERT INTO CNIC_Card"
            " (citizen_id, card_number, issue_date, expiry_date, card_status, fingerprint_verified)"
            " VALUES (%s, %s, CURRENT_DATE, DATE_ADD(CURRENT_DATE, INTERVAL 10 YEAR), 'Active', FALSE)",
            (new_cid, card_number)
        )

        if app.get("city"):
            cursor.execute(
                "INSERT INTO Address (house_no, street, city, province, postal_code)"
                " VALUES (%s, %s, %s, %s, %s)",
                (
                    app.get("house_no"), app.get("street"), app.get("city"),
                    app.get("province"), app.get("postal_code")
                )
            )
            address_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO Citizen_Address_History (citizen_id, address_id, start_date)"
                " VALUES (%s, %s, CURRENT_DATE)",
                (new_cid, address_id)
            )

        cursor.execute(
            """UPDATE Citizen_Application
               SET status = 'Approved', citizen_id = %s,
                   cnic_number = %s, reviewer_officer_id = %s,
                   approved_at = CURRENT_TIMESTAMP
               WHERE application_id = %s""",
            (new_cid, card_number, g.officer["officer_id"], app_id)
        )

        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'Citizen_Application', %s, %s)""",
            (g.officer["officer_id"], app_id, request.remote_addr)
        )

        cursor.execute(
            """INSERT INTO Notification
               (citizen_id, officer_id, title, message, notification_type, category)
               VALUES (%s, %s, %s, %s, 'success', 'system')""",
            (
                new_cid,
                None,
                'CNIC Application Approved',
                f'Your registration is approved. Your CNIC number is {card_number}.'
            )
        )

        return {"citizen_id": new_cid, "cnic_number": card_number}

    try:
        result = execute_transaction_custom(ops)
        return jsonify({
            "message": "Application approved and citizen record created.",
            "citizen_id": result["citizen_id"],
            "cnic_number": result["cnic_number"]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@citizen_bp.route("/applications/<int:app_id>/reject", methods=["PUT"])
@token_required
@permission_required("manage_citizens")
def reject_citizen_application(app_id):
    data = request.json or {}
    app = execute_query(
        "SELECT * FROM Citizen_Application WHERE application_id = %s",
        (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404

    def ops(conn, cursor):
        cursor.execute(
            """UPDATE Citizen_Application
               SET status = 'Rejected', rejection_reason = %s,
                   reviewer_officer_id = %s, approved_at = CURRENT_TIMESTAMP
               WHERE application_id = %s""",
            (data.get("reason", "Rejected by officer"), g.officer["officer_id"], app_id)
        )
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'UPDATE', 'Citizen_Application', %s, %s)""",
            (g.officer["officer_id"], app_id, request.remote_addr)
        )
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "Application rejected."}), 200


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
    ok, err = require_fields(data, "national_id_number", "first_name", "last_name", "dob", "gender")
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
    allowed = ["first_name", "last_name", "dob", "gender", "marital_status", "blood_group", "status"]
    # Validate status if provided — must be a valid ENUM value
    if "status" in data and data["status"] not in ("active", "deceased", "blacklisted"):
        return jsonify({"error": "status must be one of: active, deceased, blacklisted"}), 400
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
    existing = execute_query("SELECT citizen_id FROM Citizen WHERE citizen_id = %s", (cid,), fetch='one')
    if not existing:
        return jsonify({"error": "Citizen not found"}), 404

    def ops(conn, cursor):
        # Use 'blacklisted' — the valid ENUM soft-delete state
        # ('inactive' is not in the schema ENUM: active, deceased, blacklisted)
        cursor.execute("UPDATE Citizen SET status = 'blacklisted' WHERE citizen_id = %s", (cid,))
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'DELETE', 'Citizen', %s, %s)""",
            (g.officer["officer_id"], cid, request.remote_addr))
        return True

    execute_transaction_custom(ops)
    return jsonify({"message": "Citizen deactivated (blacklisted)"}), 200


@citizen_bp.route("/stats", methods=["GET"])
@token_required
def get_stats():
    citizen_status = execute_query("SELECT status, COUNT(*) as count FROM Citizen GROUP BY status", fetch='all')
    citizen_gender = execute_query("SELECT gender, COUNT(*) as count FROM Citizen GROUP BY gender", fetch='all')
    app_status = execute_query("SELECT status, COUNT(*) as count FROM Citizen_Application GROUP BY status", fetch='all')
    return jsonify({
        "citizen_status": {row['status']: row['count'] for row in citizen_status},
        "citizen_gender": {row['gender']: row['count'] for row in citizen_gender},
        "application_status": {row['status']: row['count'] for row in app_status}
    }), 200