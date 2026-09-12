import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # os.path.join discards BASE_DIR automatically if DATABASE_PATH is set to
    # an absolute path (e.g. a mounted persistent disk in production, such as
    # /data/attendance.db on Render) - only the relative default resolves
    # under the project directory, which is what local development wants.
    DATABASE_PATH = os.path.join(
        BASE_DIR, os.environ.get("DATABASE_PATH", "instance/attendance.db")
    )

    DEFAULT_ADMIN_USERNAME = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin123")

    ATTENDANCE_THRESHOLD = float(os.environ.get("ATTENDANCE_THRESHOLD", "75"))
    EXAM_ELIGIBILITY_THRESHOLD = float(os.environ.get("EXAM_ELIGIBILITY_THRESHOLD", "33"))

    UPLOAD_FOLDER = os.path.join(
        BASE_DIR, os.environ.get("UPLOAD_FOLDER", "instance/uploads")
    )
    MAX_ATTACHMENT_SIZE_MB = int(os.environ.get("MAX_ATTACHMENT_SIZE_MB", "5"))
    MAX_CONTENT_LENGTH = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024

    COLLEGE_NAME = os.environ.get("COLLEGE_NAME", "Attendance Management System")
    QR_DEFAULT_DURATION_MINUTES = int(os.environ.get("QR_DEFAULT_DURATION_MINUTES", "5"))

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = _bool(os.environ.get("MAIL_USE_TLS"), True)
    MAIL_USE_SSL = _bool(os.environ.get("MAIL_USE_SSL"), False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

    # If SMTP credentials are not configured, emails are logged to the
    # console instead of actually being sent, so the app still runs end to end.
    MAIL_SUPPRESS_SEND = not (MAIL_USERNAME and MAIL_PASSWORD)

    # WhatsApp (Twilio WhatsApp API) settings for absentee alerts and holiday
    # / substitution notices. If not configured, messages are logged to the
    # console instead of actually being sent (same fallback as email above).
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM")

    # S3-compatible cloud storage (Cloudflare R2, AWS S3, Backblaze B2, MinIO,
    # ...) for leave-request attachments. If not configured, attachments are
    # saved to UPLOAD_FOLDER on local disk instead, so the app still runs end
    # to end without this configured - but that only survives redeploys on
    # hosts with a real persistent disk attached.
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
    S3_BUCKET = os.environ.get("S3_BUCKET")
    S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY")
    S3_REGION = os.environ.get("S3_REGION", "auto")
