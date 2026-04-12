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


def _verify_citizen_sequence(cursor):
    cursor.execute(
        """SELECT MAX(citizen_id) AS max_id, MIN(citizen_id) AS min_id, COUNT(*) AS total
               FROM Citizen""")
    row = cursor.fetchone()
    max_id = row["max_id"] or 0
    min_id = row["min_id"] or 0
    total = row["total"] or 0
    if min_id != 1 or max_id != total:
        raise ValueError(
            "Citizen ID sequence is broken: there are gaps in Citizen IDs. "
            "Please restore sequential IDs before approving new citizens."
        )


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
        app_id = cursor.lastrowid

        # Notify all Registrar officers about the new pending application
        cursor.execute(
            """SELECT officer_id FROM Officer o
               JOIN Role r ON o.role_id = r.role_id
               WHERE r.role_name IN ('Registrar', 'Admin') AND o.is_active = 1
               LIMIT 5"""
        )
        registrars = cursor.fetchall()
        for reg in (registrars or []):
            try:
                cursor.execute(
                    """INSERT INTO Notification (citizen_id, officer_id, title, message, notification_type, category)
                       VALUES (NULL, %s, 'New Citizen Application', %s, 'info', 'system')""",
                    (reg["officer_id"],
                     f"A new citizen registration application has been submitted by {data['first_name']} {data['last_name']}. Please review it in the Officer Portal.")
                )
            except Exception:
                pass  # Non-critical — notification failure should not block registration
        return app_id

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
                          status, rejection_reason, citizen_id,
                          COALESCE(national_id_number, cnic_number) AS national_id_number,
                          cnic_number, submission_date, approved_at
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
    import datetime as _dt
    app = execute_query(
        "SELECT * FROM Citizen_Application WHERE application_id = %s",
        (app_id,), fetch='one')
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if app["status"] not in ("Pending", "Under Review"):
        return jsonify({"error": f"Cannot approve application with status '{app['status']}'"}), 400

    # Age check: citizen must be at least 0 days old (any valid DOB accepted for registration)
    try:
        dob_date = _dt.datetime.strptime(str(app["dob"])[:10], "%Y-%m-%d").date()
        age_days = (_dt.date.today() - dob_date).days
        if age_days < 0:
            return jsonify({"error": "Date of birth cannot be in the future."}), 400
    except ValueError:
        return jsonify({"error": "Invalid date of birth format."}), 400

    def ops(conn, cursor):
        _verify_citizen_sequence(cursor)

        # Generate the next sequential national ID number.
        cursor.execute(
            """SELECT
                   COALESCE(MAX(CAST(national_id_number AS UNSIGNED)), 3000000000099) + 1 AS next_nid
               FROM Citizen""")
        row = cursor.fetchone()
        national_id = str(row["next_nid"])

        cursor.execute(
            """INSERT INTO Citizen
               (national_id_number, first_name, last_name, dob, gender,
                marital_status, blood_group, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')""",
            (
                national_id,
                app["first_name"], app["last_name"],
                app["dob"], app["gender"], app["marital_status"] or "Single",
                app["blood_group"]
            )
        )
        new_cid = cursor.lastrowid

        # Auto-create Birth Registration so the Birth Certificate PDF is immediately available.
        # registrar_officer_id = the approving officer; hospital_id is optional (NULL ok).
        cert_number = f"BC-{new_cid}-{str(app['dob']).replace('-', '')}"
        try:
            cursor.execute(
                """INSERT INTO Birth_Registration
                   (citizen_id, hospital_id, registrar_officer_id,
                    birth_certificate_number, registration_date)
                   VALUES (%s, NULL, %s, %s, CURRENT_DATE)""",
                (new_cid, g.officer["officer_id"], cert_number)
            )
        except Exception:
            pass  # If Birth_Registration already exists or hospital_id NOT NULL constraint, skip.

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
                   national_id_number = %s,
                   reviewer_officer_id = %s, approved_at = CURRENT_TIMESTAMP
               WHERE application_id = %s""",
            (new_cid, national_id, g.officer["officer_id"], app_id)
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
               VALUES (%s, NULL, %s, %s, 'success', 'system')""",
            (
                new_cid,
                'Registration Approved — Welcome to CRIDA',
                f'Your registration is approved. Your Citizen ID is {new_cid} and National ID is {national_id}. '
                f'Your Birth Certificate is now available. To get a CNIC, please login and apply from the Documents section.'
            )
        )

        return {"citizen_id": new_cid, "national_id": national_id}

    try:
        result = execute_transaction_custom(ops)
        return jsonify({
            "message": "Application approved. Citizen record and Birth Certificate created. CNIC must be applied for separately.",
            "citizen_id": result["citizen_id"],
            "national_id_number": result["national_id"]
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


# ─────────────────────────────────────────────────────────────────────────
# FAMILY RELATIONSHIPS
# ─────────────────────────────────────────────────────────────────────────

@citizen_bp.route("/family", methods=["GET"])
@token_required
def get_family_relationships():
    if g.officer.get("role_name") != "Citizen":
        return jsonify({"error": "Only citizens can view their family relationships via this endpoint"}), 403

    citizen_id = g.officer["citizen_id"]
    
    # We want to fetch relationships where this citizen is the source OR the target.
    # To keep it simple for the UI, we'll format it relative to the logged-in citizen.
    # Ex: If (1, 2, 'Father') exists -> 2 is the Father of 1.
    
    relations = execute_query(
        """SELECT 
             r.relationship_id,
             r.related_citizen_id as relative_id,
             r.relationship_type,
             c.first_name,
             c.last_name,
             c.status,
             c.national_id_number,
             'Direction: They are my ->' AS dir
           FROM Family_Relationship r
           JOIN Citizen c ON c.citizen_id = r.related_citizen_id
           WHERE r.citizen_id = %s
           
           UNION ALL
           
           SELECT 
             r.relationship_id,
             r.citizen_id as relative_id,
             CASE
               WHEN r.relationship_type = 'Father' OR r.relationship_type = 'Mother' THEN 
                  IF(c2.gender = 'Male', 'Son', 'Daughter')
               WHEN r.relationship_type = 'Husband' THEN 'Wife'
               WHEN r.relationship_type = 'Wife' THEN 'Husband'
               WHEN r.relationship_type = 'Son' OR r.relationship_type = 'Daughter' THEN
                  IF(c2.gender = 'Male', 'Father', 'Mother')
               WHEN r.relationship_type = 'Brother' OR r.relationship_type = 'Sister' THEN
                  IF(c2.gender = 'Male', 'Brother', 'Sister')
             END as relationship_type,
             c.first_name,
             c.last_name,
             c.status,
             c.national_id_number,
             'Direction: I am their ->' AS dir
           FROM Family_Relationship r
           JOIN Citizen c ON c.citizen_id = r.citizen_id
           JOIN Citizen c2 ON c2.citizen_id = r.related_citizen_id
           WHERE r.related_citizen_id = %s
        """,
        (citizen_id, citizen_id), fetch='all'
    )
    return jsonify({"family": relations or []}), 200

@citizen_bp.route("/family", methods=["POST"])
@token_required
def add_family_relationship():
    import mysql.connector
    if g.officer.get("role_name") != "Citizen":
        return jsonify({"error": "Only citizens can add family relationships"}), 403

    citizen_id = g.officer["citizen_id"]
    data = request.json or {}
    related_citizen_id = data.get("related_citizen_id")
    relationship_type = data.get("relationship_type")

    if not related_citizen_id or not relationship_type:
        return jsonify({"error": "related_citizen_id and relationship_type are required"}), 400

    if str(citizen_id) == str(related_citizen_id):
        return jsonify({"error": "You cannot add a relationship to yourself."}), 400

    valid_types = ('Father', 'Mother', 'Son', 'Daughter', 'Husband', 'Wife', 'Brother', 'Sister')
    if relationship_type not in valid_types:
        return jsonify({"error": f"relationship_type must be one of {valid_types}"}), 400

    # Ensure related citizen exists
    target = execute_query("SELECT citizen_id FROM Citizen WHERE citizen_id = %s", (related_citizen_id,), fetch='one')
    if not target:
        return jsonify({"error": f"Citizen ID {related_citizen_id} not found"}), 404

    try:
        def ops(conn, cursor):
            cursor.execute(
                """INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type)
                   VALUES (%s, %s, %s)""",
                (citizen_id, related_citizen_id, relationship_type)
            )
            return True
        execute_transaction_custom(ops)
        return jsonify({"message": f"Successfully added {relationship_type} relationship"}), 201

    except mysql.connector.Error as err:
        # DB trigger threw an exception (e.g. state '45000')
        return jsonify({"error": f"Validation Error: {err.msg}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400