import secrets
import sqlite3
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

DT_FMT = "%Y-%m-%d %H:%M:%S"


def now_str():
    return datetime.now().strftime(DT_FMT)


# ---------- Admins ----------

def get_admin_by_username(username):
    db = get_db()
    return db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()


def get_admin_by_id(admin_id):
    db = get_db()
    return db.execute("SELECT * FROM admins WHERE id = ?", (admin_id,)).fetchone()


def verify_admin(username, password):
    admin = get_admin_by_username(username)
    if admin and check_password_hash(admin["password_hash"], password):
        return admin
    return None


def is_super_admin(admin_row):
    return admin_row is not None and admin_row["role"] == "super_admin"


def list_teachers():
    db = get_db()
    return db.execute("SELECT * FROM admins ORDER BY (role = 'super_admin') DESC, username").fetchall()


def create_teacher(username, password, email, phone):
    db = get_db()
    db.execute(
        """INSERT INTO admins (username, password_hash, role, email, phone)
           VALUES (?, ?, 'teacher', ?, ?)""",
        (username.strip(), generate_password_hash(password), (email or "").strip() or None, (phone or "").strip() or None),
    )
    db.commit()


def delete_teacher(admin_id):
    """Refuses to delete a super admin account (there must always be at
    least one way to fully administer the system). Returns True if a row
    was actually removed."""
    db = get_db()
    admin = get_admin_by_id(admin_id)
    if not admin or admin["role"] == "super_admin":
        return False
    db.execute("DELETE FROM admins WHERE id = ?", (admin_id,))
    db.commit()
    return True


def update_teacher_contact(admin_id, email, phone):
    db = get_db()
    db.execute(
        "UPDATE admins SET email = ?, phone = ? WHERE id = ?",
        ((email or "").strip() or None, (phone or "").strip() or None, admin_id),
    )
    db.commit()


# ---------- Teacher <-> subject assignments ----------

def list_subjects_for_teacher(teacher_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM teacher_subjects WHERE teacher_id = ? ORDER BY course, subject",
        (teacher_id,),
    ).fetchall()


def add_teacher_subject(teacher_id, subject, course):
    db = get_db()
    try:
        db.execute(
            "INSERT INTO teacher_subjects (teacher_id, subject, course) VALUES (?, ?, ?)",
            (teacher_id, subject.strip(), course.strip()),
        )
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def remove_teacher_subject(assignment_id, teacher_id=None):
    """If teacher_id is given, only removes the row when it belongs to that
    teacher (self-service edit); pass None to allow removing any row (super
    admin managing another teacher's assignments)."""
    db = get_db()
    if teacher_id is not None:
        db.execute(
            "DELETE FROM teacher_subjects WHERE id = ? AND teacher_id = ?",
            (assignment_id, teacher_id),
        )
    else:
        db.execute("DELETE FROM teacher_subjects WHERE id = ?", (assignment_id,))
    db.commit()


def teacher_can_manage(admin_row, subject, course):
    """Whether this admin account may create sessions/QR/absentee alerts
    for the given subject+course. Super admins can always do everything; a
    teacher needs a matching assignment, unless they have none at all yet
    (bootstrapping: a brand new teacher account isn't locked out before
    anyone has assigned them anything)."""
    if is_super_admin(admin_row):
        return True
    db = get_db()
    assignments = db.execute(
        "SELECT 1 FROM teacher_subjects WHERE teacher_id = ?", (admin_row["id"],)
    ).fetchall()
    if not assignments:
        return True
    match = db.execute(
        """SELECT 1 FROM teacher_subjects
           WHERE teacher_id = ? AND subject = ? COLLATE NOCASE AND course = ? COLLATE NOCASE""",
        (admin_row["id"], subject, course),
    ).fetchone()
    return match is not None


# ---------- Students ----------

def get_student_by_id(student_id):
    db = get_db()
    return db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()


def get_student_by_reg_no(reg_no):
    db = get_db()
    return db.execute("SELECT * FROM students WHERE reg_no = ?", (reg_no,)).fetchone()


def get_student_by_registration_no(registration_no):
    db = get_db()
    return db.execute(
        "SELECT * FROM students WHERE registration_no = ?", (registration_no,)
    ).fetchone()


def verify_student(reg_no, password):
    """Only succeeds for an 'active' account - a pre-imported roster entry
    that hasn't signed up yet ('unclaimed') or is awaiting teacher approval
    ('pending') can't log in even if some password were guessed, since its
    password_hash is an unusable random placeholder until signup sets a
    real one and a teacher approves it."""
    student = get_student_by_reg_no(reg_no)
    if student and student["account_status"] == "active" and check_password_hash(student["password_hash"], password):
        return student
    return None


def list_students(course=None):
    """Ordered by roll number (numeric, ascending) rather than the login ID
    text field, which mixes plain roll-number strings with full 9-character
    registration numbers and so sorts inconsistently. Students without a
    roll number on file yet are listed last, by name. When listing every
    course together, course is still the primary grouping so one section's
    roll numbers don't interleave with another's."""
    db = get_db()
    roll_order = "(roll_no IS NULL), roll_no, name COLLATE NOCASE"
    if course:
        return db.execute(
            f"SELECT * FROM students WHERE course = ? COLLATE NOCASE ORDER BY {roll_order}", (course,)
        ).fetchall()
    return db.execute(f"SELECT * FROM students ORDER BY course, {roll_order}").fetchall()


def create_student(reg_no, name, email, course, password, phone=None, roll_no=None, registration_no=None):
    db = get_db()
    db.execute(
        """INSERT INTO students
               (reg_no, name, email, phone, course, password_hash, roll_no, registration_no, account_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
        (
            reg_no.strip(), name.strip(), email.strip(), (phone or "").strip() or None,
            course.strip(), generate_password_hash(password), roll_no,
            (registration_no or "").strip() or None,
        ),
    )
    db.commit()


def create_unclaimed_student(name, course, roll_no=None, registration_no=None):
    """Pre-populates a roster entry (e.g. from a bulk CSV import) with no
    password yet. The account can't log in (account_status='unclaimed',
    password_hash is an unusable random placeholder) until the student
    signs up themselves and a teacher approves it."""
    db = get_db()
    placeholder_hash = generate_password_hash(secrets.token_urlsafe(32))
    reg_no = (registration_no or "").strip()
    db.execute(
        """INSERT INTO students
               (reg_no, name, email, course, password_hash, roll_no, registration_no, account_status)
           VALUES (?, ?, '', ?, ?, ?, ?, 'unclaimed')""",
        (reg_no, name.strip(), course.strip(), placeholder_hash, roll_no, reg_no or None),
    )
    db.commit()


def delete_student(student_id):
    db = get_db()
    db.execute("DELETE FROM students WHERE id = ?", (student_id,))
    db.commit()


def update_student(student_id, reg_no, name, email, course, phone=None, roll_no=None, registration_no=None):
    db = get_db()
    db.execute(
        """UPDATE students SET reg_no = ?, name = ?, email = ?, course = ?, phone = ?,
               roll_no = ?, registration_no = ?
           WHERE id = ?""",
        (
            reg_no.strip(), name.strip(), email.strip(), course.strip(), (phone or "").strip() or None,
            roll_no, (registration_no or "").strip() or None, student_id,
        ),
    )
    db.commit()


def update_student_roll_and_registration(student_id, roll_no, registration_no):
    """Enrichment-only update used by the roster CSV import: fills in the
    roll number / registration number for an existing student without
    touching their login (reg_no), password, email, or anything else."""
    db = get_db()
    db.execute(
        "UPDATE students SET roll_no = ?, registration_no = ? WHERE id = ?",
        (roll_no, (registration_no or "").strip() or None, student_id),
    )
    db.commit()


def reg_no_taken_by_other(reg_no, student_id):
    db = get_db()
    row = db.execute(
        "SELECT 1 FROM students WHERE reg_no = ? AND id != ?", (reg_no.strip(), student_id)
    ).fetchone()
    return row is not None


def registration_no_taken_by_other(registration_no, student_id):
    db = get_db()
    row = db.execute(
        "SELECT 1 FROM students WHERE registration_no = ? AND id != ?",
        (registration_no.strip(), student_id),
    ).fetchone()
    return row is not None


# ---------- Student self sign-up (claiming a pre-imported roster entry) ----------

def student_signup(registration_no, password, email, phone):
    """Returns (status, student_row_or_None):
    status is 'ok', 'not_found', 'already_active', or 'already_pending'."""
    student = get_student_by_registration_no(registration_no.strip())
    if not student:
        return "not_found", None
    if student["account_status"] == "active":
        return "already_active", student
    if student["account_status"] == "pending":
        return "already_pending", student

    db = get_db()
    db.execute(
        """UPDATE students
           SET password_hash = ?, email = ?, phone = ?, account_status = 'pending'
           WHERE id = ?""",
        (generate_password_hash(password), email.strip(), (phone or "").strip() or None, student["id"]),
    )
    db.commit()
    return "ok", get_student_by_id(student["id"])


def list_pending_signups():
    db = get_db()
    return db.execute(
        "SELECT * FROM students WHERE account_status = 'pending' ORDER BY name"
    ).fetchall()


def approve_signup(student_id):
    db = get_db()
    db.execute("UPDATE students SET account_status = 'active' WHERE id = ?", (student_id,))
    db.commit()


def reject_signup(student_id):
    """Sends the account back to 'unclaimed' with a fresh unusable
    placeholder password, so the student can try signing up again
    (e.g. after fixing a typo) rather than being permanently stuck."""
    db = get_db()
    placeholder_hash = generate_password_hash(secrets.token_urlsafe(32))
    db.execute(
        "UPDATE students SET account_status = 'unclaimed', password_hash = ? WHERE id = ?",
        (placeholder_hash, student_id),
    )
    db.commit()


def set_student_password(student_id, new_password):
    db = get_db()
    db.execute(
        "UPDATE students SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), student_id),
    )
    db.commit()


def distinct_courses():
    db = get_db()
    rows = db.execute(
        "SELECT course FROM students UNION SELECT course FROM class_sessions"
    ).fetchall()
    # Courses are matched case-insensitively everywhere else, so dedupe the
    # same way here (keeping the first-seen casing) instead of listing
    # "CSE" and "cse" as two different courses.
    seen = {}
    for r in rows:
        key = r["course"].lower()
        seen.setdefault(key, r["course"])
    return sorted(seen.values(), key=str.lower)


def distinct_subjects():
    db = get_db()
    rows = db.execute("SELECT DISTINCT subject FROM class_sessions ORDER BY subject COLLATE NOCASE").fetchall()
    return [r["subject"] for r in rows]


def distinct_timetable_subjects():
    """The canonical subject list for the 'Subject' dropdown when creating a
    class session or QR attendance session - sourced from the timetable
    itself (Admin > Timetable), so it always matches whatever subjects are
    actually scheduled rather than letting free text drift out of sync.

    A lab slot for the same subject (e.g. "Computer Networking: Concepts
    (Lab)" alongside the lecture "Computer Networking: Concepts") is folded
    into one entry keyed by subject_code with any " LAB" suffix stripped,
    so the dropdown offers one option per subject rather than a separate
    one for its lab session."""
    db = get_db()
    rows = db.execute(
        """SELECT DISTINCT subject_name, subject_code FROM timetable_entries
           WHERE subject_name IS NOT NULL AND subject_name != ''
           ORDER BY subject_name COLLATE NOCASE"""
    ).fetchall()

    by_code = {}
    for r in rows:
        code = (r["subject_code"] or "").strip()
        key = code.upper().removesuffix(" LAB") or r["subject_name"]
        is_lab = code.upper().endswith(" LAB")
        existing = by_code.get(key)
        # Prefer the lecture entry's (shorter, non-lab) name if both exist.
        if existing is None or (existing["is_lab"] and not is_lab):
            by_code[key] = {"subject_name": r["subject_name"], "subject_code": key, "is_lab": is_lab}

    return sorted(by_code.values(), key=lambda r: r["subject_name"].lower())


def total_students():
    db = get_db()
    return db.execute("SELECT COUNT(*) AS c FROM students").fetchone()["c"]


# ---------- Class sessions (attendance windows) ----------

def create_session(subject, course, session_date, start_at, end_at, admin_id):
    db = get_db()
    db.execute(
        """INSERT INTO class_sessions (subject, course, session_date, start_at, end_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (subject.strip(), course.strip(), session_date, start_at, end_at, admin_id),
    )
    db.commit()


def delete_session(session_id):
    db = get_db()
    db.execute("DELETE FROM class_sessions WHERE id = ?", (session_id,))
    db.commit()


def get_session_by_id(session_id):
    db = get_db()
    return db.execute("SELECT * FROM class_sessions WHERE id = ?", (session_id,)).fetchone()


def list_sessions(course=None):
    db = get_db()
    if course:
        return db.execute(
            "SELECT * FROM class_sessions WHERE course = ? COLLATE NOCASE ORDER BY start_at DESC", (course,)
        ).fetchall()
    return db.execute("SELECT * FROM class_sessions ORDER BY start_at DESC").fetchall()


def session_status(session_row, at=None):
    """Returns 'upcoming' | 'open' | 'closed' relative to `at` (default: now)."""
    at = at or now_str()
    if at < session_row["start_at"]:
        return "upcoming"
    if at > session_row["end_at"]:
        return "closed"
    return "open"


def count_sessions_for_course(course, up_to=None):
    db = get_db()
    up_to = up_to or now_str()
    return db.execute(
        "SELECT COUNT(*) AS c FROM class_sessions WHERE course = ? COLLATE NOCASE AND start_at <= ?",
        (course, up_to),
    ).fetchone()["c"]


def total_classes():
    db = get_db()
    return db.execute("SELECT COUNT(*) AS c FROM class_sessions").fetchone()["c"]


def classes_conducted(up_to=None):
    db = get_db()
    up_to = up_to or now_str()
    return db.execute(
        "SELECT COUNT(*) AS c FROM class_sessions WHERE start_at <= ?", (up_to,)
    ).fetchone()["c"]


# ---------- Attendance ----------

def has_marked(session_id, student_id):
    db = get_db()
    row = db.execute(
        "SELECT 1 FROM attendance WHERE session_id = ? AND student_id = ?",
        (session_id, student_id),
    ).fetchone()
    return row is not None


def mark_attendance(session_id, student_id):
    db = get_db()
    db.execute(
        "INSERT INTO attendance (session_id, student_id, marked_at) VALUES (?, ?, ?)",
        (session_id, student_id, now_str()),
    )
    db.commit()


def count_attendance_for_student(student_id, course=None):
    db = get_db()
    if course:
        return db.execute(
            """SELECT COUNT(*) AS c FROM attendance a
               JOIN class_sessions s ON s.id = a.session_id
               WHERE a.student_id = ? AND s.course = ? COLLATE NOCASE""",
            (student_id, course),
        ).fetchone()["c"]
    return db.execute(
        "SELECT COUNT(*) AS c FROM attendance WHERE student_id = ?", (student_id,)
    ).fetchone()["c"]


def attendance_history_for_student(student_id):
    db = get_db()
    return db.execute(
        """SELECT s.subject, s.course, s.session_date, s.start_at, a.marked_at
           FROM attendance a
           JOIN class_sessions s ON s.id = a.session_id
           WHERE a.student_id = ?
           ORDER BY s.start_at DESC""",
        (student_id,),
    ).fetchall()


def subject_wise_attendance_for_student(student_id, course, up_to=None):
    """Per-subject totals for one student: how many classes have been held
    in each subject of their course, and how many they attended."""
    db = get_db()
    up_to = up_to or now_str()
    return db.execute(
        """SELECT s.subject,
                  COUNT(DISTINCT s.id) AS total,
                  COUNT(DISTINCT a.id) AS attended
           FROM class_sessions s
           LEFT JOIN attendance a ON a.session_id = s.id AND a.student_id = ?
           WHERE s.course = ? COLLATE NOCASE AND s.start_at <= ?
           GROUP BY s.subject
           ORDER BY s.subject COLLATE NOCASE""",
        (student_id, course, up_to),
    ).fetchall()


def attendance_matrix(course=None, subject=None, student_id=None, start_date=None, end_date=None):
    """One row per (student, class session held for their course) pair, with
    an `attended` flag - the raw material for every admin statistics view
    (by student, by subject, by month) without repeated N+1 queries."""
    db = get_db()
    query = """
        SELECT st.id AS student_id, st.reg_no, st.roll_no, st.registration_no, st.name, st.course,
               s.id AS session_id, s.subject, s.session_date,
               CASE WHEN a.id IS NULL THEN 0 ELSE 1 END AS attended
        FROM students st
        JOIN class_sessions s ON s.course = st.course COLLATE NOCASE AND s.start_at <= ?
        LEFT JOIN attendance a ON a.session_id = s.id AND a.student_id = st.id
        WHERE 1 = 1
    """
    params = [now_str()]
    if course:
        query += " AND st.course = ? COLLATE NOCASE"
        params.append(course)
    if subject:
        query += " AND s.subject = ?"
        params.append(subject)
    if student_id:
        query += " AND st.id = ?"
        params.append(student_id)
    if start_date:
        query += " AND s.session_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND s.session_date <= ?"
        params.append(end_date)

    return db.execute(query, params).fetchall()


def attendees_for_session(session_id):
    db = get_db()
    return db.execute(
        """SELECT st.reg_no, st.roll_no, st.registration_no, st.name, a.marked_at
           FROM attendance a
           JOIN students st ON st.id = a.student_id
           WHERE a.session_id = ?
           ORDER BY a.marked_at""",
        (session_id,),
    ).fetchall()


def open_sessions_for_course(course):
    """Manually-created attendance windows only - QR-generated sessions are
    marked via the QR scan flow, not the plain "Mark Attendance" button, so
    scanning stays the only way in for those."""
    db = get_db()
    at = now_str()
    return db.execute(
        """SELECT * FROM class_sessions
           WHERE course = ? COLLATE NOCASE AND ? BETWEEN start_at AND end_at
             AND source = 'manual'
           ORDER BY start_at""",
        (course, at),
    ).fetchall()


# ---------- Leave requests ----------

def create_leave_request(
    student_id, leave_type, start_date, end_date, num_days, reason,
    attachment_path=None, attachment_name=None,
):
    db = get_db()
    cur = db.execute(
        """INSERT INTO leave_requests
               (student_id, leave_type, start_date, end_date, num_days, reason,
                attachment_path, attachment_name, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (
            student_id, leave_type.strip(), start_date, end_date, num_days, reason.strip(),
            attachment_path, attachment_name, now_str(),
        ),
    )
    db.commit()
    return cur.lastrowid


def get_leave_request(leave_id):
    db = get_db()
    return db.execute("SELECT * FROM leave_requests WHERE id = ?", (leave_id,)).fetchone()


def list_leave_requests_for_student(student_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM leave_requests WHERE student_id = ? ORDER BY created_at DESC, id DESC",
        (student_id,),
    ).fetchall()


def list_leave_requests(status=None):
    db = get_db()
    query = (
        """SELECT lr.*, st.name AS student_name, st.reg_no, st.course
           FROM leave_requests lr JOIN students st ON st.id = lr.student_id"""
    )
    params = ()
    if status:
        query += " WHERE lr.status = ?"
        params = (status,)
    query += " ORDER BY lr.created_at DESC, lr.id DESC"
    return db.execute(query, params).fetchall()


def leave_summary_for_student(student_id):
    db = get_db()
    rows = db.execute(
        "SELECT status, COUNT(*) AS c FROM leave_requests WHERE student_id = ? GROUP BY status",
        (student_id,),
    ).fetchall()
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    for r in rows:
        counts[r["status"]] = r["c"]
    counts["total"] = sum(counts.values())
    return counts


def leave_status_counts():
    db = get_db()
    rows = db.execute("SELECT status, COUNT(*) AS c FROM leave_requests GROUP BY status").fetchall()
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    for r in rows:
        counts[r["status"]] = r["c"]
    counts["total"] = sum(counts.values())
    return counts


def decide_leave_request(leave_id, status, admin_comment, reviewed_by):
    db = get_db()
    db.execute(
        """UPDATE leave_requests
           SET status = ?, admin_comment = ?, reviewed_by = ?, reviewed_at = ?
           WHERE id = ?""",
        (status, (admin_comment or "").strip() or None, reviewed_by, now_str(), leave_id),
    )
    db.commit()


# ---------- QR attendance sessions ----------

def create_qr_session(subject, course, session_date, lecture, start_at, end_at, code, admin_id):
    db = get_db()
    cur = db.execute(
        """INSERT INTO class_sessions
               (subject, course, session_date, start_at, end_at, lecture, source, created_by)
           VALUES (?, ?, ?, ?, ?, ?, 'qr', ?)""",
        (subject.strip(), course.strip(), session_date, start_at, end_at, lecture, admin_id),
    )
    class_session_id = cur.lastrowid
    db.execute(
        "INSERT INTO qr_sessions (session_id, code, created_by) VALUES (?, ?, ?)",
        (class_session_id, code, admin_id),
    )
    db.commit()
    return class_session_id


_QR_SELECT = """
    SELECT q.id AS qr_id, q.code, q.created_by, q.created_at AS qr_created_at,
           s.id AS session_id, s.subject, s.course, s.session_date,
           s.start_at, s.end_at, s.lecture
    FROM qr_sessions q JOIN class_sessions s ON s.id = q.session_id
"""


def get_qr_session_by_code(code):
    db = get_db()
    return db.execute(_QR_SELECT + " WHERE q.code = ?", (code,)).fetchone()


def get_qr_session(qr_id):
    db = get_db()
    return db.execute(_QR_SELECT + " WHERE q.id = ?", (qr_id,)).fetchone()


def list_qr_sessions(limit=25):
    db = get_db()
    return db.execute(_QR_SELECT + " ORDER BY q.created_at DESC LIMIT ?", (limit,)).fetchall()


# ---------- Notifications ----------

def create_notification(student_id, category, message):
    db = get_db()
    db.execute(
        "INSERT INTO notifications (student_id, category, message, created_at) VALUES (?, ?, ?, ?)",
        (student_id, category, message, now_str()),
    )
    db.commit()


def list_notifications_for_student(student_id, limit=30):
    db = get_db()
    return db.execute(
        "SELECT * FROM notifications WHERE student_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
        (student_id, limit),
    ).fetchall()


def unread_notification_count(student_id):
    db = get_db()
    return db.execute(
        "SELECT COUNT(*) AS c FROM notifications WHERE student_id = ? AND read_at IS NULL",
        (student_id,),
    ).fetchone()["c"]


def mark_notifications_read(student_id):
    db = get_db()
    db.execute(
        "UPDATE notifications SET read_at = ? WHERE student_id = ? AND read_at IS NULL",
        (now_str(), student_id),
    )
    db.commit()


# ---------- WhatsApp groups ----------
# A "group" here is our own saved list of phone numbers for a class/section
# (e.g. a class representative, a parents' group admin, or several parent
# numbers) - see app/whatsapp.py for why this isn't a native WhatsApp group.

def create_whatsapp_group(name, course, created_by):
    db = get_db()
    cur = db.execute(
        "INSERT INTO whatsapp_groups (name, course, created_by) VALUES (?, ?, ?)",
        (name.strip(), course.strip(), created_by),
    )
    db.commit()
    return cur.lastrowid


def list_whatsapp_groups(course=None):
    db = get_db()
    if course:
        return db.execute(
            "SELECT * FROM whatsapp_groups WHERE course = ? COLLATE NOCASE ORDER BY name", (course,)
        ).fetchall()
    return db.execute("SELECT * FROM whatsapp_groups ORDER BY course, name").fetchall()


def get_whatsapp_group(group_id):
    db = get_db()
    return db.execute("SELECT * FROM whatsapp_groups WHERE id = ?", (group_id,)).fetchone()


def delete_whatsapp_group(group_id):
    db = get_db()
    db.execute("DELETE FROM whatsapp_groups WHERE id = ?", (group_id,))
    db.commit()


def add_group_member(group_id, label, phone_number):
    db = get_db()
    db.execute(
        "INSERT INTO whatsapp_group_members (group_id, label, phone_number) VALUES (?, ?, ?)",
        (group_id, label.strip(), phone_number.strip()),
    )
    db.commit()


def remove_group_member(member_id):
    db = get_db()
    db.execute("DELETE FROM whatsapp_group_members WHERE id = ?", (member_id,))
    db.commit()


def list_group_members(group_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM whatsapp_group_members WHERE group_id = ? ORDER BY label", (group_id,)
    ).fetchall()


# ---------- Holidays ----------

def list_holidays():
    db = get_db()
    return db.execute("SELECT * FROM holidays ORDER BY holiday_date").fetchall()


def create_holiday(name, holiday_date, day_of_week, category):
    db = get_db()
    db.execute(
        "INSERT INTO holidays (name, holiday_date, day_of_week, category) VALUES (?, ?, ?, ?)",
        (name.strip(), holiday_date, day_of_week.strip(), category),
    )
    db.commit()


def delete_holiday(holiday_id):
    db = get_db()
    db.execute("DELETE FROM holidays WHERE id = ?", (holiday_id,))
    db.commit()


# Transcribed from the institution's official 2026 holiday list circular.
_HOLIDAY_SEED = [
    ("Republic Day", "2026-01-26", "Monday", "mandatory"),
    ("Holi", "2026-03-04", "Wednesday", "mandatory"),
    ("Good Friday", "2026-04-03", "Friday", "mandatory"),
    ("Id-ul-Zuha", "2026-05-27", "Wednesday", "mandatory"),
    ("Rath Yatra", "2026-07-16", "Thursday", "mandatory"),
    ("Independence Day", "2026-08-15", "Saturday", "mandatory"),
    ("Janmasthami", "2026-09-04", "Friday", "mandatory"),
    ("Ganesh Puja", "2026-09-14", "Monday", "mandatory"),
    ("Gandhi Jayanti", "2026-10-02", "Friday", "mandatory"),
    ("Maha Navami", "2026-10-19", "Monday", "mandatory"),
    ("Vijaya Dasami", "2026-10-20", "Tuesday", "mandatory"),
    ("X-Mass Day", "2026-12-25", "Friday", "mandatory"),
    ("Dola Purnima", "2026-03-03", "Tuesday", "optional"),
    ("Id-Ul-Fitre", "2026-03-21", "Saturday", "optional"),
    ("Maha Bisuva Sankranti", "2026-04-14", "Tuesday", "optional"),
    ("Budha Purnima", "2026-05-01", "Friday", "optional"),
    ("Sabitri Amabasya", "2026-05-16", "Saturday", "optional"),
    ("Raja Sankranti", "2026-06-15", "Monday", "optional"),
    ("Moharram", "2026-06-26", "Friday", "optional"),
    ("Bahuda Yatra", "2026-07-24", "Friday", "optional"),
    ("Nuakhai", "2026-09-15", "Tuesday", "optional"),
    ("Prathamastami", "2026-12-01", "Tuesday", "optional"),
]


def seed_holidays_if_empty():
    db = get_db()
    if db.execute("SELECT 1 FROM holidays LIMIT 1").fetchone():
        return
    db.executemany(
        "INSERT INTO holidays (name, holiday_date, day_of_week, category) VALUES (?, ?, ?, ?)",
        _HOLIDAY_SEED,
    )
    db.commit()


# ---------- Timetable ----------

_DAY_ORDER = "CASE day_of_week " + " ".join(
    f"WHEN '{d}' THEN {i}" for i, d in enumerate(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    )
) + " ELSE 99 END"


def list_timetable(course=None):
    db = get_db()
    query = f"SELECT * FROM timetable_entries"
    params = ()
    if course:
        query += " WHERE course = ? COLLATE NOCASE"
        params = (course,)
    query += f" ORDER BY {_DAY_ORDER}, start_time"
    return db.execute(query, params).fetchall()


def distinct_timetable_courses():
    db = get_db()
    rows = db.execute("SELECT DISTINCT course FROM timetable_entries ORDER BY course").fetchall()
    return [r["course"] for r in rows]


def get_timetable_entry(entry_id):
    db = get_db()
    return db.execute("SELECT * FROM timetable_entries WHERE id = ?", (entry_id,)).fetchone()


def create_timetable_entry(course, semester_label, room, day_of_week, start_time, end_time,
                            subject_code, subject_name, faculty, created_by):
    db = get_db()
    db.execute(
        """INSERT INTO timetable_entries
               (course, semester_label, room, day_of_week, start_time, end_time,
                subject_code, subject_name, faculty, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            course.strip(), (semester_label or "").strip() or None, (room or "").strip() or None,
            day_of_week, start_time, end_time, (subject_code or "").strip() or None,
            subject_name.strip(), (faculty or "").strip() or None, created_by,
        ),
    )
    db.commit()


def update_timetable_entry(entry_id, course, semester_label, room, day_of_week, start_time, end_time,
                            subject_code, subject_name, faculty):
    db = get_db()
    db.execute(
        """UPDATE timetable_entries
           SET course = ?, semester_label = ?, room = ?, day_of_week = ?, start_time = ?, end_time = ?,
               subject_code = ?, subject_name = ?, faculty = ?
           WHERE id = ?""",
        (
            course.strip(), (semester_label or "").strip() or None, (room or "").strip() or None,
            day_of_week, start_time, end_time, (subject_code or "").strip() or None,
            subject_name.strip(), (faculty or "").strip() or None, entry_id,
        ),
    )
    db.commit()


def delete_timetable_entry(entry_id):
    db = get_db()
    db.execute("DELETE FROM timetable_entries WHERE id = ?", (entry_id,))
    db.commit()


# Transcribed from the institution's official 5th-Semester B.Tech (Section
# 24E1G2, Odd Semester 2026) timetable circular. Lab sessions that span two
# consecutive periods are stored as one longer entry rather than two rows.
_TIMETABLE_SECTION = "24E1G2"
_TIMETABLE_SEMESTER = "5th Semester B.Tech - Odd Semester 2026"
_TIMETABLE_ROOM = "C-111"
_TIMETABLE_LAB_ROOM = "C-021"

_TIMETABLE_SEED = [
    # (day, start, end, subject_code, subject_name, faculty, room)
    ("Monday", "13:50", "14:50", "IPS1", "Intermediate Problem Solving - 1", "Venkatash Dalei", _TIMETABLE_ROOM),
    ("Monday", "14:50", "15:50", "FMI1", "Fundamentals of Machine Intelligence 1", "Ambarish Giri", _TIMETABLE_ROOM),
    ("Monday", "15:50", "16:50", "ITC", "Introduction to the Theory of Computation", "Pramod Kumar Sethy", _TIMETABLE_ROOM),
    ("Monday", "16:50", "17:50", "PPWC", "Practical Programming with C", "Shahid Afridi Saikia", _TIMETABLE_ROOM),

    ("Tuesday", "13:50", "14:50", "IPS1", "Intermediate Problem Solving - 1", "Venkatash Dalei", _TIMETABLE_ROOM),
    ("Tuesday", "14:50", "15:50", "DPOS", "Design Principles of Operating Systems", "Madhushree Kunar", _TIMETABLE_ROOM),
    ("Tuesday", "15:50", "16:50", "CN", "Computer Networking: Concepts", "Jagadish Ch Padhi", _TIMETABLE_ROOM),
    ("Tuesday", "16:50", "18:50", "MLC1", "Machine Learning Concepts 1", "Siba Prasad Pati", _TIMETABLE_LAB_ROOM),

    ("Wednesday", "13:50", "14:50", "IPS1", "Intermediate Problem Solving - 1", "Venkatash Dalei", _TIMETABLE_ROOM),
    ("Wednesday", "14:50", "16:50", "PPWC LAB", "Practical Programming with C (Lab)", "Shahid Afridi Saikia", _TIMETABLE_LAB_ROOM),
    ("Wednesday", "16:50", "18:50", "CN LAB", "Computer Networking: Concepts (Lab)", "Jagadish Ch Padhi", _TIMETABLE_LAB_ROOM),

    ("Thursday", "08:00", "10:00", "MLC1", "Machine Learning Concepts 1", "Siba Prasad Pati", _TIMETABLE_LAB_ROOM),
    ("Thursday", "10:00", "11:00", "CN", "Computer Networking: Concepts", "Jagadish Ch Padhi", _TIMETABLE_ROOM),
    ("Thursday", "11:00", "12:00", "DPOS", "Design Principles of Operating Systems", "Madhushree Kunar", _TIMETABLE_ROOM),
    ("Thursday", "12:00", "13:00", "FMI1", "Fundamentals of Machine Intelligence 1", "Ambarish Giri", _TIMETABLE_ROOM),

    ("Friday", "08:00", "09:00", "ITC", "Introduction to the Theory of Computation", "Pramod Kumar Sethy", _TIMETABLE_ROOM),
    ("Friday", "09:00", "10:00", "FMI1", "Fundamentals of Machine Intelligence 1", "Ambarish Giri", _TIMETABLE_ROOM),
    ("Friday", "10:00", "11:00", "PPWC", "Practical Programming with C", "Shahid Afridi Saikia", _TIMETABLE_ROOM),
    ("Friday", "11:00", "13:00", "DPOS LAB", "Design Principles of Operating Systems (Lab)", "Madhushree Kunar", _TIMETABLE_LAB_ROOM),

    ("Saturday", "08:00", "10:00", "PPWC LAB", "Practical Programming with C (Lab)", "Shahid Afridi Saikia", _TIMETABLE_LAB_ROOM),
    ("Saturday", "10:00", "11:00", "DPOS", "Design Principles of Operating Systems", "Madhushree Kunar", _TIMETABLE_ROOM),
    ("Saturday", "11:00", "12:00", "CN", "Computer Networking: Concepts", "Jagadish Ch Padhi", _TIMETABLE_ROOM),
    ("Saturday", "12:00", "13:00", "ITC", "Introduction to the Theory of Computation", "Pramod Kumar Sethy", _TIMETABLE_ROOM),
]


def seed_timetable_if_empty():
    db = get_db()
    if db.execute("SELECT 1 FROM timetable_entries LIMIT 1").fetchone():
        return
    admin = db.execute("SELECT id FROM admins ORDER BY id LIMIT 1").fetchone()
    created_by = admin["id"] if admin else None
    if created_by is None:
        return  # no admin exists yet to attribute the seed rows to
    rows = [
        (_TIMETABLE_SECTION, _TIMETABLE_SEMESTER, room, day, start, end, code, name, faculty, created_by)
        for day, start, end, code, name, faculty, room in _TIMETABLE_SEED
    ]
    db.executemany(
        """INSERT INTO timetable_entries
               (course, semester_label, room, day_of_week, start_time, end_time,
                subject_code, subject_name, faculty, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    db.commit()


# ---------- Notices (holiday / substitution / general announcements) ----------

def create_notice(title, message, category, course, created_by):
    db = get_db()
    cur = db.execute(
        """INSERT INTO notices (title, message, category, course, created_by)
           VALUES (?, ?, ?, ?, ?)""",
        (title.strip(), message.strip(), category, (course or "").strip() or None, created_by),
    )
    db.commit()
    return cur.lastrowid


def list_notices(course=None, limit=50):
    """Notices scoped to `course` also include course-less (all-course)
    notices, since those are meant for every student regardless of section."""
    db = get_db()
    if course:
        return db.execute(
            """SELECT * FROM notices WHERE course IS NULL OR course = ? COLLATE NOCASE
               ORDER BY created_at DESC LIMIT ?""",
            (course, limit),
        ).fetchall()
    return db.execute("SELECT * FROM notices ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()


def get_notice(notice_id):
    db = get_db()
    return db.execute("SELECT * FROM notices WHERE id = ?", (notice_id,)).fetchone()


def delete_notice(notice_id):
    db = get_db()
    db.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
    db.commit()


def set_notice_send_counts(notice_id, email_count, whatsapp_count):
    db = get_db()
    db.execute(
        "UPDATE notices SET email_sent_count = ?, whatsapp_sent_count = ? WHERE id = ?",
        (email_count, whatsapp_count, notice_id),
    )
    db.commit()
