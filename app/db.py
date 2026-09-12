import os
import sqlite3

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db_path = current_app.config["DATABASE_PATH"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    db = get_db()
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()

    _migrate_schema(db)
    seed_default_admin()

    # Local import: models imports get_db() from this module, so importing
    # it at module load time here would be circular. By call time (init_db
    # only ever runs inside an app context, after both modules are loaded)
    # this is safe.
    from . import models

    models.seed_holidays_if_empty()
    models.seed_timetable_if_empty()


def _migrate_schema(db):
    """Adds columns introduced after a database's initial creation.
    CREATE TABLE IF NOT EXISTS in schema.sql won't add columns to a table
    that already exists, so new nullable columns are migrated in here."""
    existing_cols = {row["name"] for row in db.execute("PRAGMA table_info(class_sessions)").fetchall()}
    if "lecture" not in existing_cols:
        db.execute("ALTER TABLE class_sessions ADD COLUMN lecture TEXT")
    if "source" not in existing_cols:
        db.execute("ALTER TABLE class_sessions ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")

    admin_cols = {row["name"] for row in db.execute("PRAGMA table_info(admins)").fetchall()}
    added_role = False
    if "role" not in admin_cols:
        db.execute("ALTER TABLE admins ADD COLUMN role TEXT NOT NULL DEFAULT 'teacher'")
        added_role = True
    if "email" not in admin_cols:
        db.execute("ALTER TABLE admins ADD COLUMN email TEXT")
    if "phone" not in admin_cols:
        db.execute("ALTER TABLE admins ADD COLUMN phone TEXT")
    if added_role:
        # Every admin account that existed before roles were introduced
        # already had full access - promote them all rather than silently
        # downgrading existing admins to the more restricted 'teacher' role.
        db.execute("UPDATE admins SET role = 'super_admin'")

    student_cols = {row["name"] for row in db.execute("PRAGMA table_info(students)").fetchall()}
    if "phone" not in student_cols:
        db.execute("ALTER TABLE students ADD COLUMN phone TEXT")
    if "roll_no" not in student_cols:
        db.execute("ALTER TABLE students ADD COLUMN roll_no INTEGER")
    if "registration_no" not in student_cols:
        db.execute("ALTER TABLE students ADD COLUMN registration_no TEXT")
    if "account_status" not in student_cols:
        # Every student that existed before signup/approval was introduced
        # already has a real password set by an admin - default to 'active'
        # so nobody who could already log in gets locked out.
        db.execute("ALTER TABLE students ADD COLUMN account_status TEXT NOT NULL DEFAULT 'active'")

    db.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_students_registration_no
           ON students(registration_no) WHERE registration_no IS NOT NULL"""
    )

    db.commit()


def seed_default_admin():
    db = get_db()
    existing = db.execute("SELECT id FROM admins LIMIT 1").fetchone()
    if existing:
        return

    username = current_app.config["DEFAULT_ADMIN_USERNAME"]
    password = current_app.config["DEFAULT_ADMIN_PASSWORD"]
    db.execute(
        "INSERT INTO admins (username, password_hash, role) VALUES (?, ?, 'super_admin')",
        (username, generate_password_hash(password)),
    )
    db.commit()
    click.echo(
        f" * Created default super admin account -> username: {username!r}, "
        f"password: {password!r} (change this after logging in)"
    )


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    db_exists = os.path.exists(app.config["DATABASE_PATH"])
    with app.app_context():
        init_db()
    if not db_exists:
        app.logger.info("Initialized a new attendance database.")


@click.command("init-db")
def init_db_command():
    """Drop/recreate tables is NOT done here; this just ensures schema + default admin exist."""
    init_db()
    click.echo("Database initialized.")
