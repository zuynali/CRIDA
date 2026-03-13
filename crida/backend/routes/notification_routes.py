from flask import Blueprint, request, jsonify, g
from db import execute_query
from middleware.auth import token_required

notification_bp = Blueprint("notifications", __name__)

# Schema reference:
# Notification: notification_id, citizen_id, officer_id, title, message,
#               notification_type (info/success/warning/error),
#               category (transaction/document/security/system/appointment),
#               is_read, email_sent, created_at


@notification_bp.route("/", methods=["GET"])
@token_required
def list_notifications():
    cid = request.args.get("citizen_id")
    unread_only = request.args.get("unread") == "1"
    sql = "SELECT * FROM Notification WHERE 1=1"
    params = []
    if cid:
        sql += " AND citizen_id = %s"
        params.append(cid)
    if unread_only:
        sql += " AND is_read = 0"
    sql += " ORDER BY created_at DESC LIMIT 50"
    rows = execute_query(sql, params or None, fetch='all')
    return jsonify({"notifications": rows or []}), 200


@notification_bp.route("/<int:nid>/read", methods=["PUT"])
@token_required
def mark_read(nid):
    execute_query(
        "UPDATE Notification SET is_read = 1 WHERE notification_id = %s", (nid,))
    return jsonify({"message": "Marked as read"}), 200


@notification_bp.route("/unread-count", methods=["GET"])
@token_required
def unread_count():
    cid = request.args.get("citizen_id")
    if cid:
        row = execute_query(
            "SELECT COUNT(*) AS cnt FROM Notification WHERE citizen_id = %s AND is_read = 0",
            (cid,), fetch='one')
    else:
        row = execute_query(
            "SELECT COUNT(*) AS cnt FROM Notification WHERE is_read = 0",
            fetch='one')
    return jsonify({"unread_count": row["cnt"] if row else 0}), 200


@notification_bp.route("/send", methods=["POST"])
@token_required
def send_manual_notification():
    """Admin endpoint to manually send a notification."""
    from middleware.rbac import role_required
    from utils.notifications import send_notification
    from utils.validators import require_fields
    data = request.json or {}
    ok, err = require_fields(data, "title", "message")
    if not ok:
        return jsonify({"error": err}), 400

    send_notification(
        citizen_id=data.get("citizen_id"),
        officer_id=data.get("officer_id"),
        title=data["title"],
        message=data["message"],
        notif_type=data.get("notification_type", "info"),
        category=data.get("category", "system"))
    return jsonify({"message": "Notification sent"}), 201
