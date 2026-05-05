from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager


# Declarations to insert before the create_app function:
class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


def create_app(test_config=None):
    app = Flask(__name__)

    # A secret for signing session cookies
    app.config["SECRET_KEY"] = "93220d9b340cf9a6c39bac99cce7daf220167498f91fa"

    # Code to place inside create_app, after the other app.config assignment
    app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://25_webapp_058:s4wSelAZ@mysql.lab.it.uc3m.es/25_webapp_058b"
    
    db.init_app(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'  # Set the login view
    login_manager.init_app(app)  # Initialize with the Flask app

    # Import model for user loading
    from . import model

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(model.User, int(user_id))  # Load user by ID

    # Register blueprints
    from . import main

    app.register_blueprint(main.bp)

    from .auth import bp as auth_blueprint
    app.register_blueprint(auth_blueprint)

    return app
