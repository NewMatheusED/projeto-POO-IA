import logging
from datetime import datetime

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__)


@health_bp.get("/")
def get_health_basic():
    """
    Endpoint simples de healthcheck.
    Retorna status da aplicação e data/hora atual do servidor.
    """
    logger.info("Healthcheck solicitado")
    return (
        jsonify(
            {
                "status": "up",
                "datetime": datetime.now().isoformat(),
            }
        ),
        200,
    )