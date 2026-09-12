from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from . import models
from .attendance_calc import compute_summary
from .auth import admin_required
from .validators import generate_password, validate_password

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def dashboard():
    students = models.list_students()
    sessions = models.list_sessions()

    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    low_attendance = []
    for s in students:
        total = models.count_sessions_for_course(s["course"])
        attended = models.count_attendance_for_student(s["id"], s["course"])
        summary = compute_summary(total, attended, threshold)
        if total > 0 and not summary.meets_threshold:
            low_attendance.append({"student": s, "summary": summary})

    open_count = sum(1 for sess in sessions if models.session_status(sess) == "open")

    return render_template(
        "admin/dashboard.html",
        student_count=len(students),
        session_count=len(sessions),
        open_count=open_count,
        low_attendance=low_attendance,
        threshold=threshold,
    )


@bp.route("/students", methods=["GET", "POST"])
@admin_required
def students():
    if request.method == "POST":
        reg_no = request.form.get("reg_no", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        course = request.form.get("course", "").strip()
        password = request.form.get("password", "").strip() or generate_password()

        password_ok, password_error = validate_password(password)

        if not (reg_no and name and email and course):
            flash("Registration number, name, email, and course are all required.", "error")
        elif models.get_student_by_reg_no(reg_no):
            flash(f"A student with registration number {reg_no} already exists.", "error")
        elif not password_ok:
            flash(password_error, "error")
        else:
            models.create_student(reg_no, name, email, course, password)
            flash(
                f"Registered {name} ({reg_no}). Temporary password: {password} "
                "- share this with the student securely.",
                "success",
            )
        return redirect(url_for("admin.students"))

    return render_template(
        "admin/students.html",
        students=models.list_students(),
        threshold=current_app.config["ATTENDANCE_THRESHOLD"],
        summaries={
            s["id"]: compute_summary(
                models.count_sessions_for_course(s["course"]),
                models.count_attendance_for_student(s["id"], s["course"]),
                current_app.config["ATTENDANCE_THRESHOLD"],
            )
            for s in models.list_students()
        },
    )


@bp.route("/students/<int:student_id>/delete", methods=["POST"])
@admin_required
def delete_student(student_id):
    models.delete_student(student_id)
    flash("Student removed.", "success")
    return redirect(url_for("admin.students"))


@bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_student(student_id):
    student = models.get_student_by_id(student_id)
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("admin.students"))

    if request.method == "POST":
        reg_no = request.form.get("reg_no", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        course = request.form.get("course", "").strip()
        new_password = request.form.get("password", "").strip()

        # Re-render with what the admin typed (not the stale DB row) if validation fails.
        form_state = {"id": student_id, "reg_no": reg_no, "name": name, "email": email, "course": course}

        if not (reg_no and name and email and course):
            flash("Registration number, name, email, and course are all required.", "error")
            return render_template("admin/edit_student.html", student=form_state)

        if models.reg_no_taken_by_other(reg_no, student_id):
            flash(f"Registration number {reg_no} is already used by another student.", "error")
            return render_template("admin/edit_student.html", student=form_state)

        if new_password:
            password_ok, password_error = validate_password(new_password)
            if not password_ok:
                flash(password_error, "error")
                return render_template("admin/edit_student.html", student=form_state)
            models.set_student_password(student_id, new_password)

        models.update_student(student_id, reg_no, name, email, course)
        flash(f"Updated {name} ({reg_no}).", "success")
        return redirect(url_for("admin.students"))

    return render_template("admin/edit_student.html", student=student)


@bp.route("/sessions", methods=["GET", "POST"])
@admin_required
def sessions():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        course = request.form.get("course", "").strip()
        session_date = request.form.get("session_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()

        if not (subject and course and session_date and start_time and end_time):
            flash("All fields are required to create a class session.", "error")
        else:
            start_at = f"{session_date} {start_time}:00"
            end_at = f"{session_date} {end_time}:00"
            if end_at <= start_at:
                flash("The attendance window end time must be after the start time.", "error")
            else:
                models.create_session(subject, course, session_date, start_at, end_at, session["user_id"])
                flash(f"Created session '{subject}' with attendance window {start_time}-{end_time}.", "success")
        return redirect(url_for("admin.sessions"))

    rows = models.list_sessions()
    statuses = {row["id"]: models.session_status(row) for row in rows}
    return render_template("admin/sessions.html", sessions=rows, statuses=statuses)


@bp.route("/sessions/<int:session_id>/delete", methods=["POST"])
@admin_required
def delete_session(session_id):
    models.delete_session(session_id)
    flash("Session deleted.", "success")
    return redirect(url_for("admin.sessions"))


@bp.route("/sessions/<int:session_id>/report")
@admin_required
def session_report(session_id):
    sess = models.get_session_by_id(session_id)
    if not sess:
        flash("Session not found.", "error")
        return redirect(url_for("admin.sessions"))

    attendees = models.attendees_for_session(session_id)
    roster = models.list_students(sess["course"])
    attended_reg_nos = {a["reg_no"] for a in attendees}
    absentees = [s for s in roster if s["reg_no"] not in attended_reg_nos]

    return render_template(
        "admin/session_report.html",
        session=sess,
        attendees=attendees,
        absentees=absentees,
    )


@bp.route("/reports")
@admin_required
def reports():
    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    course_filter = request.args.get("course", "").strip()
    students = models.list_students(course_filter or None)

    rows = []
    for s in students:
        total = models.count_sessions_for_course(s["course"])
        attended = models.count_attendance_for_student(s["id"], s["course"])
        summary = compute_summary(total, attended, threshold)
        rows.append({"student": s, "summary": summary})

    return render_template(
        "admin/reports.html",
        rows=rows,
        courses=models.distinct_courses(),
        course_filter=course_filter,
        threshold=threshold,
    )
