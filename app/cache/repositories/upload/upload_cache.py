"""
Repositório para cache de uploads de arquivos.

Este módulo implementa o repositório para cache de uploads,
utilizando o padrão Cache-Aside com Redis como backend de cache.
"""

import logging
from typing import Any, Dict, List, Optional

from app.cache.base import Repository
from app.cache.config import CacheConfig
from app.cache.redis_timeline import RedisTimelineCache

logger = logging.getLogger(__name__)


class UploadCache(Repository[Dict[str, Any]]):
    """
    Repositório para cache de uploads de arquivos.

    Implementa o padrão Cache-Aside para dados de upload,
    utilizando Redis como backend de cache e schema para serialização.
    """

    def __init__(self):
        """Inicializa o repositório com a estratégia de cache para uploads."""
        ttl = CacheConfig.get_ttl("uploads")

        # Define padrões de chaves personalizados (footprint reduzido)
        # external: upload:{file_id} -> value: file_key (string)
        # user_timeline: set de keys 'upload:{file_id}'
        # key_by_file_key: upload:file_key:{file_key} -> value: file_id (string)
        self.key_patterns = {
            "external": "upload:{file_id}",
            "user_timeline": "user:{pin}:uploads:timeline",
            "key_by_file_key": "upload:file_key:{file_key}",
        }

        cache_strategy = RedisTimelineCache[Dict[str, Any]](entity_type="uploads", ttl_seconds=ttl, key_patterns=self.key_patterns)
        super().__init__(cache_strategy, schema_factory=None)

    def get_from_database(self, key: str) -> Optional[Dict[str, Any]]:
        return None

    def save_to_database(self, key: str, data: Dict[str, Any]) -> bool:
        return True

    def _format_upload_key(self, file_id: str) -> str:
        """Formata a chave do upload."""
        return self.key_patterns["external"].format(file_id=file_id)

    def _format_user_timeline_key(self, pin: str) -> str:
        """Formata a chave da timeline do usuário."""
        return self.key_patterns["user_timeline"].format(pin=pin)

    def _format_file_key(self, file_key: str) -> str:
        """Formata a chave do arquivo (reversa)."""
        return self.key_patterns["key_by_file_key"].format(file_key=file_key)

    def save_upload(self, file_id: str, upload_data: Dict[str, Any], user_pin: str) -> bool:
        """
        Salva dados do upload no cache.

        Args:
            file_id: ID único do arquivo
            upload_data: Dados do upload
            user_pin: PIN do usuário

        Returns:
            True se salvo com sucesso
        """
        try:
            # Salva dados mínimos (file_id -> file_key)
            upload_key = self._format_upload_key(file_id)
            file_key_value = upload_data.get("file_key", "")
            self.cache.set(upload_key, file_key_value)

            # Adiciona à timeline do usuário
            timeline_key = self._format_user_timeline_key(user_pin)
            self.cache.redis.sadd(timeline_key, upload_key)

            # Referência reversa (file_key -> file_id)
            if file_key_value:
                file_key_ref = self._format_file_key(file_key_value)
                self.cache.set(file_key_ref, file_id)

            return True

        except Exception as e:
            logger.error(f"Erro ao salvar upload no cache: {str(e)}")
            return False

    def get_upload(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém dados do upload por ID.

        Args:
            file_id: ID único do arquivo

        Returns:
            Dados do upload ou None
        """
        try:
            upload_key = self._format_upload_key(file_id)
            file_key = self.cache.get(upload_key)
            if not file_key:
                return None
            return {"id": file_id, "file_key": file_key}
        except Exception as e:
            logger.error(f"Erro ao obter upload do cache: {str(e)}")
            return None

    def get_upload_by_file_key(self, file_key: str) -> Optional[Dict[str, Any]]:
        """
        Obtém dados do upload por file_key.

        Args:
            file_key: Chave do arquivo no R2

        Returns:
            Dados do upload ou None
        """
        try:
            file_key_ref = self._format_file_key(file_key)
            file_id = self.cache.get(file_key_ref)
            if file_id:
                return self.get_upload(file_id)
            return None
        except Exception as e:
            logger.error(f"Erro ao obter upload por file_key: {str(e)}")
            return None

    def get_user_uploads(self, user_pin: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Lista uploads de um usuário.

        Args:
            user_pin: PIN do usuário
            limit: Limite de resultados
            offset: Offset para paginação

        Returns:
            Lista de uploads
        """
        try:
            timeline_key = self._format_user_timeline_key(user_pin)
            upload_keys = list(self.cache.redis.smembers(timeline_key))

            if not upload_keys:
                return []

            # Converte bytes para string se necessário
            keys_str = [key.decode("utf-8") if isinstance(key, bytes) else key for key in upload_keys]

            # Aplica paginação
            paginated_keys = keys_str[offset : offset + limit]

            # Busca os dados mínimos (file_id, file_key)
            uploads = []
            for key in paginated_keys:
                file_key_value = self.cache.get(key)
                file_id = key.split(":", 1)[-1] if ":" in key else key
                if file_key_value:
                    uploads.append({"id": file_id, "file_key": file_key_value})

            return uploads

        except Exception as e:
            logger.error(f"Erro ao listar uploads do usuário: {str(e)}")
            return []

    def delete_upload(self, file_id: str, user_pin: str) -> bool:
        """
        Remove upload do cache.

        Args:
            file_id: ID único do arquivo
            user_pin: PIN do usuário

        Returns:
            True se removido com sucesso
        """
        try:
            # Obtém dados do upload
            upload_data = self.get_upload(file_id)
            if not upload_data:
                return False

            # Remove dados do upload
            upload_key = self._format_upload_key(file_id)
            self.cache.delete(upload_key)

            # Remove da timeline do usuário
            timeline_key = self._format_user_timeline_key(user_pin)
            self.cache.redis.srem(timeline_key, upload_key)

            # Remove referência por file_key
            file_key_value = upload_data.get("file_key", "") if isinstance(upload_data, dict) else ""
            if file_key_value:
                file_key_ref = self._format_file_key(file_key_value)
                self.cache.delete(file_key_ref)

            return True

        except Exception as e:
            logger.error(f"Erro ao remover upload do cache: {str(e)}")
            return False
