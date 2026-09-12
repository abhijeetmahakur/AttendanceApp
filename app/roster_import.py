"""Bulk student roster import from a CSV file (e.g. a Google Form export
like "Student Information Form (Responses)").

Column headers are matched flexibly (case/space/apostrophe-insensitive) so
small variations in how the form's headers were named don't break import:
  - a name-like column:           "Student's Full Name", "Name", ...
  - a roll-number-like column:    "Updated Student Roll Number", "Roll No", ...
  - a registration-number column: "Registration Number", "Reg No", ...

Matching an incoming row to an existing student (so re-running an import,
or importing a roster for students added before this feature existed,
enriches them instead of creating duplicates) is done ONLY by exact,
unambiguous identifiers - never by name, since names are typed
inconsistently (typos, spacing, capitalization) and a wrong name-based
match would silently merge two different people's data:
  1. an existing student's `registration_no` equals this row's, or
  2. an existing student's login `reg_no` equals this row's registration
     number or plain roll number (covers accounts created before roll
     number / registration number were split into their own columns).
Anything else becomes a new, unclaimed roster entry the student can claim
via sign-up.
"""

from . import models
from .validators import REGISTRATION_NO_RE

_NAME_KEYS = {"studentsfullname", "fullname", "name", "studentname"}
_ROLL_KEYS = {"updatedstudentrollnumber", "rollnumber", "rollno", "roll"}
_REG_KEYS = {"registrationnumber", "registrationno", "regno", "registration"}

_BLANK_LIKE = {"", "no", "na", "n/a", "none", "-", "nil"}


def _normalize_key(key):
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _find_column(fieldnames, candidates):
    normalized = {_normalize_key(f): f for f in fieldnames if f}
    for key in candidates:
        if key in normalized:
            return normalized[key]
    return None


def _build_existing_index():
    """All current students, indexed for exact-identifier matching. Roll
    numbers are also indexed with leading zeros stripped (DB rows created
    before this feature existed sometimes have reg_no='02' for roll 2,
    while a freshly-read CSV cell for the same roll is just '2') so both
    spellings resolve to the same student instead of creating a duplicate."""
    by_registration_no = {}
    by_reg_no = {}
    by_numeric_reg_no = {}
    for s in models.list_students():
        if s["registration_no"]:
            by_registration_no[s["registration_no"]] = s
        by_reg_no[s["reg_no"]] = s
        if s["reg_no"].isdigit():
            by_numeric_reg_no[str(int(s["reg_no"]))] = s
    return by_registration_no, by_reg_no, by_numeric_reg_no


def import_rows(rows, fieldnames, course):
    """rows: an iterable of dicts (as from csv.DictReader).
    Returns a summary dict: created, updated, skipped (rows NOT imported,
    each {row, name, reason}), and anomalies (rows that WERE imported but
    look off and are worth a manual glance, each {row, name, reason})."""
    name_col = _find_column(fieldnames, _NAME_KEYS)
    roll_col = _find_column(fieldnames, _ROLL_KEYS)
    reg_col = _find_column(fieldnames, _REG_KEYS)

    by_registration_no, by_reg_no, by_numeric_reg_no = _build_existing_index()

    created, updated, skipped, anomalies = 0, 0, [], []
    seen_registration_numbers = set()

    for i, row in enumerate(rows, start=1):
        name = (row.get(name_col) or "").strip() if name_col else ""
        roll_raw = (row.get(roll_col) or "").strip() if roll_col else ""
        reg_raw = (row.get(reg_col) or "").strip() if reg_col else ""

        if not name and not reg_raw:
            skipped.append({"row": i, "name": name or "(blank)", "reason": "no name or registration number"})
            continue

        roll_no = int(roll_raw) if roll_raw.isdigit() else None

        registration_no = reg_raw if reg_raw and reg_raw.lower() not in _BLANK_LIKE else ""
        if not registration_no:
            skipped.append({"row": i, "name": name or "(blank)", "reason": "missing registration number"})
            continue

        anomaly = None
        if not REGISTRATION_NO_RE.match(registration_no):
            anomaly = f"registration number {registration_no!r} isn't exactly 9 letters/digits - imported as-is"

        if registration_no in seen_registration_numbers:
            skipped.append({"row": i, "name": name, "reason": f"duplicate registration number {registration_no} within this file"})
            continue

        # Match an existing student by an unambiguous identifier only (never by name).
        existing = (
            by_registration_no.get(registration_no)
            or by_reg_no.get(registration_no)
            or (by_numeric_reg_no.get(str(roll_no)) if roll_no is not None else None)
        )

        if existing:
            models.update_student_roll_and_registration(existing["id"], roll_no, registration_no)
            updated += 1
        else:
            try:
                models.create_unclaimed_student(name or f"Roll {roll_no}", course, roll_no, registration_no)
                created += 1
            except Exception as exc:  # noqa: BLE001 - e.g. a race on the unique index
                skipped.append({"row": i, "name": name, "reason": f"could not be created ({exc})"})
                continue

        seen_registration_numbers.add(registration_no)
        if anomaly:
            anomalies.append({"row": i, "name": name, "reason": anomaly})

    return {"created": created, "updated": updated, "skipped": skipped, "anomalies": anomalies}
