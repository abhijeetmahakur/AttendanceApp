import csv
import io
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from . import mailer, models, qr_calc, reports_export, roster_import, stats_calc, storage, whatsapp
from .attendance_calc import classify_status, compute_summary, is_exam_eligible
from .auth import admin_required, super_admin_required
from .leave_calc import LEAVE_STATUSES
from .qr_calc import DURATION_CHOICES_MINUTES, LECTURE_PERIODS
from .validators import generate_password, validate_password, validate_registration_no, validate_roll_no

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NOTICE_CATEGORIES = ["holiday", "substitution", "general"]

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _current_admin():
    return models.get_admin_by_id(session["user_id"])


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
    leave_counts = models.leave_status_counts()

    return render_template(
        "admin/dashboard.html",
        student_count=len(students),
        session_count=len(sessions),
        open_count=open_count,
        low_attendance=low_attendance,
        threshold=threshold,
        leave_counts=leave_counts,
    )


@bp.route("/students", methods=["GET", "POST"])
@admin_required
def students():
    if request.method == "POST":
        reg_no = request.form.get("reg_no", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        course = request.form.get("course", "").strip()
        roll_no_raw = request.form.get("roll_no", "").strip()
        registration_no = request.form.get("registration_no", "").strip()
        password = request.form.get("password", "").strip() or generate_password()

        password_ok, password_error = validate_password(password)
        roll_ok, roll_no, roll_error = validate_roll_no(roll_no_raw)
        reg_no_ok = True
        reg_no_error = None
        if registration_no:
            reg_no_ok, reg_no_error = validate_registration_no(registration_no)

        if not (reg_no and name and email and course):
            flash("Registration number (login ID), name, email, and course are all required.", "error")
        elif models.get_student_by_reg_no(reg_no):
            flash(f"A student with login ID {reg_no} already exists.", "error")
        elif not password_ok:
            flash(password_error, "error")
        elif not roll_ok:
            flash(roll_error, "error")
        elif not reg_no_ok:
            flash(reg_no_error, "error")
        elif registration_no and models.get_student_by_registration_no(registration_no):
            flash(f"A student with registration number {registration_no} already exists.", "error")
        else:
            models.create_student(reg_no, name, email, course, password, phone, roll_no, registration_no)
            flash(
                f"Registered {name} ({reg_no}). Temporary password: {password} "
                "- share this with the student securely.",
                "success",
            )
        return redirect(url_for("admin.students"))

    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    exam_threshold = current_app.config["EXAM_ELIGIBILITY_THRESHOLD"]
    all_students = models.list_students()
    summaries = {
        s["id"]: compute_summary(
            models.count_sessions_for_course(s["course"]),
            models.count_attendance_for_student(s["id"], s["course"]),
            threshold,
        )
        for s in all_students
    }
    return render_template(
        "admin/students.html",
        students=all_students,
        threshold=threshold,
        exam_threshold=exam_threshold,
        summaries=summaries,
        exam_eligible={sid: is_exam_eligible(s.percentage, exam_threshold) for sid, s in summaries.items()},
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
        phone = request.form.get("phone", "").strip()
        course = request.form.get("course", "").strip()
        roll_no_raw = request.form.get("roll_no", "").strip()
        registration_no = request.form.get("registration_no", "").strip()
        new_password = request.form.get("password", "").strip()

        # Re-render with what the admin typed (not the stale DB row) if validation fails.
        form_state = {
            "id": student_id, "reg_no": reg_no, "name": name, "email": email,
            "phone": phone, "course": course, "roll_no": roll_no_raw, "registration_no": registration_no,
        }

        if not (reg_no and name and email and course):
            flash("Registration number, name, email, and course are all required.", "error")
            return render_template("admin/edit_student.html", student=form_state)

        if models.reg_no_taken_by_other(reg_no, student_id):
            flash(f"Registration number {reg_no} is already used by another student.", "error")
            return render_template("admin/edit_student.html", student=form_state)

        roll_ok, roll_no, roll_error = validate_roll_no(roll_no_raw)
        if not roll_ok:
            flash(roll_error, "error")
            return render_template("admin/edit_student.html", student=form_state)

        if registration_no:
            reg_ok, reg_error = validate_registration_no(registration_no)
            if not reg_ok:
                flash(reg_error, "error")
                return render_template("admin/edit_student.html", student=form_state)
            if models.registration_no_taken_by_other(registration_no, student_id):
                flash(f"Registration number {registration_no} is already used by another student.", "error")
                return render_template("admin/edit_student.html", student=form_state)

        if new_password:
            password_ok, password_error = validate_password(new_password)
            if not password_ok:
                flash(password_error, "error")
                return render_template("admin/edit_student.html", student=form_state)
            models.set_student_password(student_id, new_password)

        models.update_student(student_id, reg_no, name, email, course, phone, roll_no, registration_no)
        flash(f"Updated {name} ({reg_no}).", "success")
        return redirect(url_for("admin.students"))

    return render_template("admin/edit_student.html", student=student)


@bp.route("/students/import", methods=["GET", "POST"])
@admin_required
def students_import():
    if request.method == "POST":
        course = request.form.get("course", "").strip()
        upload = request.files.get("csv_file")

        if not course:
            flash("Please choose the class/section these students belong to.", "error")
            return redirect(url_for("admin.students_import"))
        if not upload or not upload.filename:
            flash("Please choose a CSV file to import.", "error")
            return redirect(url_for("admin.students_import"))

        try:
            text = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            flash("Could not read that file as text - please upload a CSV file.", "error")
            return redirect(url_for("admin.students_import"))

        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        if not reader.fieldnames:
            flash("That file doesn't look like a CSV (no header row found).", "error")
            return redirect(url_for("admin.students_import"))

        summary = roster_import.import_rows(rows, reader.fieldnames, course)

        message = (
            f"Import finished: {summary['created']} new roster entr"
            f"{'y' if summary['created'] == 1 else 'ies'} created (unclaimed, awaiting student sign-up), "
            f"{summary['updated']} existing student(s) enriched with roll/registration numbers, "
            f"{len(summary['skipped'])} row(s) skipped."
        )
        flash(message, "success")
        for row in summary["skipped"]:
            flash(f"Row {row['row']} ({row['name']}) skipped: {row['reason']}", "error")
        for row in summary["anomalies"]:
            flash(f"Row {row['row']} ({row['name']}): {row['reason']}", "warning")

        return redirect(url_for("admin.students"))

    return render_template("admin/students_import.html", courses=models.distinct_courses())


@bp.route("/signups")
@admin_required
def signups():
    return render_template("admin/signups.html", signups=models.list_pending_signups())


@bp.route("/signups/<int:student_id>/approve", methods=["POST"])
@admin_required
def approve_signup(student_id):
    student = models.get_student_by_id(student_id)
    if not student:
        flash("Student not found.", "error")
    else:
        models.approve_signup(student_id)
        flash(f"Approved {student['name']}'s sign-up. They can now log in.", "success")
    return redirect(url_for("admin.signups"))


@bp.route("/signups/<int:student_id>/reject", methods=["POST"])
@admin_required
def reject_signup(student_id):
    student = models.get_student_by_id(student_id)
    if not student:
        flash("Student not found.", "error")
    else:
        models.reject_signup(student_id)
        flash(f"Rejected {student['name']}'s sign-up request. They can submit a new one.", "success")
    return redirect(url_for("admin.signups"))


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
        elif not models.teacher_can_manage(_current_admin(), subject, course):
            flash(
                f"You aren't assigned to teach {subject} for {course}. "
                "Add it under \"My Subjects\" first, or ask a super admin to assign it to you.",
                "error",
            )
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
    return render_template(
        "admin/sessions.html", sessions=rows, statuses=statuses,
        subjects=models.distinct_timetable_subjects(),
    )


@bp.route("/sessions/<int:session_id>/delete", methods=["POST"])
@admin_required
def delete_session(session_id):
    models.delete_session(session_id)
    flash("Session deleted.", "success")
    return redirect(url_for("admin.sessions"))


def _absentees_for_session(sess):
    attendees = models.attendees_for_session(sess["id"])
    roster = models.list_students(sess["course"])
    attended_reg_nos = {a["reg_no"] for a in attendees}
    return attendees, [s for s in roster if s["reg_no"] not in attended_reg_nos]


@bp.route("/sessions/<int:session_id>/report")
@admin_required
def session_report(session_id):
    sess = models.get_session_by_id(session_id)
    if not sess:
        flash("Session not found.", "error")
        return redirect(url_for("admin.sessions"))

    attendees, absentees = _absentees_for_session(sess)

    return render_template(
        "admin/session_report.html",
        class_session=sess,
        attendees=attendees,
        absentees=absentees,
    )


@bp.route("/reports")
@admin_required
def reports():
    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    exam_threshold = current_app.config["EXAM_ELIGIBILITY_THRESHOLD"]
    course_filter = request.args.get("course", "").strip()
    students = models.list_students(course_filter or None)

    rows = []
    for s in students:
        total = models.count_sessions_for_course(s["course"])
        attended = models.count_attendance_for_student(s["id"], s["course"])
        summary = compute_summary(total, attended, threshold)
        rows.append({
            "student": s, "summary": summary,
            "exam_eligible": is_exam_eligible(summary.percentage, exam_threshold),
        })

    return render_template(
        "admin/reports.html",
        rows=rows,
        courses=models.distinct_courses(),
        course_filter=course_filter,
        threshold=threshold,
        exam_threshold=exam_threshold,
    )


# ---------- Leave requests ----------

@bp.route("/leaves")
@admin_required
def leaves():
    status_filter = request.args.get("status", "").strip().lower()
    if status_filter not in LEAVE_STATUSES:
        status_filter = ""

    return render_template(
        "admin/leaves.html",
        leave_requests=models.list_leave_requests(status_filter or None),
        status_filter=status_filter,
        counts=models.leave_status_counts(),
    )


@bp.route("/leaves/<int:leave_id>")
@admin_required
def leave_detail(leave_id):
    leave = models.get_leave_request(leave_id)
    if not leave:
        flash("Leave request not found.", "error")
        return redirect(url_for("admin.leaves"))

    student = models.get_student_by_id(leave["student_id"])
    reviewer = models.get_admin_by_id(leave["reviewed_by"]) if leave["reviewed_by"] else None
    return render_template("admin/leave_detail.html", leave=leave, student=student, reviewer=reviewer)


@bp.route("/leaves/<int:leave_id>/decide", methods=["POST"])
@admin_required
def leave_decide(leave_id):
    leave = models.get_leave_request(leave_id)
    if not leave:
        flash("Leave request not found.", "error")
        return redirect(url_for("admin.leaves"))

    decision = request.form.get("decision", "").strip().lower()
    comment = request.form.get("comment", "").strip()

    if decision not in ("approved", "rejected"):
        flash("Please choose to approve or reject the request.", "error")
        return redirect(url_for("admin.leave_detail", leave_id=leave_id))

    if decision == "rejected" and not comment:
        flash("Please provide a reason for rejecting the request.", "error")
        return redirect(url_for("admin.leave_detail", leave_id=leave_id))

    models.decide_leave_request(leave_id, decision, comment, session["user_id"])

    if decision == "approved":
        models.create_notification(
            leave["student_id"], "leave_approved",
            f"🟢 Your leave request LR-{leave_id:06d} ({leave['leave_type']}, "
            f"{leave['start_date']} to {leave['end_date']}) has been approved.",
        )
    else:
        models.create_notification(
            leave["student_id"], "leave_rejected",
            f"🔴 Your leave request LR-{leave_id:06d} ({leave['leave_type']}, "
            f"{leave['start_date']} to {leave['end_date']}) has been rejected. Reason: {comment}",
        )

    flash(f"Leave request LR-{leave_id:06d} marked as {decision}.", "success")
    return redirect(url_for("admin.leaves"))


@bp.route("/leaves/<int:leave_id>/attachment")
@admin_required
def leave_attachment(leave_id):
    leave = models.get_leave_request(leave_id)
    if not leave or not leave["attachment_path"]:
        abort(404)

    try:
        stream, size = storage.open_stream(leave["attachment_path"])
    except Exception:  # noqa: BLE001 - missing/unreachable file either way -> 404
        abort(404)

    return send_file(
        stream,
        as_attachment=True,
        download_name=leave["attachment_name"] or "attachment",
        conditional=False,
    )


# ---------- Attendance statistics ----------

def _stats_filters():
    return {
        "course": request.args.get("course", "").strip(),
        "subject": request.args.get("subject", "").strip(),
        "student_id": request.args.get("student_id", "").strip(),
        "start_date": request.args.get("start_date", "").strip(),
        "end_date": request.args.get("end_date", "").strip(),
    }


@bp.route("/stats")
@admin_required
def stats():
    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    filters = _stats_filters()

    matrix = models.attendance_matrix(
        course=filters["course"] or None,
        subject=filters["subject"] or None,
        student_id=int(filters["student_id"]) if filters["student_id"].isdigit() else None,
        start_date=filters["start_date"] or None,
        end_date=filters["end_date"] or None,
    )
    data = stats_calc.build_stats(matrix, threshold)

    return render_template(
        "admin/stats.html",
        data=data,
        filters=filters,
        courses=models.distinct_courses(),
        subjects=models.distinct_subjects(),
        students=models.list_students(),
        threshold=threshold,
        total_students=models.total_students(),
        total_classes=models.total_classes(),
        classes_conducted=models.classes_conducted(),
    )


# ---------- Exports ----------

@bp.route("/export/excel")
@admin_required
def export_excel():
    filters = _stats_filters()
    matrix = models.attendance_matrix(
        course=filters["course"] or None,
        subject=filters["subject"] or None,
        student_id=int(filters["student_id"]) if filters["student_id"].isdigit() else None,
        start_date=filters["start_date"] or None,
        end_date=filters["end_date"] or None,
    )

    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    grouped = {}
    for row in matrix:
        key = (row["student_id"], row["subject"])
        entry = grouped.setdefault(key, {
            "student_name": row["name"], "reg_no": row["reg_no"], "course": row["course"],
            "subject": row["subject"], "total": 0, "attended": 0,
        })
        entry["total"] += 1
        entry["attended"] += row["attended"]

    export_rows = []
    for entry in grouped.values():
        pct = round((entry["attended"] / entry["total"]) * 100, 2) if entry["total"] else 0.0
        export_rows.append({
            **entry,
            "missed": entry["total"] - entry["attended"],
            "percentage": pct,
            "status": classify_status(pct, threshold).title() if entry["total"] else "Safe",
        })
    export_rows.sort(key=lambda r: (r["student_name"].lower(), r["subject"].lower()))

    buf = reports_export.build_attendance_excel(export_rows)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"attendance_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
    )


@bp.route("/export/pdf/<int:student_id>")
@admin_required
def export_pdf(student_id):
    student = models.get_student_by_id(student_id)
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("admin.reports"))

    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    exam_threshold = current_app.config["EXAM_ELIGIBILITY_THRESHOLD"]
    subject_rows_raw = models.subject_wise_attendance_for_student(student_id, student["course"])
    subject_rows, overall = stats_calc.student_subject_breakdown(subject_rows_raw, threshold)

    buf = reports_export.build_student_attendance_pdf(
        current_app.config["COLLEGE_NAME"], student, subject_rows, overall, threshold,
        exam_eligible=is_exam_eligible(overall["percentage"], exam_threshold),
        exam_threshold=exam_threshold,
    )
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"attendance_{student['reg_no']}.pdf",
    )


# ---------- QR attendance ----------

@bp.route("/qr")
@admin_required
def qr_list():
    rows = models.list_qr_sessions()
    statuses = {row["session_id"]: models.session_status(row) for row in rows}
    return render_template("admin/qr_list.html", qr_sessions=rows, statuses=statuses)


@bp.route("/qr/generate", methods=["GET", "POST"])
@admin_required
def qr_generate():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        course = request.form.get("course", "").strip()
        session_date = request.form.get("session_date", "").strip()
        lecture = request.form.get("lecture", "").strip()
        duration = request.form.get("duration", "").strip()

        if not (subject and course and session_date and lecture):
            flash("Subject, class/section, date, and lecture/period are all required.", "error")
            return redirect(url_for("admin.qr_generate"))

        if not models.teacher_can_manage(_current_admin(), subject, course):
            flash(
                f"You aren't assigned to teach {subject} for {course}. "
                "Add it under \"My Subjects\" first, or ask a super admin to assign it to you.",
                "error",
            )
            return redirect(url_for("admin.qr_generate"))

        try:
            duration_minutes = int(duration)
            if duration_minutes <= 0:
                raise ValueError
        except ValueError:
            flash("Please choose a valid attendance duration.", "error")
            return redirect(url_for("admin.qr_generate"))

        now = datetime.now()
        start_at = now.strftime("%Y-%m-%d %H:%M:%S")
        end_at = (now + timedelta(minutes=duration_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        code = qr_calc.generate_code()

        class_session_id = models.create_qr_session(
            subject, course, session_date, lecture, start_at, end_at, code, session["user_id"],
        )
        qr_row = models.get_qr_session_by_code(code)
        flash(f"QR attendance session created for {subject} ({lecture}).", "success")
        return redirect(url_for("admin.qr_view", qr_id=qr_row["qr_id"]))

    return render_template(
        "admin/qr_generate.html",
        lecture_periods=LECTURE_PERIODS,
        duration_choices=DURATION_CHOICES_MINUTES,
        default_duration=current_app.config["QR_DEFAULT_DURATION_MINUTES"],
        today=datetime.now().strftime("%Y-%m-%d"),
    )


@bp.route("/qr/<int:qr_id>")
@admin_required
def qr_view(qr_id):
    qr_row = models.get_qr_session(qr_id)
    if not qr_row:
        flash("QR session not found.", "error")
        return redirect(url_for("admin.qr_list"))

    status = models.session_status(qr_row)
    qr_image = qr_calc.qr_image_data_uri(qr_row["code"])
    attendees = models.attendees_for_session(qr_row["session_id"])

    end_dt = datetime.strptime(qr_row["end_at"], "%Y-%m-%d %H:%M:%S")
    remaining_seconds = max(0, int((end_dt - datetime.now()).total_seconds()))

    return render_template(
        "admin/qr_view.html",
        qr=qr_row,
        status=status,
        qr_image=qr_image,
        attendees=attendees,
        remaining_seconds=remaining_seconds,
    )


# ---------- Teacher accounts (super admin only) ----------

@bp.route("/teachers", methods=["GET", "POST"])
@super_admin_required
def teachers():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip() or generate_password()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        password_ok, password_error = validate_password(password)

        if not username:
            flash("A username is required.", "error")
        elif models.get_admin_by_username(username):
            flash(f"An account with username {username!r} already exists.", "error")
        elif not password_ok:
            flash(password_error, "error")
        else:
            models.create_teacher(username, password, email, phone)
            flash(
                f"Created teacher account {username!r}. Temporary password: {password} "
                "- share this with them securely.",
                "success",
            )
        return redirect(url_for("admin.teachers"))

    return render_template(
        "admin/teachers.html",
        teachers=models.list_teachers(),
        subjects_by_teacher={t["id"]: models.list_subjects_for_teacher(t["id"]) for t in models.list_teachers()},
    )


@bp.route("/teachers/<int:teacher_id>/delete", methods=["POST"])
@super_admin_required
def delete_teacher(teacher_id):
    if models.delete_teacher(teacher_id):
        flash("Teacher account removed.", "success")
    else:
        flash("That account can't be removed (it may be the super admin account).", "error")
    return redirect(url_for("admin.teachers"))


@bp.route("/teachers/<int:teacher_id>/subjects", methods=["POST"])
@super_admin_required
def assign_teacher_subject(teacher_id):
    subject = request.form.get("subject", "").strip()
    course = request.form.get("course", "").strip()
    if not (subject and course):
        flash("Subject and class/section are both required.", "error")
    elif not models.add_teacher_subject(teacher_id, subject, course):
        flash("That teacher is already assigned to that subject/section.", "error")
    else:
        flash(f"Assigned {subject} ({course}) to this teacher.", "success")
    return redirect(url_for("admin.teachers"))


@bp.route("/teachers/<int:teacher_id>/subjects/<int:assignment_id>/delete", methods=["POST"])
@super_admin_required
def remove_teacher_subject_admin(teacher_id, assignment_id):
    models.remove_teacher_subject(assignment_id)
    flash("Subject assignment removed.", "success")
    return redirect(url_for("admin.teachers"))


# ---------- My subjects (any teacher, self-service) ----------

@bp.route("/my-subjects", methods=["GET", "POST"])
@admin_required
def my_subjects():
    admin = _current_admin()

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        course = request.form.get("course", "").strip()
        if not (subject and course):
            flash("Subject and class/section are both required.", "error")
        elif not models.add_teacher_subject(admin["id"], subject, course):
            flash("You're already assigned to that subject/section.", "error")
        else:
            flash(f"Added {subject} ({course}) to your subjects.", "success")
        return redirect(url_for("admin.my_subjects"))

    return render_template(
        "admin/my_subjects.html",
        admin=admin,
        assignments=models.list_subjects_for_teacher(admin["id"]),
        subjects=models.distinct_timetable_subjects(),
    )


@bp.route("/my-subjects/<int:assignment_id>/delete", methods=["POST"])
@admin_required
def remove_my_subject(assignment_id):
    models.remove_teacher_subject(assignment_id, teacher_id=session["user_id"])
    flash("Subject removed from your list.", "success")
    return redirect(url_for("admin.my_subjects"))


# ---------- WhatsApp groups ----------

@bp.route("/whatsapp/groups", methods=["GET", "POST"])
@admin_required
def whatsapp_groups():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        course = request.form.get("course", "").strip()
        if not (name and course):
            flash("Group name and class/section are both required.", "error")
        else:
            group_id = models.create_whatsapp_group(name, course, session["user_id"])
            flash(f"Created WhatsApp group '{name}'. Add member phone numbers to it below.", "success")
            return redirect(url_for("admin.whatsapp_group_detail", group_id=group_id))
        return redirect(url_for("admin.whatsapp_groups"))

    return render_template(
        "admin/whatsapp_groups.html",
        groups=models.list_whatsapp_groups(),
        whatsapp_configured=whatsapp.is_configured(),
    )


@bp.route("/whatsapp/groups/<int:group_id>", methods=["GET", "POST"])
@admin_required
def whatsapp_group_detail(group_id):
    group = models.get_whatsapp_group(group_id)
    if not group:
        flash("WhatsApp group not found.", "error")
        return redirect(url_for("admin.whatsapp_groups"))

    if request.method == "POST":
        label = request.form.get("label", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        if not (label and phone_number):
            flash("A label and phone number are both required.", "error")
        else:
            models.add_group_member(group_id, label, phone_number)
            flash(f"Added {label} to the group.", "success")
        return redirect(url_for("admin.whatsapp_group_detail", group_id=group_id))

    return render_template(
        "admin/whatsapp_group_detail.html",
        group=group,
        members=models.list_group_members(group_id),
    )


@bp.route("/whatsapp/groups/<int:group_id>/delete", methods=["POST"])
@admin_required
def delete_whatsapp_group(group_id):
    models.delete_whatsapp_group(group_id)
    flash("WhatsApp group deleted.", "success")
    return redirect(url_for("admin.whatsapp_groups"))


@bp.route("/whatsapp/groups/<int:group_id>/members/<int:member_id>/delete", methods=["POST"])
@admin_required
def remove_whatsapp_member(group_id, member_id):
    models.remove_group_member(member_id)
    flash("Member removed.", "success")
    return redirect(url_for("admin.whatsapp_group_detail", group_id=group_id))


# ---------- Absentee WhatsApp alert ----------

@bp.route("/sessions/<int:session_id>/absentee-alert", methods=["GET", "POST"])
@admin_required
def absentee_alert(session_id):
    sess = models.get_session_by_id(session_id)
    if not sess:
        flash("Session not found.", "error")
        return redirect(url_for("admin.sessions"))

    _, absentees = _absentees_for_session(sess)
    groups = models.list_whatsapp_groups(sess["course"])

    if request.method == "POST":
        group_id = request.form.get("group_id", "").strip()
        subject = request.form.get("subject", "").strip() or sess["subject"]
        message = request.form.get("message", "").strip()

        group = models.get_whatsapp_group(int(group_id)) if group_id.isdigit() else None
        if not group:
            flash("Please choose a WhatsApp group to send to.", "error")
            return redirect(url_for("admin.absentee_alert", session_id=session_id))

        members = models.list_group_members(group["id"])
        if not members:
            flash("That group has no phone numbers yet - add some first.", "error")
            return redirect(url_for("admin.whatsapp_group_detail", group_id=group["id"]))

        sent, failed, failures = whatsapp.send_group_message(members, message)
        if failed:
            flash(
                f"Sent to {sent} of {len(members)} member(s). {failed} failed "
                f"({', '.join(p for p, _ in failures[:3])}{'...' if failed > 3 else ''}).",
                "error" if sent == 0 else "success",
            )
        else:
            flash(f"Absentee alert for {subject} sent to all {sent} member(s) of '{group['name']}'.", "success")
        return redirect(url_for("admin.session_report", session_id=session_id))

    absent_list = ", ".join(s["reg_no"] for s in absentees) or "None"
    default_message = (
        f"Attendance Alert - {sess['subject']}\n"
        f"Date: {sess['session_date']}\n"
        f"Absent Roll Numbers: {absent_list}\n"
        f"Total Absent: {len(absentees)}"
    )

    return render_template(
        "admin/absentee_alert.html",
        class_session=sess,
        absentees=absentees,
        groups=groups,
        default_message=default_message,
        whatsapp_configured=whatsapp.is_configured(),
    )


# ---------- Holidays ----------

@bp.route("/holidays", methods=["GET", "POST"])
@admin_required
def holidays():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        holiday_date = request.form.get("holiday_date", "").strip()
        day_of_week = request.form.get("day_of_week", "").strip()
        category = request.form.get("category", "mandatory").strip()

        if not (name and holiday_date and day_of_week):
            flash("Name, date, and day of the week are all required.", "error")
        else:
            models.create_holiday(name, holiday_date, day_of_week, category)
            flash(f"Added holiday '{name}'.", "success")
        return redirect(url_for("admin.holidays"))

    return render_template("admin/holidays.html", holidays=models.list_holidays())


@bp.route("/holidays/<int:holiday_id>/delete", methods=["POST"])
@admin_required
def delete_holiday(holiday_id):
    models.delete_holiday(holiday_id)
    flash("Holiday removed.", "success")
    return redirect(url_for("admin.holidays"))


# ---------- Timetable ----------

@bp.route("/timetable")
@admin_required
def timetable():
    course_filter = request.args.get("course", "").strip()
    rows = models.list_timetable(course_filter or None)
    by_day = {day: [r for r in rows if r["day_of_week"] == day] for day in DAYS_OF_WEEK}

    return render_template(
        "admin/timetable.html",
        by_day=by_day,
        days=DAYS_OF_WEEK,
        courses=models.distinct_timetable_courses(),
        course_filter=course_filter,
    )


@bp.route("/timetable/add", methods=["GET", "POST"])
@admin_required
def timetable_add():
    if request.method == "POST":
        course = request.form.get("course", "").strip()
        semester_label = request.form.get("semester_label", "").strip()
        room = request.form.get("room", "").strip()
        day_of_week = request.form.get("day_of_week", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        subject_code = request.form.get("subject_code", "").strip()
        subject_name = request.form.get("subject_name", "").strip()
        faculty = request.form.get("faculty", "").strip()

        if not (course and day_of_week and start_time and end_time and subject_name):
            flash("Class/section, day, start/end time, and subject name are required.", "error")
        elif end_time <= start_time:
            flash("End time must be after the start time.", "error")
        else:
            models.create_timetable_entry(
                course, semester_label, room, day_of_week, start_time, end_time,
                subject_code, subject_name, faculty, session["user_id"],
            )
            flash(f"Added {subject_name} on {day_of_week} to the timetable.", "success")
            return redirect(url_for("admin.timetable", course=course))

    return render_template("admin/timetable_form.html", entry=None, days=DAYS_OF_WEEK)


@bp.route("/timetable/<int:entry_id>/edit", methods=["GET", "POST"])
@admin_required
def timetable_edit(entry_id):
    entry = models.get_timetable_entry(entry_id)
    if not entry:
        flash("Timetable entry not found.", "error")
        return redirect(url_for("admin.timetable"))

    if request.method == "POST":
        course = request.form.get("course", "").strip()
        semester_label = request.form.get("semester_label", "").strip()
        room = request.form.get("room", "").strip()
        day_of_week = request.form.get("day_of_week", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        subject_code = request.form.get("subject_code", "").strip()
        subject_name = request.form.get("subject_name", "").strip()
        faculty = request.form.get("faculty", "").strip()

        if not (course and day_of_week and start_time and end_time and subject_name):
            flash("Class/section, day, start/end time, and subject name are required.", "error")
        elif end_time <= start_time:
            flash("End time must be after the start time.", "error")
        else:
            models.update_timetable_entry(
                entry_id, course, semester_label, room, day_of_week, start_time, end_time,
                subject_code, subject_name, faculty,
            )
            flash(f"Updated {subject_name}.", "success")
            return redirect(url_for("admin.timetable", course=course))

    return render_template("admin/timetable_form.html", entry=entry, days=DAYS_OF_WEEK)


@bp.route("/timetable/<int:entry_id>/delete", methods=["POST"])
@admin_required
def timetable_delete(entry_id):
    models.delete_timetable_entry(entry_id)
    flash("Timetable entry removed.", "success")
    return redirect(url_for("admin.timetable"))


# ---------- Notices ----------

@bp.route("/notices", methods=["GET", "POST"])
@admin_required
def notices():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        category = request.form.get("category", "general").strip()
        course = request.form.get("course", "").strip()

        if not (title and message):
            flash("Title and message are both required.", "error")
            return redirect(url_for("admin.notices"))
        if category not in NOTICE_CATEGORIES:
            category = "general"

        notice_id = models.create_notice(title, message, category, course, session["user_id"])
        notice = models.get_notice(notice_id)
        recipients = models.list_students(course or None)

        email_count = 0
        for student in recipients:
            if mailer.send_notice_email(student, notice):
                email_count += 1

        whatsapp_count = 0
        for student in recipients:
            if student["phone"]:
                ok, _detail = whatsapp.send_whatsapp_message(
                    student["phone"], f"{title}\n\n{message}",
                )
                if ok:
                    whatsapp_count += 1

        models.set_notice_send_counts(notice_id, email_count, whatsapp_count)
        flash(
            f"Notice '{title}' sent: {email_count}/{len(recipients)} by email, "
            f"{whatsapp_count} by WhatsApp (only students with a phone number on file).",
            "success",
        )
        return redirect(url_for("admin.notices"))

    return render_template(
        "admin/notices.html",
        notices=models.list_notices(),
        courses=models.distinct_courses(),
        categories=NOTICE_CATEGORIES,
        whatsapp_configured=whatsapp.is_configured(),
        prefill_title=request.args.get("title", ""),
        prefill_category=request.args.get("category", "general"),
    )


@bp.route("/notices/<int:notice_id>/delete", methods=["POST"])
@admin_required
def delete_notice(notice_id):
    models.delete_notice(notice_id)
    flash("Notice deleted.", "success")
    return redirect(url_for("admin.notices"))
