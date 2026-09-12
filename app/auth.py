from functools import wraps

from flask import flash, redirect, session, url_for

from . import models


def login_admin(admin_row):
    session.clear()
    session["role"] = "admin"
    session["user_id"] = admin_row["id"]
    session["display_name"] = admin_row["username"]
    session["admin_role"] = admin_row["role"]


def login_student(student_row):
    session.clear()
    session["role"] = "student"
    session["user_id"] = student_row["id"]
    session["display_name"] = student_row["name"]
    session["course"] = student_row["course"]
    session["reg_no"] = student_row["reg_no"]


def logout():
    session.clear()


def current_role():
    return session.get("role")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin" or not models.get_admin_by_id(session.get("user_id")):
            session.clear()
            flash("Please log in as an admin to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def super_admin_required(view):
    """Stricter than admin_required: only for actions a regular teacher
    account shouldn't be able to do, like creating/removing other admin
    accounts. Re-checks the role from the database rather than trusting
    the session, in case it changed after login."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        admin = session.get("role") == "admin" and models.get_admin_by_id(session.get("user_id"))
        if not admin:
            session.clear()
            flash("Please log in as an admin to continue.", "error")
            return redirect(url_for("auth.login"))
        if admin["role"] != "super_admin":
            flash("Only a super admin can do that.", "error")
            return redirect(url_for("admin.dashboard"))
        return view(*args, **kwargs)

    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "student" or not models.get_student_by_id(session.get("user_id")):
            session.clear()
            flash("Your session is no longer valid (the account may have been removed). Please log in again.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped
