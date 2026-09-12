import sqlite3
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from . import mailer, models, reports_export, stats_calc, storage
from .attendance_calc import classify_status, compute_summary, is_exam_eligible, summary_message
from .auth import student_required
from .leave_calc import LEAVE_TYPES, validate_leave_dates
from .validators import allowed_attachment_filename

bp = Blueprint("student", __name__, url_prefix="/student")

STATUS_ICON = {"safe": "🟢", "warning": "🟡", "critical": "🔴"}


def _current_summary(student):
    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    total = models.count_sessions_for_course(student["course"])
    attended = models.count_attendance_for_student(student["id"], student["course"])
    return compute_summary(total, attended, threshold)


def _notify_threshold_change(student, before, after):
    """Fires a notification only when a newly-marked attendance record
    actually pushes the student across the pass/fail threshold line."""
    if before.meets_threshold == after.meets_threshold:
        return
    if after.meets_threshold:
        models.create_notification(
            student["id"], "attendance_ok",
            f"🟢 Your attendance has reached {after.percentage}%, at or above the "
            f"required {after.threshold:.0f}%. Keep it up!",
        )
    else:
        models.create_notification(
            student["id"], "attendance_low",
            f"🔴 Your attendance has fallen to {after.percentage}%, below the required "
            f"{after.threshold:.0f}%.",
        )


@bp.route("/")
@student_required
def dashboard():
    student = models.get_student_by_id(session["user_id"])
    summary = _current_summary(student)
    open_sessions = models.open_sessions_for_course(student["course"])
    open_sessions = [s for s in open_sessions if not models.has_marked(s["id"], student["id"])]
    history = models.attendance_history_for_student(student["id"])
    leave_summary = models.leave_summary_for_student(student["id"])
    status = classify_status(summary.percentage, summary.threshold)
    exam_threshold = current_app.config["EXAM_ELIGIBILITY_THRESHOLD"]

    return render_template(
        "student/dashboard.html",
        student=student,
        summary=summary,
        message=summary_message(summary),
        open_sessions=open_sessions,
        history=history,
        leave_summary=leave_summary,
        status=status,
        status_icon=STATUS_ICON[status],
        exam_eligible=is_exam_eligible(summary.percentage, exam_threshold),
        exam_threshold=exam_threshold,
    )


@bp.route("/mark/<int:session_id>", methods=["POST"])
@student_required
def mark(session_id):
    student = models.get_student_by_id(session["user_id"])
    sess = models.get_session_by_id(session_id)

    if not sess or sess["course"].lower() != student["course"].lower():
        flash("That class session is not available to you.", "error")
        return redirect(url_for("student.dashboard"))

    if models.session_status(sess) != "open":
        flash("The attendance window for that class is not currently open.", "error")
        return redirect(url_for("student.dashboard"))

    if models.has_marked(session_id, student["id"]):
        flash("You have already marked attendance for that class.", "error")
        return redirect(url_for("student.dashboard"))

    before_summary = _current_summary(student)
    models.mark_attendance(session_id, student["id"])

    summary = _current_summary(student)
    _notify_threshold_change(student, before_summary, summary)
    email_sent = mailer.send_attendance_email(student, summary)

    email_note = " A summary email has been sent." if email_sent else " (The summary email could not be sent - contact the admin.)"
    flash(
        f"Attendance marked for {sess['subject']}. Current attendance: {summary.percentage}%. "
        + summary_message(summary)
        + email_note,
        "success",
    )
    return redirect(url_for("student.dashboard"))


# ---------- Leave management ----------

def _save_attachment(file_storage, student_id):
    """Saves an uploaded leave attachment via app.storage (cloud storage
    when configured, local disk otherwise - see storage.py).

    Returns (relative_path, original_name), or (None, None) if no file was
    provided. Raises ValueError (safe to flash) if the file type isn't allowed.
    """
    if not file_storage or not file_storage.filename:
        return None, None

    original_name = file_storage.filename
    if not allowed_attachment_filename(original_name):
        raise ValueError(
            "Attachment must be a PDF, Word document, or image (pdf, doc, docx, png, jpg, jpeg)."
        )

    ext = original_name.rsplit(".", 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    rel_path = f"leave_attachments/{student_id}/{safe_name}"
    storage.save(file_storage, rel_path)

    return rel_path, secure_filename(original_name) or original_name


@bp.route("/leave/apply", methods=["GET", "POST"])
@student_required
def leave_apply():
    student = models.get_student_by_id(session["user_id"])
    max_attachment_mb = current_app.config["MAX_ATTACHMENT_SIZE_MB"]

    if request.method == "POST":
        leave_type = request.form.get("leave_type", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        reason = request.form.get("reason", "").strip()
        attachment = request.files.get("attachment")

        form = {
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
        }

        if leave_type not in LEAVE_TYPES:
            flash("Please choose a valid leave type.", "error")
            return render_template(
                "student/leave_apply.html", leave_types=LEAVE_TYPES, form=form,
                max_attachment_mb=max_attachment_mb,
            )

        if not reason:
            flash("Please provide a reason for your leave.", "error")
            return render_template(
                "student/leave_apply.html", leave_types=LEAVE_TYPES, form=form,
                max_attachment_mb=max_attachment_mb,
            )

        dates_ok, num_days, date_error = validate_leave_dates(start_date, end_date)
        if not dates_ok:
            flash(date_error, "error")
            return render_template(
                "student/leave_apply.html", leave_types=LEAVE_TYPES, form=form,
                max_attachment_mb=max_attachment_mb,
            )

        try:
            attachment_path, attachment_name = _save_attachment(attachment, student["id"])
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template(
                "student/leave_apply.html", leave_types=LEAVE_TYPES, form=form,
                max_attachment_mb=max_attachment_mb,
            )

        leave_id = models.create_leave_request(
            student["id"], leave_type, start_date, end_date, num_days, reason,
            attachment_path, attachment_name,
        )

        flash(
            f"Leave request LR-{leave_id:06d} submitted successfully. "
            "Its status is now Pending review by an administrator.",
            "success",
        )
        return redirect(url_for("student.leave_status"))

    return render_template(
        "student/leave_apply.html", leave_types=LEAVE_TYPES, form={},
        max_attachment_mb=max_attachment_mb,
    )


@bp.route("/leave/status")
@student_required
def leave_status():
    student = models.get_student_by_id(session["user_id"])
    leave_requests = models.list_leave_requests_for_student(student["id"])
    return render_template("student/leave_status.html", leave_requests=leave_requests)


@bp.route("/leave/<int:leave_id>/attachment")
@student_required
def leave_attachment(leave_id):
    leave = models.get_leave_request(leave_id)
    if not leave or leave["student_id"] != session["user_id"] or not leave["attachment_path"]:
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


# ---------- My Attendance (detailed subject-wise view) ----------

@bp.route("/attendance")
@student_required
def attendance_detail():
    student = models.get_student_by_id(session["user_id"])
    threshold = current_app.config["ATTENDANCE_THRESHOLD"]

    subject_rows_raw = models.subject_wise_attendance_for_student(student["id"], student["course"])
    subject_rows, overall = stats_calc.student_subject_breakdown(subject_rows_raw, threshold)
    summary = _current_summary(student)
    status = classify_status(summary.percentage, threshold)
    exam_threshold = current_app.config["EXAM_ELIGIBILITY_THRESHOLD"]

    return render_template(
        "student/attendance.html",
        student=student,
        subject_rows=subject_rows,
        overall=overall,
        summary=summary,
        message=summary_message(summary),
        status=status,
        status_icon=STATUS_ICON[status],
        threshold=threshold,
        exam_eligible=is_exam_eligible(overall["percentage"], exam_threshold),
        exam_threshold=exam_threshold,
    )


@bp.route("/attendance/export/pdf")
@student_required
def attendance_export_pdf():
    student = models.get_student_by_id(session["user_id"])
    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    exam_threshold = current_app.config["EXAM_ELIGIBILITY_THRESHOLD"]
    subject_rows_raw = models.subject_wise_attendance_for_student(student["id"], student["course"])
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
        download_name=f"my_attendance_{student['reg_no']}.pdf",
    )


# ---------- QR attendance ----------

@bp.route("/qr/scan")
@student_required
def qr_scan():
    return render_template("student/qr_scan.html")


@bp.route("/qr/verify", methods=["POST"])
@student_required
def qr_verify():
    student = models.get_student_by_id(session["user_id"])
    payload = request.get_json(silent=True) or {}
    code = (request.form.get("code") or payload.get("code") or "").strip()

    if not code:
        return jsonify(ok=False, status="invalid", message="No QR code was provided."), 400

    qr_row = models.get_qr_session_by_code(code)
    if not qr_row:
        return jsonify(ok=False, status="invalid", message="This QR code is not recognized."), 404

    if qr_row["course"].lower() != student["course"].lower():
        return jsonify(
            ok=False, status="invalid",
            message="This QR code is not for your class/section.",
        ), 403

    window_status = models.session_status(qr_row)
    if window_status == "upcoming":
        return jsonify(
            ok=False, status="invalid",
            message="This attendance session has not started yet.",
        ), 400
    if window_status == "closed":
        models.create_notification(
            student["id"], "qr_expired",
            f"❌ The QR attendance session for {qr_row['subject']} on {qr_row['session_date']} expired "
            "before you scanned it.",
        )
        return jsonify(
            ok=False, status="expired",
            message="Attendance Session Expired",
        ), 410

    if models.has_marked(qr_row["session_id"], student["id"]):
        return jsonify(
            ok=False, status="already_marked",
            message="Attendance Already Marked",
        ), 409

    before_summary = _current_summary(student)
    try:
        models.mark_attendance(qr_row["session_id"], student["id"])
    except sqlite3.IntegrityError:
        # Lost a race with another request for the same student+session.
        return jsonify(
            ok=False, status="already_marked",
            message="Attendance Already Marked",
        ), 409

    summary = _current_summary(student)
    _notify_threshold_change(student, before_summary, summary)

    now = datetime.now()
    models.create_notification(
        student["id"], "qr_attendance",
        f"✅ Attendance marked via QR for {qr_row['subject']} "
        f"({qr_row['lecture'] or 'session'}) at {now.strftime('%I:%M %p')}.",
    )

    return jsonify(
        ok=True,
        status="success",
        subject=qr_row["subject"],
        lecture=qr_row["lecture"] or "",
        date=now.strftime("%d %B %Y"),
        time=now.strftime("%I:%M %p"),
        percentage=summary.percentage,
    )


# ---------- Notifications ----------

@bp.route("/notifications")
@student_required
def notifications():
    student_id = session["user_id"]
    items = models.list_notifications_for_student(student_id)
    models.mark_notifications_read(student_id)
    return render_template("student/notifications.html", notifications=items)


# ---------- Holidays ----------

@bp.route("/holidays")
@student_required
def holidays():
    return render_template("student/holidays.html", holidays=models.list_holidays())


# ---------- Timetable ----------

@bp.route("/timetable")
@student_required
def timetable():
    student = models.get_student_by_id(session["user_id"])
    rows = models.list_timetable(student["course"])
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_day = {day: [r for r in rows if r["day_of_week"] == day] for day in days}
    return render_template("student/timetable.html", by_day=by_day, days=days, student=student)


# ---------- Notices ----------

@bp.route("/notices")
@student_required
def notices():
    student = models.get_student_by_id(session["user_id"])
    return render_template("student/notices.html", notices=models.list_notices(student["course"]))
