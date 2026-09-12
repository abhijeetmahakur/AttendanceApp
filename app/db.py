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

    seed_default_admin()


def seed_default_admin():
    db = get_db()
    existing = db.execute("SELECT id FROM admins LIMIT 1").fetchone()
    if existing:
        return

    username = current_app.config["DEFAULT_ADMIN_USERNAME"]
    password = current_app.config["DEFAULT_ADMIN_PASSWORD"]
    db.execute(
        "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
        (username, generate_password_hash(password)),
    )
    db.commit()
    click.echo(
        f" * Created default admin account -> username: {username!r}, "
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
