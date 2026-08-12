import logging

logger = logging.getLogger(__name__)


def send_notification_email(recipient_email: str, subject: str, body: str) -> dict:
    """Simulates sending notification emails asynchronously via Background Worker."""
    logger.info("Sending notification to %s | Subject: %s", recipient_email, subject)
    return {
        "status": "sent",
        "recipient": recipient_email,
        "subject": subject,
        "detail": body,
    }
