"""
Repositório para cache de cotas de upload.

Este módulo implementa o repositório para cache de cotas,
utilizando Redis para controle de rate limiting.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Tuple

from app.utils.redis import get_redis_client

logger = logging.getLogger(__name__)


class UploadQuotaCache:
    """
    Repositório para cache de cotas de upload.

    Implementa rate limiting usando Redis para prevenir spam.
    """

    def __init__(self):
        """Inicializa o repositório de cotas."""
        self.redis = get_redis_client()

    def _get_quota_key(self, user_pin: str, quota_type: str) -> str:
        """Gera chave para cota."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return f"quota:{user_pin}:{quota_type}:{today}"

    def can_upload(self, user_pin: str, file_size_mb: float, max_daily_uploads: int = 50, max_daily_size_mb: int = 500) -> Tuple[bool, str]:
        """
        Verifica se usuário pode fazer upload.

        Args:
            user_pin: PIN do usuário
            file_size_mb: Tamanho do arquivo em MB
            max_daily_uploads: Máximo de uploads por dia
            max_daily_size_mb: Máximo de tamanho por dia em MB

        Returns:
            Tupla com (pode_upload, mensagem)
        """
        try:
            # Chaves para contadores diários
            uploads_key = self._get_quota_key(user_pin, "uploads")
            size_key = self._get_quota_key(user_pin, "size_centi_mb")

            # Obtém contadores atuais
            current_uploads = int(self.redis.get(uploads_key) or 0)
            current_size = int(self.redis.get(size_key) or 0)
            file_size_centi_mb = int(round(float(file_size_mb) * 100))

            # Verifica limites
            if current_uploads >= max_daily_uploads:
                return False, f"Limite diário de uploads atingido ({max_daily_uploads})"

            if current_size + file_size_centi_mb > (max_daily_size_mb * 100):
                return False, f"Limite diário de tamanho atingido ({max_daily_size_mb:.2f}MB)"

            return True, "OK"

        except Exception as e:
            logger.error(f"Erro ao verificar cota: {str(e)}")
            return False, f"Erro interno: {str(e)}"

    def record_upload(self, user_pin: str, file_size_mb: float) -> bool:
        """
        Registra upload na cota.

        Args:
            user_pin: PIN do usuário
            file_size_mb: Tamanho do arquivo em MB

        Returns:
            True se registrado com sucesso
        """
        try:
            # Chaves para contadores diários
            uploads_key = self._get_quota_key(user_pin, "uploads")
            size_key = self._get_quota_key(user_pin, "size_centi_mb")

            # Incrementa contadores com TTL de 24 horas
            pipe = self.redis.pipeline()
            pipe.incr(uploads_key)
            pipe.expire(uploads_key, 86400)  # 24 horas
            pipe.incrby(size_key, int(round(float(file_size_mb) * 100)))
            pipe.expire(size_key, 86400)  # 24 horas
            pipe.execute()

            return True

        except Exception as e:
            logger.error(f"Erro ao registrar upload na cota: {str(e)}")
            return False

    def get_quota_info(self, user_pin: str) -> Dict[str, Any]:
        """
        Obtém informações de cota do usuário.

        Args:
            user_pin: PIN do usuário

        Returns:
            Informações da cota
        """
        try:
            # Chaves para contadores diários
            uploads_key = self._get_quota_key(user_pin, "uploads")
            size_key = self._get_quota_key(user_pin, "size_centi_mb")

            # Obtém contadores atuais
            daily_uploads = int(self.redis.get(uploads_key) or 0)
            daily_size_mb = round((int(self.redis.get(size_key) or 0)) / 100.0, 2)

            return {"user_pin": user_pin, "daily_uploads": daily_uploads, "daily_size_mb": daily_size_mb, "limits": {"max_daily_uploads": 50, "max_daily_size_mb": 500}}

        except Exception as e:
            logger.error(f"Erro ao obter cota: {str(e)}")
            return {}
