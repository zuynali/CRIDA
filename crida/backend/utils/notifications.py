"""
utils/notifications.py — In-App Notifications + Optional SMTP Email
====================================================================
Uses Python's built-in smtplib (stdlib) — no third-party package needed.

send_notification() is called AFTER a transaction commits, so it never
blocks or rolls back the ACID transaction that triggered it.

Email is fire-and-forget in a daemon thread:
  - If SMTP_USER is not set in .env → silently skips email
  - If SMTP send fails → logs warning, does NOT raise
"""

import smtplib
import threading
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import Config
from db import execute_query

logger = logging.getLogger(__name__)


def send_notification(citizen_id=None, officer_id=None, title="",
                      message="", notif_type="info", category="system"):
    """
    Store a notification in the DB, then attempt email asynchronously.

    Called AFTER transaction commits (ACID durability confirmed).
    A failure here never affects the transaction that triggered it.
    """
    try:
        notif_id = execute_query(
            """INSERT INTO Notification
                   (citizen_id, officer_id, title, message,
                    notification_type, category)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (citizen_id, officer_id, title, message, notif_type, category)
        )
    except Exception as e:
        logger.error(f"Failed to store notification: {e}")
        return

    # Async email — only fires if SMTP is configured
    if Config.SMTP_USER:
        threading.Thread(
            target=_send_email_async,
            args=(title, message, notif_id),
            daemon=True
        ).start()


def _send_email_async(subject, body, notif_id):
    """Send email via stdlib smtplib with TLS. Marks email_sent=1 on success."""
    if not Config.SMTP_USER:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"CRIDA — {subject}"
        msg["From"]    = Config.SMTP_FROM
        msg["To"]      = Config.SMTP_USER   # Replace with citizen email when available

        html = f"""<html><body style="font-family:Arial;color:#1F4E79">
  <div style="background:#1F4E79;padding:16px;color:white"><h2>CRIDA Notification</h2></div>
  <div style="padding:16px">
    <h3>{subject}</h3><p>{body}</p>
    <hr/><small style="color:gray">Automated message from CRIDA.</small>
  </div>
</body></html>"""

        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html,  "html"))

        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASS)
            server.send_message(msg)

        execute_query(
            "UPDATE Notification SET email_sent = 1 WHERE notification_id = %s",
            (notif_id,)
        )
        logger.info(f"Email sent for notification {notif_id}")

    except Exception as e:
        logger.warning(f"Email send failed (non-critical): {e}")
