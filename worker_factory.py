# app/worker_factory.py
from flask import Flask

from app import db


def create_worker_app():
    app = Flask(__name__)
    app.config.from_object("app.flask_config.Config")
    db.init_app(app)
    # NÃO registre blueprints, middlewares, jobs, etc!
    return app
