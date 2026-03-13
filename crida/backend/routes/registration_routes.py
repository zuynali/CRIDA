"""
routes/registration_routes.py — Birth, Death, Marriage Registrations
=====================================================================
POST /birth          — register birth (ACID)
GET  /birth/<id>     — get birth record
POST /death          — register death (ACID; trigger sets citizen='deceased')
GET  /death/<id>     — get death record
POST /marriage       — register marriage (ACID; trigger validates age/gender)
GET  /marriage/<id>  — get marriage record

Phase 1 triggers that fire automatically:
  - validate_marriage_requirements: husband/wife age ≥ 18, genders enforced
  - update_citizen_status_on_death: sets citizen status='deceased'
  - validate_cnic_applicant_age: age ≥ 18 for CNIC
"""

import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from middleware.rbac import permission_required
from utils.validators import require_fields
from utils.notifications import send_notification

logger = logging.getLogger(__name__)
reg_bp = Blueprint("registrations", __name__)


# ── BIRTH ─────────────────────────────────────────────────────────────────
@reg_bp.route("/birth", methods=["POST"])
@token_required
@permission_required("manage_registrations")
def register_birth():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "birth_date")
    if not ok:
        return jsonify({"error": err}), 400

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO Birth_Registration
                   (citizen_id, birth_date, birth_place, hospital_id,
                    father_name, mother_name, registrar_officer_id,
                    birth_certificate_number)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (data["citizen_id"],
             data["birth_date"],
             data.get("birth_place"),
             data.get("hospital_id"),
             data.get("father_name"),
             data.get("mother_name"),
             g.officer["officer_id"],
             f"BC-{data['citizen_id']}-{data['birth_date'].replace('-','')}")
        )
        bid = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'INSERT','Birth_Registration',%s,%s)""",
            (g.officer["officer_id"], bid, request.remote_addr or "unknown")
        )
        return bid

    new_id = execute_transaction_custom(ops)
    return jsonify({"message": "Birth registered",
                    "birth_registration_id": new_id}), 201


@reg_bp.route("/birth/<int:cid>", methods=["GET"])
@token_required
def get_birth(cid):
    row = execute_query(
        """SELECT br.*, c.first_name, c.last_name, c.dob, c.gender,
                  h.name AS hospital_name
           FROM Birth_Registration br
           JOIN Citizen c ON br.citizen_id = c.citizen_id
           LEFT JOIN Hospital h ON br.hospital_id = h.hospital_id
           WHERE br.citizen_id = %s LIMIT 1""",
        (cid,), fetch='one'
    )
    if not row:
        return jsonify({"error": "Birth registration not found"}), 404
    return jsonify({"registration": row}), 200


# ── DEATH ─────────────────────────────────────────────────────────────────
@reg_bp.route("/death", methods=["POST"])
@token_required
@permission_required("manage_registrations")
def register_death():
    """
    ACID: INSERT Death_Registration + Audit_Log.
    Trigger update_citizen_status_on_death fires automatically
    and sets citizen status='deceased'.
    """
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "death_date")
    if not ok:
        return jsonify({"error": err}), 400

    # Confirm citizen exists and is active
    citizen = execute_query(
        "SELECT citizen_id, status FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one'
    )
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404
    if citizen["status"] == "deceased":
        return jsonify({"error": "Death already registered for this citizen"}), 400

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO Death_Registration
                   (citizen_id, death_date, death_cause, death_place,
                    hospital_id, registrar_officer_id,
                    death_certificate_number)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (data["citizen_id"],
             data["death_date"],
             data.get("death_cause"),
             data.get("death_place"),
             data.get("hospital_id"),
             g.officer["officer_id"],
             f"DC-{data['citizen_id']}-{data['death_date'].replace('-','')}")
        )
        did = cursor.lastrowid
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'INSERT','Death_Registration',%s,%s)""",
            (g.officer["officer_id"], did, request.remote_addr or "unknown")
        )
        return did

    new_id = execute_transaction_custom(ops)
    return jsonify({"message": "Death registered. Citizen status updated by trigger.",
                    "death_registration_id": new_id}), 201


@reg_bp.route("/death/<int:cid>", methods=["GET"])
@token_required
def get_death(cid):
    row = execute_query(
        """SELECT dr.*, c.first_name, c.last_name
           FROM Death_Registration dr
           JOIN Citizen c ON dr.citizen_id = c.citizen_id
           WHERE dr.citizen_id = %s LIMIT 1""",
        (cid,), fetch='one'
    )
    if not row:
        return jsonify({"error": "Death registration not found"}), 404
    return jsonify({"registration": row}), 200


# ── MARRIAGE ──────────────────────────────────────────────────────────────
@reg_bp.route("/marriage", methods=["POST"])
@token_required
@permission_required("manage_registrations")
def register_marriage():
    """
    ACID three-step transaction (guide section 3.4):
      Step 1 — INSERT Marriage_Registration (trigger validates age/gender)
      Step 2 — UPDATE Citizen marital_status='Married' for both
      Step 3 — INSERT Audit_Log
    Post-commit: send_notification to both citizens.
    """
    data = request.json or {}
    ok, err = require_fields(data, "husband_id", "wife_id", "marriage_date")
    if not ok:
        return jsonify({"error": err}), 400

    def ops(conn, cursor):
        cursor.execute(
            """INSERT INTO Marriage_Registration
                   (husband_id, wife_id, marriage_date,
                    registrar_officer_id, marriage_certificate_number)
               VALUES (%s,%s,%s,%s,%s)""",
            (data["husband_id"], data["wife_id"], data["marriage_date"],
             g.officer["officer_id"],
             f"MARR-{data['husband_id']}-{data['wife_id']}")
        )
        mid = cursor.lastrowid
        for cid in [data["husband_id"], data["wife_id"]]:
            cursor.execute(
                "UPDATE Citizen SET marital_status='Married' WHERE citizen_id=%s",
                (cid,)
            )
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'INSERT','Marriage_Registration',%s,%s)""",
            (g.officer["officer_id"], mid, request.remote_addr or "unknown")
        )
        return mid

    try:
        mid = execute_transaction_custom(ops)
    except Exception as e:
        # Trigger may raise e.g. age/gender violations
        return jsonify({"error": f"Marriage validation failed: {str(e)}"}), 400

    # Post-commit notifications (non-blocking)
    for cid in [data["husband_id"], data["wife_id"]]:
        send_notification(
            citizen_id=cid,
            title="Marriage Registered",
            message=f"Your marriage (ID: {mid}) has been successfully registered.",
            notif_type="success",
            category="transaction"
        )

    return jsonify({"message": "Marriage registered", "marriage_id": mid}), 201


@reg_bp.route("/marriage/<int:mid>", methods=["GET"])
@token_required
def get_marriage(mid):
    row = execute_query(
        """SELECT mr.*,
                  CONCAT(h.first_name,' ',h.last_name) AS husband_name,
                  CONCAT(w.first_name,' ',w.last_name) AS wife_name
           FROM Marriage_Registration mr
           JOIN Citizen h ON mr.husband_id = h.citizen_id
           JOIN Citizen w ON mr.wife_id   = w.citizen_id
           WHERE mr.marriage_id = %s""",
        (mid,), fetch='one'
    )
    if not row:
        return jsonify({"error": "Marriage registration not found"}), 404
    return jsonify({"registration": row}), 200
