import logging
import os
from datetime import timedelta

import redis

try:
    import fakeredis
except Exception:  # pragma: no cover
    fakeredis = None

from app.flask_config import Config

logger = logging.getLogger(__name__)
_logged_backend: str | None = None

TOKEN_EXPIRATION = timedelta(hours=3)


def get_redis_client():
    """
    Cliente Redis
    """
    # Ambiente de testes: usa fakeredis/mocks para isolar CI e unit tests
    if os.getenv("TESTING") == "true" or os.getenv("PYTEST_CURRENT_TEST"):
        if fakeredis is None:
            raise RuntimeError("fakeredis não está instalado. Adicione 'fakeredis' às dependências de testes.")
        return fakeredis.FakeRedis(decode_responses=True)

    return _get_standalone_client()


def _get_standalone_client():
    """Cliente Redis standalone para desenvolvimento"""
    redis_url = Config.REDIS_URL
    return redis.Redis.from_url(redis_url)
