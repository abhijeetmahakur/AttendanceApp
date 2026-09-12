"""Pure leave-request logic: the leave type list and inclusive day-count /
date validation shared by the student leave form and its server-side check."""

from datetime import datetime

LEAVE_TYPES = ["Holiday", "Personal", "Medical", "Other"]
LEAVE_STATUSES = ("pending", "approved", "rejected")

DATE_FMT = "%Y-%m-%d"


def parse_date(value):
    """Returns a date object, or None if value isn't a valid YYYY-MM-DD date."""
    try:
        return datetime.strptime(value, DATE_FMT).date()
    except (TypeError, ValueError):
        return None


def calculate_days(start, end):
    """Inclusive day count: a leave that starts and ends on the same day is 1 day."""
    return (end - start).days + 1


def validate_leave_dates(start_raw, end_raw):
    """Returns (is_valid, num_days, error_message)."""
    start = parse_date(start_raw)
    end = parse_date(end_raw)

    if not start or not end:
        return False, None, "Please provide valid start and end dates."

    if end < start:
        return False, None, "End date cannot be before the start date."

    return True, calculate_days(start, end), None


def leave_code(leave_id):
    """The student/admin-facing unique Leave Request ID."""
    return f"LR-{leave_id:06d}"
