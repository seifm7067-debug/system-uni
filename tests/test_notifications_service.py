import logging

import pytest
from app.services.notifications import send_notification_email
from app.workers.tasks import process_background_notification


def test_send_notification_email_success_returns_expected_structure():
    recipient = "student@example.com"
    subject = "Course Registration Confirmation"
    body = "You have successfully registered for CS101."

    result = send_notification_email(recipient, subject, body)

    assert isinstance(result, dict)
    assert result["status"] == "sent"
    assert result["recipient"] == recipient
    assert result["subject"] == subject
    assert result["detail"] == body


def test_send_notification_email_logs_recipient_and_subject(caplog):
    caplog.set_level(logging.INFO, logger="app.services.notifications")

    recipient = "faculty@example.com"
    subject = "Faculty Meeting"
    body = "Reminder: Meeting at 2 PM."

    send_notification_email(recipient, subject, body)

    assert any(
        "Sending notification to faculty@example.com | Subject: Faculty Meeting"
        in record.message
        for record in caplog.records
    )


@pytest.mark.parametrize(
    "recipient,subject,body",
    [
        ("", "", ""),
        (
            "طالب@جامعة.مصر",
            "إشعار تسجيل المواد",
            "تم تسجيلك بنجاح في الفصل الدراسي الأول.",
        ),
        (
            "user@test.org",
            "Long body test",
            "A" * 1000,
        ),
    ],
)
def test_send_notification_email_supports_various_payloads(recipient, subject, body):
    result = send_notification_email(recipient, subject, body)
    assert result["status"] == "sent"
    assert result["recipient"] == recipient
    assert result["subject"] == subject
    assert result["detail"] == body


def test_process_background_notification_worker_integration(caplog):
    caplog.set_level(logging.INFO)

    recipient = "worker_student@test.com"
    subject = "Background Task Alert"
    body = "Your report is ready."

    result = process_background_notification(recipient, subject, body)

    assert result["status"] == "sent"
    assert result["recipient"] == recipient
    assert result["subject"] == subject
    assert result["detail"] == body

    # Verify worker logging
    assert any(
        "[WORKER] Processing background notification for worker_student@test.com"
        in record.message
        for record in caplog.records
    )
