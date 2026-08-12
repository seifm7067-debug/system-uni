import logging
from typing import Any

from app.services.notifications import send_notification_email

logger = logging.getLogger(__name__)


def process_background_notification(
    recipient: str, subject: str, body: str
) -> dict[str, Any]:
    logger.info("[WORKER] Processing background notification for %s", recipient)
    return send_notification_email(recipient, subject, body)


def process_async_report(report_type: str, target_id: int) -> dict[str, Any]:
    logger.info(
        "[WORKER] Processing async report of type '%s' for ID %d",
        report_type,
        target_id,
    )
    return {
        "status": "completed",
        "report_type": report_type,
        "target_id": target_id,
        "file_url": f"/reports/download/{report_type}_{target_id}.pdf",
    }
