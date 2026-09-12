import os

from flask import Flask, flash, redirect, request, session, url_for

from config import Config


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from . import db

    db.init_app(app)

    from . import mailer

    mailer.init_app(app)

    from .auth_routes import bp as auth_bp
    from .admin_routes import bp as admin_bp
    from .student_routes import bp as student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(student_bp)

    @app.errorhandler(413)
    def file_too_large(_exc):
        flash(
            f"That file is too large. The maximum attachment size is "
            f"{app.config['MAX_ATTACHMENT_SIZE_MB']}MB.",
            "error",
        )
        return redirect(request.referrer or url_for("auth.index"))

    @app.context_processor
    def inject_unread_notifications():
        if session.get("role") == "student" and session.get("user_id"):
            from . import models
            return {"unread_notifications": models.unread_notification_count(session["user_id"])}
        return {"unread_notifications": 0}

    @app.context_processor
    def inject_pending_signups():
        if session.get("role") == "admin" and session.get("user_id"):
            from . import models
            return {"pending_signups": len(models.list_pending_signups())}
        return {"pending_signups": 0}

    return app
