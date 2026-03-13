"""
routes/payment_routes.py — Payment Recording & Listing
=======================================================
POST /     — record payment (ACID: INSERT + optional fee_paid update + Audit)
GET  /     — list payments (paginated, filterable by citizen)
GET  /<id> — get single payment transaction

ACID transaction scenario #2 (guide section 3.5):
  Step 1 — INSERT Payment_Transaction
  Step 2 — If passport_app_id given → UPDATE Passport_Application fee_paid=1
           If cnic_app_id given    → UPDATE CNIC_Application fee_paid=1
           If dl_app_id given      → UPDATE DL_Application fee_paid=1
  Step 3 — INSERT Audit_Log
All three steps succeed or all rollback.
"""

import datetime
import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from utils.validators import require_fields
from utils.notifications import send_notification

logger     = logging.getLogger(__name__)
payment_bp = Blueprint("payments", __name__)


@payment_bp.route("/", methods=["GET"])
@token_required
def list_payments():
    page       = int(request.args.get("page", 1))
    limit      = min(int(request.args.get("limit", 20)), 100)
    offset     = (page - 1) * limit
    citizen_id = request.args.get("citizen_id")

    if citizen_id:
        rows = execute_query(
            """SELECT pt.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM Payment_Transaction pt
               JOIN Citizen c ON pt.citizen_id = c.citizen_id
               WHERE pt.citizen_id = %s
               ORDER BY pt.transaction_id DESC LIMIT %s OFFSET %s""",
            (citizen_id, limit, offset), fetch='all'
        )
        total = execute_query(
            "SELECT COUNT(*) AS cnt FROM Payment_Transaction WHERE citizen_id=%s",
            (citizen_id,), fetch='one'
        )
    else:
        rows = execute_query(
            """SELECT pt.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM Payment_Transaction pt
               JOIN Citizen c ON pt.citizen_id = c.citizen_id
               ORDER BY pt.transaction_id DESC LIMIT %s OFFSET %s""",
            (limit, offset), fetch='all'
        )
        total = execute_query(
            "SELECT COUNT(*) AS cnt FROM Payment_Transaction", fetch='one'
        )
    return jsonify({"payments": rows or [], "total": total["cnt"],
                    "page": page, "limit": limit}), 200


@payment_bp.route("/<int:pid>", methods=["GET"])
@token_required
def get_payment(pid):
    row = execute_query(
        """SELECT pt.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Payment_Transaction pt
           JOIN Citizen c ON pt.citizen_id = c.citizen_id
           WHERE pt.transaction_id = %s""",
        (pid,), fetch='one'
    )
    if not row:
        return jsonify({"error": "Payment not found"}), 404
    return jsonify({"payment": row}), 200


@payment_bp.route("/", methods=["POST"])
@token_required
def record_payment():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "service_type",
                             "amount", "payment_method")
    if not ok:
        return jsonify({"error": err}), 400

    def ops(conn, cursor):
        ref = f"TX-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # Step 1 — Insert payment
        cursor.execute(
            """INSERT INTO Payment_Transaction
                   (citizen_id, service_type, cnic_app_id, passport_app_id,
                    dl_app_id, amount, payment_method, payment_status,
                    transaction_reference)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'Completed',%s)""",
            (data["citizen_id"],
             data["service_type"],
             data.get("cnic_app_id"),
             data.get("passport_app_id"),
             data.get("dl_app_id"),
             data["amount"],
             data["payment_method"],
             ref)
        )
        pid = cursor.lastrowid

        # Step 2 — Mark fee_paid on linked application
        if data.get("passport_app_id"):
            cursor.execute(
                "UPDATE Passport_Application SET fee_paid=1 WHERE passport_app_id=%s",
                (data["passport_app_id"],)
            )
        if data.get("cnic_app_id"):
            cursor.execute(
                "UPDATE CNIC_Application SET fee_paid=1 WHERE cnic_app_id=%s",
                (data["cnic_app_id"],)
            )
        if data.get("dl_app_id"):
            cursor.execute(
                "UPDATE DL_Application SET fee_paid=1 WHERE dl_app_id=%s",
                (data["dl_app_id"],)
            )

        # Step 3 — Audit
        cursor.execute(
            """INSERT INTO Audit_Log
                   (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s,'INSERT','Payment_Transaction',%s,%s)""",
            (g.officer["officer_id"], pid, request.remote_addr or "unknown")
        )
        return pid, ref

    pid, ref = execute_transaction_custom(ops)

    # Post-commit notification
    send_notification(
        citizen_id=data["citizen_id"],
        title="Payment Confirmed",
        message=(f"Payment of PKR {data['amount']} for "
                 f"{data['service_type']} confirmed. Ref: {ref}"),
        notif_type="success",
        category="transaction"
    )
    return jsonify({"message": "Payment recorded",
                    "payment_id": pid, "reference": ref}), 201
