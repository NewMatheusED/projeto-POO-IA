"""
Cache para métricas de tempo de resposta das perguntas do Mercado Livre.

Atualiza no máximo 1 vez ao dia por conta ativa.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.cache.base import Repository
from app.cache.config import CacheConfig
from app.cache.redis_timeline import RedisTimelineCache

logger = logging.getLogger(__name__)


class MeliQuestionsMetricsCache(Repository[Dict[str, Any]]):
    def __init__(self):
        # TTL padrão: 48h como segurança; vamos controlar atualização diária
        ttl = CacheConfig.get_ttl("questions_metrics")

        self.key_patterns = {
            "external": "questions_metrics:{marketplace_type}:{marketplace_shop_id}",
            "user_timeline": "user:{pin}:questions_metrics:timeline",
        }

        cache_strategy = RedisTimelineCache[Dict[str, Any]](entity_type="questions_metrics", ttl_seconds=ttl, key_patterns=self.key_patterns)
        super().__init__(cache_strategy, schema_factory=None)

    def _format_metrics_key(self, marketplace_type: str, marketplace_shop_id: str) -> str:
        return self.key_patterns["external"].format(marketplace_type=marketplace_type, marketplace_shop_id=marketplace_shop_id)

    def _format_user_timeline_key(self, pin: str) -> str:
        return self.key_patterns["user_timeline"].format(pin=pin)

    def parse_id_from_key(self, key: str) -> Optional[str]:
        try:
            parts = key.split(":")
            if len(parts) >= 3 and parts[0] == "questions_metrics":
                return parts[2]
            return None
        except Exception:
            return None

    def get_from_database(self, entity_id: str) -> Optional[Dict[str, Any]]:
        return None

    def save_to_database(self, entity_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    def should_update_today(self, payload: Optional[Dict[str, Any]]) -> bool:
        if not isinstance(payload, dict):
            return True
        updated_at = payload.get("updated_at")
        if not updated_at:
            return True
        try:
            dt = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return now.date() > dt.date()
        except Exception:
            return True

    def save_metrics(self, *, pin: str, marketplace_type: str, marketplace_shop_id: str, metrics: Dict[str, Any]) -> bool:
        payload = dict(metrics or {})
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()

        key = self._format_metrics_key(marketplace_type, marketplace_shop_id)
        stored = self.cache.set(key, payload, ttl_seconds=int(timedelta(days=2).total_seconds()))
        try:
            timeline_key = self._format_user_timeline_key(pin)
            self.cache.redis.sadd(timeline_key, key)
            self.cache.redis.expire(timeline_key, timedelta(days=4))
        except Exception as e:
            logger.error(f"Erro ao atualizar timeline metrics: {e}")
        return stored

    def get_metrics(self, *, marketplace_type: str, marketplace_shop_id: str) -> Optional[Dict[str, Any]]:
        key = self._format_metrics_key(marketplace_type, marketplace_shop_id)
        return self.cache.get(key)
