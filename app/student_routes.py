from flask import Blueprint, current_app, flash, redirect, render_template, session, url_for

from . import mailer, models
from .attendance_calc import compute_summary, summary_message
from .auth import student_required

bp = Blueprint("student", __name__, url_prefix="/student")


def _current_summary(student):
    threshold = current_app.config["ATTENDANCE_THRESHOLD"]
    total = models.count_sessions_for_course(student["course"])
    attended = models.count_attendance_for_student(student["id"], student["course"])
    return compute_summary(total, attended, threshold)


@bp.route("/")
@student_required
def dashboard():
    student = models.get_student_by_id(session["user_id"])
    summary = _current_summary(student)
    open_sessions = models.open_sessions_for_course(student["course"])
    open_sessions = [s for s in open_sessions if not models.has_marked(s["id"], student["id"])]
    history = models.attendance_history_for_student(student["id"])

    return render_template(
        "student/dashboard.html",
        student=student,
        summary=summary,
        message=summary_message(summary),
        open_sessions=open_sessions,
        history=history,
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

    models.mark_attendance(session_id, student["id"])

    summary = _current_summary(student)
    email_sent = mailer.send_attendance_email(student, summary)

    email_note = " A summary email has been sent." if email_sent else " (The summary email could not be sent - contact the admin.)"
    flash(
        f"Attendance marked for {sess['subject']}. Current attendance: {summary.percentage}%. "
        + summary_message(summary)
        + email_note,
        "success",
    )
    return redirect(url_for("student.dashboard"))
