from functools import wraps

from flask import flash, redirect, session, url_for


def login_admin(admin_row):
    session.clear()
    session["role"] = "admin"
    session["user_id"] = admin_row["id"]
    session["display_name"] = admin_row["username"]


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
        if session.get("role") != "admin":
            flash("Please log in as an admin to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "student":
            flash("Please log in with your registration number to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped
