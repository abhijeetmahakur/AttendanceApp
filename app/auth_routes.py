from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from . import auth, models

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    role = auth.current_role()
    if role == "admin":
        return redirect(url_for("admin.dashboard"))
    if role == "student":
        return redirect(url_for("student.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role")

        if role == "admin":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            admin = models.verify_admin(username, password)
            if admin:
                auth.login_admin(admin)
                return redirect(url_for("admin.dashboard"))
            flash("Invalid admin username or password.", "error")

        elif role == "student":
            reg_no = request.form.get("reg_no", "").strip()
            password = request.form.get("password", "")
            student = models.verify_student(reg_no, password)
            if student:
                auth.login_student(student)
                return redirect(url_for("student.dashboard"))
            flash("Invalid registration number or password.", "error")

        else:
            flash("Please choose a login type.", "error")

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    auth.logout()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
