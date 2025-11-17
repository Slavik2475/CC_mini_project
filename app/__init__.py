import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    default_db_uri = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:Slvk%402475@localhost:5432/pft",
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = default_db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    from . import models  # noqa: F401
    from .routes import main_bp

    with app.app_context():
        db.create_all()
        ensure_profile_photo_column()
        seed_defaults()

    app.register_blueprint(main_bp)

    return app


DEFAULT_CATEGORIES = [
    ("Food", "expense"),
    ("Transport", "expense"),
    ("Housing", "expense"),
    ("Utilities", "expense"),
    ("Entertainment", "expense"),
    ("Salary", "income"),
]


def seed_defaults():
    from .models import User, Category

    user = User.query.get(1)
    if user is None:
        user = User(
            id=1,
            email="demo@example.com",
            password_hash="demo",
            name="Demo User",
            profile_photo_url="/static/img/profile.jpg",
        )
        db.session.add(user)
        db.session.flush()
    else:
        if not user.profile_photo_url:
            user.profile_photo_url = "/static/img/profile.jpg"
        if not user.name:
            user.name = "Demo User"

    existing_categories = Category.query.filter_by(user_id=user.id).count()
    if existing_categories == 0:
        for name, category_type in DEFAULT_CATEGORIES:
            db.session.add(
                Category(user_id=user.id, name=name, type=category_type)
            )

    db.session.commit()


def ensure_profile_photo_column():
    inspector = inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "profile_photo_url" not in columns:
        with db.engine.connect() as connection:
            connection.execute(
                text('ALTER TABLE "user" ADD COLUMN profile_photo_url VARCHAR(255)')
            )
            connection.commit()
