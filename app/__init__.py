import logging
import os

from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate

from app.auth.jwt_handlers import register_jwt_handlers
from app.config.cors import CORSConfig
from app.database import db, init_db
from app.flask_config import Config

# Inicialização das extensões
jwt = JWTManager()
migrate = Migrate()
ma = Marshmallow()

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources=CORSConfig.get_api_cors_config())
    jwt.init_app(app)
    register_jwt_handlers(jwt)
    init_db(app)
    ma.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(os.path.dirname(__file__), "migrations"))

    from app.api.v1.blueprints import blueprint_v1 as api_v1_bp

    app.register_blueprint(api_v1_bp, url_prefix="/v1")

    return app
