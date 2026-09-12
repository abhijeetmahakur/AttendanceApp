from flask import current_app
from flask_mail import Mail, Message

from .attendance_calc import AttendanceSummary, summary_message

mail = Mail()


def init_app(app):
    mail.init_app(app)


def send_attendance_email(student, summary: AttendanceSummary):
    """Email a student their attendance stats after marking attendance.

    If SMTP credentials aren't configured (MAIL_SUPPRESS_SEND), Flask-Mail
    logs the message instead of sending it, so the feature still works
    end-to-end in a local/demo setup.
    """
    subject = f"Attendance update: {summary.percentage}% in {student['course']}"

    body = (
        f"Hi {student['name']},\n\n"
        f"You just marked attendance. Here is your updated summary:\n\n"
        f"  Classes held so far : {summary.total_classes}\n"
        f"  Classes attended    : {summary.attended_classes}\n"
        f"  Attendance          : {summary.percentage}%\n"
        f"  Required minimum    : {summary.threshold:.0f}%\n\n"
        f"{summary_message(summary)}\n\n"
        f"- Attendance Management System"
    )

    msg = Message(
        subject=subject,
        recipients=[student["email"]],
        body=body,
        sender=current_app.config.get("MAIL_DEFAULT_SENDER"),
    )

    try:
        mail.send(msg)
    except Exception as exc:  # noqa: BLE001 - email failure shouldn't break attendance marking
        current_app.logger.warning("Failed to send attendance email to %s: %s", student["email"], exc)
        return False
    return True


def send_notice_email(student, notice):
    """Emails one student a holiday / substitution / general notice.
    Returns True on success, False on failure (never raises)."""
    category_label = {
        "holiday": "Holiday Notice",
        "substitution": "Class Substitution Notice",
        "general": "Notice",
    }.get(notice["category"], "Notice")

    msg = Message(
        subject=f"{category_label}: {notice['title']}",
        recipients=[student["email"]],
        body=(
            f"Hi {student['name']},\n\n"
            f"{notice['message']}\n\n"
            f"- {current_app.config.get('COLLEGE_NAME', 'Attendance Management System')}"
        ),
        sender=current_app.config.get("MAIL_DEFAULT_SENDER"),
    )

    try:
        mail.send(msg)
    except Exception as exc:  # noqa: BLE001 - one failed email shouldn't stop the rest of the notice run
        current_app.logger.warning("Failed to send notice email to %s: %s", student["email"], exc)
        return False
    return True
