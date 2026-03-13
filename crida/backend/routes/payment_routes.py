import datetime
import logging
from flask import Blueprint, request, jsonify, g
from db import execute_query, execute_transaction_custom
from middleware.auth import token_required
from utils.validators import require_fields

logger = logging.getLogger(__name__)
payment_bp = Blueprint("payments", __name__)

# Schema reference:
# Payment_Transaction: payment_id, citizen_id, service_type, cnic_app_id, passport_app_id,
#                      dl_app_id, amount, payment_method, payment_status, transaction_reference,
#                      payment_date
# service_type enum: CNIC, Passport, Driving License, Birth Certificate,
#                    Death Certificate, Marriage Certificate
# payment_method enum: Cash, Credit Card, Debit Card, Bank Transfer, Online
# payment_status enum: Pending, Completed, Failed, Refunded
# NOTE: Only Passport_Application has fee_paid. CNIC_Application does NOT.


@payment_bp.route("/", methods=["GET"])
@token_required
def list_payments():
    page = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = (page - 1) * limit
    citizen_id = request.args.get("citizen_id")
    if citizen_id:
        rows = execute_query(
            """SELECT pt.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM Payment_Transaction pt
               JOIN Citizen c ON pt.citizen_id = c.citizen_id
               WHERE pt.citizen_id = %s
               ORDER BY pt.payment_date DESC LIMIT %s OFFSET %s""",
            (citizen_id, limit, offset), fetch='all')
    else:
        rows = execute_query(
            """SELECT pt.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
               FROM Payment_Transaction pt
               JOIN Citizen c ON pt.citizen_id = c.citizen_id
               ORDER BY pt.payment_date DESC LIMIT %s OFFSET %s""",
            (limit, offset), fetch='all')
    return jsonify({"payments": rows or [], "page": page, "limit": limit}), 200


@payment_bp.route("/<int:pid>", methods=["GET"])
@token_required
def get_payment(pid):
    row = execute_query(
        """SELECT pt.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Payment_Transaction pt
           JOIN Citizen c ON pt.citizen_id = c.citizen_id
           WHERE pt.payment_id = %s""",
        (pid,), fetch='one')
    if not row:
        return jsonify({"error": "Payment not found"}), 404
    return jsonify({"payment": row}), 200


@payment_bp.route("/", methods=["POST"])
@token_required
def record_payment():
    """
    ACID Transaction Scenario #2 (guide section 3.5):
    Step 1 — INSERT Payment_Transaction
    Step 2 — If linked to Passport_Application, mark fee_paid = 1
             (CNIC_Application has no fee_paid column — skip for CNIC)
    Step 3 — INSERT Audit_Log
    All 3 succeed or ALL rollback.
    """
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "service_type", "amount", "payment_method")
    if not ok:
        return jsonify({"error": err}), 400

    valid_services = ('CNIC', 'Passport', 'Driving License',
                      'Birth Certificate', 'Death Certificate', 'Marriage Certificate')
    if data["service_type"] not in valid_services:
        return jsonify({"error": f"service_type must be one of {valid_services}"}), 400

    valid_methods = ('Cash', 'Credit Card', 'Debit Card', 'Bank Transfer', 'Online')
    if data["payment_method"] not in valid_methods:
        return jsonify({"error": f"payment_method must be one of {valid_methods}"}), 400

    def ops(conn, cursor):
        ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
        tx_ref = f"TX-{ts}"

        # Step 1: insert payment
        cursor.execute(
            """INSERT INTO Payment_Transaction
               (citizen_id, service_type, cnic_app_id, passport_app_id, dl_app_id,
                amount, payment_method, payment_status, transaction_reference)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'Completed', %s)""",
            (data["citizen_id"],
             data["service_type"],
             data.get("cnic_app_id"),
             data.get("passport_app_id"),
             data.get("dl_app_id"),
             data["amount"],
             data["payment_method"],
             tx_ref))
        pid = cursor.lastrowid

        # Step 2: mark fee_paid only for Passport (only table with fee_paid column)
        if data.get("passport_app_id"):
            cursor.execute(
                "UPDATE Passport_Application SET fee_paid = 1 WHERE passport_app_id = %s",
                (data["passport_app_id"],))

        # Step 3: audit log
        cursor.execute(
            """INSERT INTO Audit_Log
               (officer_id, action_type, table_name, record_id, ip_address)
               VALUES (%s, 'INSERT', 'Payment_Transaction', %s, %s)""",
            (g.officer["officer_id"], pid, request.remote_addr))
        return pid

    pid = execute_transaction_custom(ops)

    # Post-commit notification (ACID satisfied before this runs)
    try:
        from utils.notifications import send_notification
        send_notification(
            citizen_id=data["citizen_id"],
            title="Payment Confirmed",
            message=f"Payment of PKR {data['amount']} for {data['service_type']} recorded.",
            notif_type="success",
            category="transaction"
        )
    except Exception:
        pass  # Notification failure must never fail the payment response

    return jsonify({"message": "Payment recorded", "payment_id": pid}), 201
