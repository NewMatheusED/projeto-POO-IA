from flask import Blueprint

from app.middleware.auth_middleware import protect_blueprint_with_jwt_except

from app.auth.views import auth_bp
from app.services.health.views import health_bp
from app.services.ia.views import ia_bp
from app.services.ia.data_processing.views import processing_bp

blueprint_v1 = Blueprint("v1", __name__)

blueprint_v1.register_blueprint(auth_bp, url_prefix="/auth")
blueprint_v1.register_blueprint(ia_bp, url_prefix="/ia")
blueprint_v1.register_blueprint(processing_bp, url_prefix="/processing")
blueprint_v1.register_blueprint(health_bp, url_prefix="/health")


# coloca dentro do set o nome do blueprint sem o /, tal blueprint não vai ser necessario o jwt para funcionar
protect_blueprint_with_jwt_except(blueprint_v1, {"auth", "health"})
