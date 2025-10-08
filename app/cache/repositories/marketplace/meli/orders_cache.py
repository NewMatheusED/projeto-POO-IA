"""
Repositório para cache de pedidos do Mercado Livre.

Este módulo implementa o repositório para cache de pedidos do Mercado Livre,
utilizando o padrão Cache-Aside com Redis como backend de cache.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from app.cache.base import Repository
from app.cache.config import CacheConfig
from app.cache.redis_timeline import RedisTimelineCache
from app.services.orders.models import generalOrders, meliOrders
from app.services.orders.schema import create_meli_order_schema
from app.utils.context_manager import get_db_session

logger = logging.getLogger(__name__)


class MeliOrdersCache(Repository[Dict[str, Any]]):
    """
    Repositório para cache de pedidos do Mercado Livre.
    """

    def __init__(self):
        """
        Inicializa o repositório com a estratégia de cache para pedidos.
        """
        ttl = CacheConfig.get_ttl("orders")

        self.key_patterns = {"external": "orders:{marketplace_type}:{marketplace_shop_id}:{order_id}", "user_timeline": "user:{pin}:orders:timeline"}

        cache_strategy = RedisTimelineCache[Dict[str, Any]](entity_type="orders", ttl_seconds=ttl, key_patterns=self.key_patterns)
        super().__init__(cache_strategy, schema_factory=create_meli_order_schema)

    def _format_order_key(self, marketplace_type: str, marketplace_shop_id: str, order_id: str) -> str:
        """Formata a chave externa do pedido."""
        return self.key_patterns["external"].format(marketplace_type=marketplace_type, marketplace_shop_id=marketplace_shop_id, order_id=order_id)

    def _format_user_timeline_key(self, pin: str) -> str:
        """Formata a chave da timeline do usuário."""
        return self.key_patterns["user_timeline"].format(pin=pin)

    # Permite que o base interprete chaves externas em get/get_many
    def parse_id_from_key(self, key: str) -> Optional[str]:
        try:
            parts = key.split(":")
            # Esperado: orders:{marketplace_type}:{marketplace_shop_id}:{order_id}
            if len(parts) >= 4 and parts[0] == "orders":
                return parts[3]
            return None
        except Exception:
            return None

    def get_from_database(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Obtém um pedido do banco de dados.

        Tenta primeiro em `general_orders` (fonte canônica). Se não existir,
        tenta resolver via `meli_orders` e então obter o `general_order` relacionado.
        """
        try:
            with get_db_session() as db:
                # 1) Tenta buscar direto na tabela canônica
                general_order = db.query(generalOrders).filter(generalOrders.order_id == order_id).first()
                if not general_order:
                    # 2) Fallback: resolve pelo detalhe específico e então busca o canônico
                    meli_order = db.query(meliOrders).filter(meliOrders.order_id == order_id).first()
                    if not meli_order:
                        return None
                    general_order = db.query(generalOrders).filter(generalOrders.id == meli_order.general_order_id).first()
                    if not general_order:
                        return None

                # Serializa dentro da sessão para evitar DetachedInstance
                return self.apply_schema(general_order, many=False)

        except Exception as e:
            logger.error(f"Erro ao buscar pedido do banco: {e}")
            return None
        finally:
            db.close()

    def save_to_database(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Salva um pedido no banco de dados."""
        try:
            with get_db_session() as db:
                order = meliOrders(**order_data)
                db.add(order)
                db.commit()
                return order_data
        except Exception as e:
            logger.error(f"Erro ao salvar pedido no banco: {e}")
            return None
        finally:
            db.close()

    def get_order(self, order_id: str, marketplace_type: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Busca um pedido"""
        if account_id:
            key = self._format_order_key(marketplace_type, account_id, order_id)
            return self.cache.get(key) or self._load_order_from_db(order_id, marketplace_type, account_id)
        return self.get(order_id)

    def _load_order_from_db(self, order_id: str, marketplace_type: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Carrega um pedido do banco de dados e armazena no cache."""
        order_data = self.get_from_database(order_id)
        if order_data:
            key = self._format_order_key(marketplace_type, account_id, order_id)
            self.cache.set(key, order_data)
        return order_data

    def get_account_orders(self, account_id: str, pin: str, marketplace_type: str) -> List[Dict[str, Any]]:
        """
        Busca todos os pedidos de uma conta.

        Args:
            account_id: ID da conta (marketplace_shop_id)
            pin: PIN do usuário
            marketplace_type: Tipo de marketplace

        Returns:
            Lista de pedidos da conta
        """
        try:
            # Verifica se é um colaborador
            with get_db_session() as db:
                from app.services.user.models import users

                user = db.query(users).filter(users.pin == pin).first()

                if not user:
                    return []

                # Se for colaborador, usa o PIN do master para a timeline
                master_pin = user.master_pin if user.is_colab else None
                timeline_pin = master_pin if master_pin else pin

                # Busca pedidos pela timeline do usuário com hidratação embutida no base
                timeline_key = self._format_user_timeline_key(timeline_pin)
                order_keys = self.cache.redis.smembers(timeline_key)
                keys_str = [key.decode("utf-8") if isinstance(key, bytes) else key for key in order_keys]
                matching_keys = [k for k in keys_str if isinstance(k, str) and k.startswith(f"orders:{marketplace_type}:{account_id}:")]
                values_map = self.get_many(matching_keys)
                # Limpa referências inválidas e renova TTL
                for ref_key, payload in values_map.items():
                    if payload is None:
                        self.cache.redis.srem(timeline_key, ref_key)
                self.cache.redis.expire(timeline_key, timedelta(seconds=self.cache.default_ttl * 2))

                existing_orders_map: Dict[str, Any] = {k: v for k, v in values_map.items() if v is not None}
                existing_keys_set: set = set(existing_orders_map.keys())

                # Busca do banco: usa sempre a canônica por conta
                generals = db.query(generalOrders).filter(generalOrders.marketplace_shop_id == account_id).all()
                if not generals:
                    return []

                orders_list = []
                for general_order in generals:
                    # Tenta enriquecer com meli_orders, mas não depende dele para criar a chave
                    meli_order = db.query(meliOrders).filter(meliOrders.order_id == general_order.order_id).first()

                    # Preferimos armazenar a forma canônica (general) no cache; se não houver detalhe específico, ainda usamos general
                    if meli_order is None:
                        order_dict = self.apply_schema(general_order, many=False)
                        order_id_for_key = str(general_order.order_id)
                    else:
                        order_dict = self.apply_schema(meli_order, many=False)
                        order_id_for_key = str(meli_order.order_id)

                    # Armazena o pedido na nova estrutura de chaves (chave externa)
                    order_key = self._format_order_key(marketplace_type, account_id, order_id_for_key)
                    if order_key not in existing_keys_set:
                        self.cache.set(order_key, order_dict)

                    # Adiciona referência à timeline do usuário
                    timeline_key = self._format_user_timeline_key(timeline_pin)
                    if order_key not in existing_keys_set:
                        self.cache.redis.sadd(timeline_key, order_key)
                    self.cache.redis.expire(timeline_key, timedelta(seconds=self.cache.default_ttl * 2))

                    orders_list.append(order_dict)

                combined = list(existing_orders_map.values()) + orders_list
                logger.info(f"Pedidos da conta {account_id} retornados: {len(combined)} (cache {len(existing_orders_map)}, novos {len(orders_list)})")
                return combined
        except Exception as e:
            logger.exception(f"Erro ao buscar pedidos da conta {account_id}: {e}")
            return []
        finally:
            db.close()

    def after_save_update_cache(self, id: str, saved_entity: Dict[str, Any]) -> None:
        """
        Após salvar um pedido, garante referência na timeline do usuário correto.

        Requer que a aplicação passe sempre o id formatado como
        orders:{marketplace_type}:{marketplace_shop_id}:{order_id}
        """
        try:
            user_pin = saved_entity.get("user_pin")
            if not user_pin:
                return
            timeline_key = self._format_user_timeline_key(user_pin)
            self.add_reference_to_sets(id, [timeline_key])
        except Exception as e:
            logger.error(f"after_save_update_cache(MeliOrdersCache) falhou: {e}")
