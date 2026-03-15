import logging
import datetime
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required
from utils.validators import require_fields

logger = logging.getLogger(__name__)
reg_bp = Blueprint("registrations", __name__)

# Schema reference (actual columns — no father_id / mother_id):
# Birth_Registration:    birth_id, citizen_id, hospital_id,
#                        registrar_officer_id (NOT NULL),
#                        birth_certificate_number,
#                        registration_date (DEFAULT CURRENT_TIMESTAMP)
# Death_Registration:    death_id, citizen_id, date_of_death, cause_of_death,
#                        place_of_death, registrar_officer_id (NOT NULL),
#                        death_certificate_number
# Marriage_Registration: marriage_id, husband_id, wife_id, marriage_date,
#                        registrar_officer_id, marriage_certificate_number


@reg_bp.route("/birth", methods=["POST"])
@token_required
@permission_required("manage_registrations")
def register_birth():
    data = request.json or {}
    # citizen_id is the only hard requirement; hospital_id is optional
    ok, err = require_fields(data, "citizen_id")
    if not ok:
        return jsonify({"error": err}), 400

    citizen = execute_query(
        "SELECT citizen_id, first_name, last_name FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    def ops(conn, cursor):
        today = datetime.date.today().strftime('%Y%m%d')
        cert_number = f"BC-{data['citizen_id']}-{today}"
        cursor.execute(
            """INSERT INTO Birth_Registration
               (citizen_id, hospital_id, registrar_officer_id, birth_certificate_number)
               VALUES (%s, %s, %s, %s)""",
            (data["citizen_id"],
             data.get("hospital_id"),
             g.officer["officer_id"],    # NOT NULL — was missing before
             cert_number))
        birth_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'INSERT', 'Birth_Registration', %s, %s)""",
            (g.officer["officer_id"], birth_id, request.remote_addr))
        return birth_id

    try:
        birth_id = execute_transaction_custom(ops)
        return jsonify({"message": "Birth registered", "birth_id": birth_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reg_bp.route("/birth/<int:cid>", methods=["GET"])
@token_required
def get_birth_registration(cid):
    row = execute_query(
        """SELECT br.*, c.first_name, c.last_name, c.dob, c.gender,
                  h.name AS hospital_name
           FROM Birth_Registration br
           JOIN Citizen c ON br.citizen_id = c.citizen_id
           LEFT JOIN Hospital h ON br.hospital_id = h.hospital_id
           WHERE br.citizen_id = %s LIMIT 1""",
        (cid,), fetch='one')
    if not row:
        return jsonify({"error": "Birth registration not found"}), 404
    return jsonify({"registration": row}), 200


@reg_bp.route("/death", methods=["POST"])
@token_required
@permission_required("manage_registrations")
def register_death():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "date_of_death")
    if not ok:
        return jsonify({"error": err}), 400

    citizen = execute_query(
        "SELECT citizen_id, status FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    def ops(conn, cursor):
        cert_number = f"DC-{data['citizen_id']}-{data['date_of_death'].replace('-', '')}"
        cursor.execute(
            """INSERT INTO Death_Registration
               (citizen_id, date_of_death, cause_of_death,
                place_of_death, registrar_officer_id, death_certificate_number)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (data["citizen_id"],
             data["date_of_death"],
             data.get("cause_of_death"),
             data.get("place_of_death"),
             g.officer["officer_id"],    # NOT NULL — was missing before
             cert_number))
        death_id = cursor.lastrowid
        # Trigger update_citizen_status_on_death fires automatically,
        # setting citizen status = 'deceased'
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'INSERT', 'Death_Registration', %s, %s)""",
            (g.officer["officer_id"], death_id, request.remote_addr))
        return death_id

    try:
        death_id = execute_transaction_custom(ops)
        return jsonify({
            "message": "Death registered. Citizen status updated to deceased by trigger.",
            "death_id": death_id
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reg_bp.route("/death/<int:cid>", methods=["GET"])
@token_required
def get_death_registration(cid):
    row = execute_query(
        """SELECT dr.*, c.first_name, c.last_name
           FROM Death_Registration dr
           JOIN Citizen c ON dr.citizen_id = c.citizen_id
           WHERE dr.citizen_id = %s LIMIT 1""",
        (cid,), fetch='one')
    if not row:
        return jsonify({"error": "Death registration not found"}), 404
    return jsonify({"registration": row}), 200


@reg_bp.route("/marriage", methods=["POST"])
@token_required
@permission_required("manage_registrations")
def register_marriage():
    """
    ACID Transaction:
    Step 1 — INSERT Marriage_Registration (trigger validates age >= 18 and genders)
    Step 2 — UPDATE both citizens marital_status = 'Married'
    Step 3 — INSERT Audit_Log
    All 3 steps or none.
    """
    data = request.json or {}
    ok, err = require_fields(data, "husband_id", "wife_id", "marriage_date")
    if not ok:
        return jsonify({"error": err}), 400

    def ops(conn, cursor):
        cert_number = f"MARR-{data['husband_id']}-{data['wife_id']}"
        # Step 1: insert (Phase 1 trigger validate_marriage_requirements fires here)
        cursor.execute(
            """INSERT INTO Marriage_Registration
               (husband_id, wife_id, marriage_date, registrar_officer_id,
                marriage_certificate_number)
               VALUES (%s, %s, %s, %s, %s)""",
            (data["husband_id"], data["wife_id"], data["marriage_date"],
             g.officer["officer_id"], cert_number))
        mid = cursor.lastrowid

        # Step 2: update marital status for both citizens
        for cid in [data["husband_id"], data["wife_id"]]:
            cursor.execute(
                "UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id = %s",
                (cid,))

        # Step 3: audit log
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'INSERT', 'Marriage_Registration', %s, %s)""",
            (g.officer["officer_id"], mid, request.remote_addr))
        return mid

    try:
        mid = execute_transaction_custom(ops)
        return jsonify({"message": "Marriage registered", "marriage_id": mid}), 201
    except Exception as e:
        # Trigger violations (age/gender) surface as DB errors
        return jsonify({"error": str(e)}), 400


@reg_bp.route("/marriage/<int:mid>", methods=["GET"])
@token_required
def get_marriage_registration(mid):
    row = execute_query(
        """SELECT mr.*,
                  CONCAT(h.first_name,' ',h.last_name) AS husband_name,
                  CONCAT(w.first_name,' ',w.last_name) AS wife_name
           FROM Marriage_Registration mr
           JOIN Citizen h ON mr.husband_id = h.citizen_id
           JOIN Citizen w ON mr.wife_id = w.citizen_id
           WHERE mr.marriage_id = %s""",
        (mid,), fetch='one')
    if not row:
        return jsonify({"error": "Marriage registration not found"}), 404
    return jsonify({"registration": row}), 200