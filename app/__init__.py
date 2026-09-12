from flask import Flask

from config import Config


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)

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

    return app
