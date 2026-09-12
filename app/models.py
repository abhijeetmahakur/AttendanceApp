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


def verify_admin(username, password):
    admin = get_admin_by_username(username)
    if admin and check_password_hash(admin["password_hash"], password):
        return admin
    return None


# ---------- Students ----------

def get_student_by_id(student_id):
    db = get_db()
    return db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()


def get_student_by_reg_no(reg_no):
    db = get_db()
    return db.execute("SELECT * FROM students WHERE reg_no = ?", (reg_no,)).fetchone()


def verify_student(reg_no, password):
    student = get_student_by_reg_no(reg_no)
    if student and check_password_hash(student["password_hash"], password):
        return student
    return None


def list_students(course=None):
    db = get_db()
    if course:
        return db.execute(
            "SELECT * FROM students WHERE course = ? COLLATE NOCASE ORDER BY reg_no", (course,)
        ).fetchall()
    return db.execute("SELECT * FROM students ORDER BY course, reg_no").fetchall()


def create_student(reg_no, name, email, course, password):
    db = get_db()
    db.execute(
        """INSERT INTO students (reg_no, name, email, course, password_hash)
           VALUES (?, ?, ?, ?, ?)""",
        (reg_no.strip(), name.strip(), email.strip(), course.strip(), generate_password_hash(password)),
    )
    db.commit()


def delete_student(student_id):
    db = get_db()
    db.execute("DELETE FROM students WHERE id = ?", (student_id,))
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


def attendees_for_session(session_id):
    db = get_db()
    return db.execute(
        """SELECT st.reg_no, st.name, a.marked_at
           FROM attendance a
           JOIN students st ON st.id = a.student_id
           WHERE a.session_id = ?
           ORDER BY a.marked_at""",
        (session_id,),
    ).fetchall()


def open_sessions_for_course(course):
    db = get_db()
    at = now_str()
    return db.execute(
        """SELECT * FROM class_sessions
           WHERE course = ? COLLATE NOCASE AND ? BETWEEN start_at AND end_at
           ORDER BY start_at""",
        (course, at),
    ).fetchall()
