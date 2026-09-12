from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from . import auth, models
from .validators import validate_password, validate_registration_no

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
            student_row = models.get_student_by_reg_no(reg_no)

            if not student_row:
                flash("Invalid registration number or password.", "error")
            elif student_row["account_status"] == "unclaimed":
                flash(
                    "This account hasn't been set up yet. Use \"Sign Up\" below to create your password first.",
                    "error",
                )
            elif student_row["account_status"] == "pending":
                flash("Your sign-up request is awaiting teacher approval. Please check back soon.", "error")
            else:
                student = models.verify_student(reg_no, password)
                if student:
                    auth.login_student(student)
                    return redirect(url_for("student.dashboard"))
                flash("Invalid registration number or password.", "error")

        else:
            flash("Please choose a login type.", "error")

    return render_template("auth/login.html")


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        registration_no = request.form.get("registration_no", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        reg_ok, reg_error = validate_registration_no(registration_no)
        password_ok, password_error = validate_password(password)

        if not reg_ok:
            flash(reg_error, "error")
        elif not email:
            flash("Email is required.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        elif not password_ok:
            flash(password_error, "error")
        else:
            status, _student = models.student_signup(registration_no, password, email, phone)
            if status == "not_found":
                flash(
                    "That registration number wasn't found on the roster. "
                    "Ask your teacher to make sure it has been added first.",
                    "error",
                )
            elif status == "already_active":
                flash("This account already has a password set - please use Login instead.", "error")
            elif status == "already_pending":
                flash("A sign-up request for this registration number is already awaiting approval.", "error")
            else:
                flash(
                    "Sign-up request submitted! A teacher must approve it before you can log in.",
                    "success",
                )
                return redirect(url_for("auth.login"))

    return render_template("auth/signup.html")


@bp.route("/logout")
def logout():
    auth.logout()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
