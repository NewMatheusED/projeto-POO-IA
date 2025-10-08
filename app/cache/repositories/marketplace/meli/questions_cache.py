"""
Repositório para cache de perguntas do Mercado Livre.

Armazena somente em cache (não persiste em banco), cada pergunta como
entidade independente, com TTL específico baseado na data de criação
da pergunta (30 dias por padrão).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.cache.base import Repository
from app.cache.config import CacheConfig
from app.cache.redis_timeline import RedisTimelineCache

logger = logging.getLogger(__name__)


class MeliQuestionsCache(Repository[Dict[str, Any]]):
    """
    Repositório para cache de perguntas do Mercado Livre.
    """

    def __init__(self):
        # TTL padrão do namespace "questions" (fallback; usamos TTL por item)
        ttl = CacheConfig.get_ttl("questions")

        self.key_patterns = {
            "external": "questions:{marketplace_type}:{marketplace_shop_id}:{question_id}",
            "user_timeline": "user:{pin}:questions:timeline",
        }

        cache_strategy = RedisTimelineCache[Dict[str, Any]](entity_type="questions", ttl_seconds=ttl, key_patterns=self.key_patterns)
        super().__init__(cache_strategy, schema_factory=None)

    def _format_question_key(self, marketplace_type: str, marketplace_shop_id: str, question_id: str) -> str:
        return self.key_patterns["external"].format(marketplace_type=marketplace_type, marketplace_shop_id=marketplace_shop_id, question_id=question_id)

    def _format_user_timeline_key(self, pin: str) -> str:
        return self.key_patterns["user_timeline"].format(pin=pin)

    # Interpretação de chave externa
    def parse_id_from_key(self, key: str) -> Optional[str]:
        try:
            parts = key.split(":")
            if len(parts) >= 4 and parts[0] == "questions":
                return parts[3]
            return None
        except Exception:
            return None

    # Perguntas não têm save/get em banco; implementações retornam None
    def get_from_database(self, entity_id: str) -> Optional[Dict[str, Any]]:
        return None

    def save_to_database(self, entity_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    def _compute_ttl_from_created_at(self, created_at: Optional[datetime], days: int = 30) -> int:
        """
        Calcula TTL em segundos como max(0, (created_at + days) - now).
        Se não houver created_at, retorna o TTL padrão do namespace.
        """
        if created_at is None:
            return int(self.cache.default_ttl)

        # Normaliza timezone
        created = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        expiry = created + timedelta(days=days)
        delta = (expiry - now).total_seconds()
        ttl_seconds = int(max(0, delta))
        return ttl_seconds

    def _parse_date(self, value: Any) -> Optional[datetime]:
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                return None
        return None

    def save_questions_for_account(
        self,
        *,
        pin: str,
        marketplace_type: str,
        marketplace_shop_id: str,
        questions: List[Dict[str, Any]],
        window_days: int = 30,
    ) -> int:
        """
        Salva perguntas individualmente no cache com TTL baseado na data de criação.

        - Cada pergunta vira uma chave: questions:{marketplace_type}:{marketplace_shop_id}:{question_id}
        - TTL por item = max(0, (created_at + window_days) - now)

        Returns: quantidade gravada
        """
        if not questions:
            return 0

        count = 0
        for q in questions:
            qid = str(q.get("id")) if q.get("id") is not None else None
            if not qid:
                continue

            created_at = self._parse_date(q.get("date_created"))
            ttl_seconds = self._compute_ttl_from_created_at(created_at, days=window_days)
            if ttl_seconds <= 0:
                # Já expirou pela janela
                continue

            key = self._format_question_key(marketplace_type, marketplace_shop_id, qid)
            stored = self.cache.set(key, q, ttl_seconds)
            if stored:
                # Mantém referência na timeline do usuário
                try:
                    user_timeline_key = self._format_user_timeline_key(pin)
                    self.cache.redis.sadd(user_timeline_key, key)
                    # Expira timeline com margem de segurança
                    expire_secs = int(max(ttl_seconds, self.cache.default_ttl)) * 2
                    self.cache.redis.expire(user_timeline_key, expire_secs)
                except Exception as e:
                    logger.error(f"Erro ao atualizar timeline de perguntas do usuário: {e}")
                count += 1
        return count

    def get_questions_for_account(self, *, pin: str, marketplace_type: str, marketplace_shop_id: str) -> List[Dict[str, Any]]:
        """
        Busca todas as perguntas de uma conta específica do cache.

        Args:
            pin: PIN do usuário
            marketplace_type: Tipo de marketplace
            marketplace_shop_id: ID da conta no marketplace

        Returns:
            Lista de perguntas da conta
        """
        try:
            # Usa timeline do usuário e filtra por prefixo da conta
            user_timeline_key = self._format_user_timeline_key(pin)
            keys = self.cache.redis.smembers(user_timeline_key)
            if not keys:
                return []
            keys_str = [k.decode("utf-8") if isinstance(k, bytes) else k for k in keys]
            prefix = f"questions:{marketplace_type}:{marketplace_shop_id}:"
            filtered_keys = [k for k in keys_str if isinstance(k, str) and k.startswith(prefix)]
            if not filtered_keys:
                return []
            values_map = self.cache.get_many(filtered_keys)
            # Limpa refs inválidas
            for ref_key, payload in values_map.items():
                if payload is None:
                    try:
                        self.cache.redis.srem(user_timeline_key, ref_key)
                    except Exception:
                        pass
            # Renova TTL da timeline
            try:
                self.cache.redis.expire(user_timeline_key, int(self.cache.default_ttl) * 2)
            except Exception:
                pass
            return [v for v in values_map.values() if v is not None]
        except Exception as e:
            logger.error(f"Erro ao buscar perguntas da conta: {e}")
            return []

    def get_question(self, *, question_id: str, marketplace_type: str, marketplace_shop_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca uma pergunta específica por ID do cache.

        Args:
            question_id: ID da pergunta
            marketplace_type: Tipo de marketplace
            marketplace_shop_id: ID da conta no marketplace

        Returns:
            Dados da pergunta ou None se não encontrada
        """
        try:
            key = self._format_question_key(marketplace_type, marketplace_shop_id, question_id)
            return self.cache.get(key)
        except Exception as e:
            logger.error(f"Erro ao buscar pergunta específica: {e}")
            return None
