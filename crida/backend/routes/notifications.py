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
    Store notification in DB + send email asynchronously.
    Called AFTER transaction commits (ACID durability confirmed).
    Non-blocking: a failure here never affects the calling route.
    """
    try:
        notif_id = execute_query(
            """INSERT INTO Notification
               (citizen_id, officer_id, title, message, notification_type, category)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (citizen_id, officer_id, title, message, notif_type, category)
        )
    except Exception as e:
        logger.error(f"Failed to store notification: {e}")
        return

    # Send email asynchronously if SMTP is configured
    if Config.SMTP_USER:
        threading.Thread(
            target=_send_email_async,
            args=(None, title, message, notif_id),
            daemon=True
        ).start()


def _send_email_async(to_email, subject, body, notif_id):
    """Non-blocking SMTP email. Marks email_sent=1 on success."""
    if not Config.SMTP_USER or not to_email:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"CRIDA — {subject}"
        msg["From"] = Config.SMTP_FROM
        msg["To"] = to_email
        html = f"""
        <html><body style="font-family:Arial;color:#1F4E79">
        <div style="background:#1F4E79;padding:16px;color:white">
            <h2>CRIDA Notification</h2>
        </div>
        <div style="padding:16px">
            <h3>{subject}</h3>
            <p>{body}</p>
            <hr/>
            <small style="color:gray">This is an automated message from CRIDA.</small>
        </div>
        </body></html>"""
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASS)
            server.send_message(msg)
        execute_query(
            "UPDATE Notification SET email_sent = 1 WHERE notification_id = %s",
            (notif_id,)
        )
        logger.info(f"Email sent to {to_email} for notification {notif_id}")
    except Exception as e:
        logger.warning(f"Email send failed (non-critical): {e}")
