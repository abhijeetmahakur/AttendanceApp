"""Password policy for student accounts: alphanumeric characters plus a
defined set of special characters, with a minimum length and a required
mix of letters + digits."""

import re
import secrets
import string

SPECIAL_CHARS = "!@#$%^&*()_+-=.,?"
ALLOWED_PASSWORD_RE = re.compile(r"^[A-Za-z0-9" + re.escape(SPECIAL_CHARS) + r"]+$")
MIN_PASSWORD_LENGTH = 8

ALLOWED_ATTACHMENT_EXTENSIONS = {"pdf", "doc", "docx", "png", "jpg", "jpeg"}


def allowed_attachment_filename(filename):
    """Whether an uploaded leave-attachment filename has an accepted extension."""
    return bool(filename) and "." in filename and (
        filename.rsplit(".", 1)[1].lower() in ALLOWED_ATTACHMENT_EXTENSIONS
    )


def validate_password(password):
    """Returns (is_valid, error_message)."""
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."

    if not ALLOWED_PASSWORD_RE.match(password):
        return False, (
            "Password can only contain letters, numbers, and these special "
            f"characters: {SPECIAL_CHARS}"
        )

    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."

    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one digit."

    return True, None


REGISTRATION_NO_LENGTH = 9
REGISTRATION_NO_RE = re.compile(r"^[A-Za-z0-9]{9}$")


def validate_registration_no(value):
    """Returns (is_valid, error_message). The registration number is a
    fixed-length (9 character) alphanumeric college ID, distinct from the
    plain integer class roll number."""
    value = (value or "").strip()
    if not value:
        return False, "Registration number is required."
    if not REGISTRATION_NO_RE.match(value):
        return False, f"Registration number must be exactly {REGISTRATION_NO_LENGTH} letters/digits."
    return True, None


def validate_roll_no(value):
    """Returns (is_valid, roll_no_int_or_None, error_message). Blank is
    allowed (roll number is optional metadata); anything non-blank must be
    a plain positive integer."""
    value = (value or "").strip()
    if not value:
        return True, None, None
    if not value.isdigit():
        return False, None, "Roll number must be a whole number."
    return True, int(value), None


def generate_password(length=10):
    """Generates a random password that satisfies validate_password():
    a mix of letters, digits, and at least one special character."""
    length = max(length, MIN_PASSWORD_LENGTH)

    letters_and_digits = string.ascii_letters + string.digits
    password_chars = [
        secrets.choice(string.ascii_letters),
        secrets.choice(string.digits),
        secrets.choice(SPECIAL_CHARS),
    ]
    password_chars += [
        secrets.choice(letters_and_digits + SPECIAL_CHARS) for _ in range(length - len(password_chars))
    ]
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)
