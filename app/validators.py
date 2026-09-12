"""Password policy for student accounts: alphanumeric characters plus a
defined set of special characters, with a minimum length and a required
mix of letters + digits."""

import re
import secrets
import string

SPECIAL_CHARS = "!@#$%^&*()_+-=.,?"
ALLOWED_PASSWORD_RE = re.compile(r"^[A-Za-z0-9" + re.escape(SPECIAL_CHARS) + r"]+$")
MIN_PASSWORD_LENGTH = 8


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
