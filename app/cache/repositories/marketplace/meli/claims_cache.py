"""
Repositório para cache de reclamações (claims) do Mercado Livre.

- Somente cache (não persiste em banco)
- TTL dinâmico baseado na data de criação (janela de 30 dias por padrão)
- Chaves por item: claims:{marketplace_type}:{marketplace_shop_id}:{claim_id}
- Timeline por usuário: user:{pin}:claims:timeline
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.cache.base import Repository
from app.cache.config import CacheConfig
from app.cache.redis_timeline import RedisTimelineCache

logger = logging.getLogger(__name__)


class MeliClaimsCache(Repository[Dict[str, Any]]):
    def __init__(self):
        ttl = CacheConfig.get_ttl("claims")
        self.key_patterns = {
            "external": "claims:{marketplace_type}:{marketplace_shop_id}:{claim_id}",
            "user_timeline": "user:{pin}:claims:timeline",
        }
        cache_strategy = RedisTimelineCache[Dict[str, Any]](entity_type="claims", ttl_seconds=ttl, key_patterns=self.key_patterns)
        super().__init__(cache_strategy, schema_factory=None)

    def _format_claim_key(self, marketplace_type: str, marketplace_shop_id: str, claim_id: str) -> str:
        return self.key_patterns["external"].format(marketplace_type=marketplace_type, marketplace_shop_id=marketplace_shop_id, claim_id=claim_id)

    def _format_user_timeline_key(self, pin: str) -> str:
        return self.key_patterns["user_timeline"].format(pin=pin)

    def parse_id_from_key(self, key: str) -> Optional[str]:
        try:
            parts = key.split(":")
            if len(parts) >= 4 and parts[0] == "claims":
                return parts[3]
            return None
        except Exception:
            return None

    def get_from_database(self, entity_id: str) -> Optional[Dict[str, Any]]:
        return None

    def save_to_database(self, entity_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

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

    def _compute_ttl_from_created_at(self, created_at: Optional[datetime], days: int = 30) -> int:
        if created_at is None:
            return int(self.cache.default_ttl)
        created = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        expiry = created + timedelta(days=days)
        return int(max(0, (expiry - now).total_seconds()))

    def save_claims_for_account(self, *, pin: str, marketplace_type: str, marketplace_shop_id: str, claims: List[Dict[str, Any]], window_days: int = 30) -> int:
        if not claims:
            return 0
        count = 0
        for c in claims:
            cid = str(c.get("id")) if c.get("id") is not None else None
            if not cid:
                continue
            created_at = self._parse_date(c.get("date_created"))
            ttl_seconds = self._compute_ttl_from_created_at(created_at, days=window_days)
            if ttl_seconds <= 0:
                continue
            key = self._format_claim_key(marketplace_type, marketplace_shop_id, cid)
            stored = self.cache.set(key, c, ttl_seconds)
            if stored:
                try:
                    user_timeline_key = self._format_user_timeline_key(pin)
                    self.cache.redis.sadd(user_timeline_key, key)
                    expire_secs = int(max(ttl_seconds, self.cache.default_ttl)) * 2
                    self.cache.redis.expire(user_timeline_key, expire_secs)
                except Exception as e:
                    logger.error(f"Erro ao atualizar timeline de claims do usuário: {e}")
                count += 1
        return count

    def get_claims_for_account(self, *, pin: str, marketplace_type: str, marketplace_shop_id: str) -> List[Dict[str, Any]]:
        try:
            user_timeline_key = self._format_user_timeline_key(pin)
            keys = self.cache.redis.smembers(user_timeline_key)
            if not keys:
                return []
            keys_str = [k.decode("utf-8") if isinstance(k, bytes) else k for k in keys]
            key = self._format_claim_key(marketplace_type, marketplace_shop_id, "")
            filtered_keys = [k for k in keys_str if isinstance(k, str) and k.startswith(key)]
            if not filtered_keys:
                return []
            values_map = self.cache.get_many(filtered_keys)
            for ref_key, payload in values_map.items():
                if payload is None:
                    try:
                        self.cache.redis.srem(user_timeline_key, ref_key)
                    except Exception:
                        pass
            try:
                self.cache.redis.expire(user_timeline_key, int(self.cache.default_ttl) * 2)
            except Exception:
                pass
            return [v for v in values_map.values() if v is not None]
        except Exception as e:
            logger.error(f"Erro ao buscar claims da conta: {e}")
            return []

    def get_claim(self, *, claim_id: str, marketplace_type: str, marketplace_shop_id: str) -> Optional[Dict[str, Any]]:
        try:
            key = self._format_claim_key(marketplace_type, marketplace_shop_id, claim_id)
            return self.cache.get(key)
        except Exception as e:
            logger.error(f"Erro ao buscar claim específica: {e}")
            return None

    def get_claims_for_order(self, *, pin: str, marketplace_type: str, marketplace_shop_id: str, order_id: str) -> List[Dict[str, Any]]:
        """Filtra claims relacionadas a um pedido (resource=order, resource_id=order_id)."""
        claims = self.get_claims_for_account(pin=pin, marketplace_type=marketplace_type, marketplace_shop_id=marketplace_shop_id)
        result: List[Dict[str, Any]] = []
        for c in claims:
            if c.get("resource") == "order" and str(c.get("resource_id")) == str(order_id):
                result.append(c)
        return result
