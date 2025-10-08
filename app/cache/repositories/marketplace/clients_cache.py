"""
Repositório para cache de clientes de marketplace.

Este módulo implementa o repositório para cache de clientes de marketplace,
utilizando o padrão Cache-Aside com Redis como backend de cache.
"""

import logging
from typing import Any, Dict, List, Optional

from app.cache.base import Repository
from app.cache.config import CacheConfig
from app.cache.redis_timeline import RedisTimelineCache
from app.cache.repositories.marketplace.client_extractors.registry import get_client_extractor_registry

logger = logging.getLogger(__name__)


class ClientsCache(Repository[Dict[str, Any]]):
    """
    Repositório para cache de clientes de marketplace.

    Implementa o padrão Cache-Aside para dados de clientes de marketplace,
    utilizando Redis como backend de cache e schema para serialização.
    """

    def __init__(self):
        """
        Inicializa o repositório com a estratégia de cache para clientes.
        """
        ttl = CacheConfig.get_ttl("clients")

        # Define padrões de chaves personalizados para clients
        self.key_patterns = {"external": "clients:{marketplace_type}:{marketplace_shop_id}:{client_id}", "user_timeline": "user:{pin}:clients:timeline"}

        cache_strategy = RedisTimelineCache[Dict[str, Any]](entity_type="clients", ttl_seconds=ttl, key_patterns=self.key_patterns)
        super().__init__(cache_strategy, schema_factory=None)

        # Registry de extratores para diferentes marketplaces
        self._extractor_registry = get_client_extractor_registry()

    def _format_client_key(self, marketplace_type: str, marketplace_shop_id: str, client_id: str) -> str:
        """Formata a chave externa do cliente."""
        return self.key_patterns["external"].format(marketplace_type=marketplace_type, marketplace_shop_id=marketplace_shop_id, client_id=client_id)

    def _format_user_timeline_key(self, pin: str) -> str:
        """Formata a chave da timeline do usuário."""
        return self.key_patterns["user_timeline"].format(pin=pin)

    def parse_id_from_key(self, key: str) -> Optional[str]:
        """Interpreta o ID do cliente a partir da chave formatada."""
        try:
            parts = key.split(":")
            if len(parts) >= 4 and parts[0] == "clients":
                return parts[3]
            return None
        except Exception:
            return None

    def get_from_database(self, client_id: str) -> Optional[Dict[str, Any]]:
        return None

    def save_to_database(self, client_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    def get_client(self, client_id: str, marketplace_type: str, marketplace_shop_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca um cliente específico pelo ID.

        Args:
            client_id: ID do cliente
            marketplace_type: Tipo do marketplace
            marketplace_shop_id: ID da conta no marketplace

        Returns:
            Dados do cliente ou None se não encontrado
        """
        key = self._format_client_key(marketplace_type, marketplace_shop_id, client_id)
        return self.cache.get(key) or self._load_client_from_db(client_id, marketplace_type, marketplace_shop_id)

    def get_account_clients(self, marketplace_shop_id: str, pin: str, marketplace_type: str) -> List[Dict[str, Any]]:
        """
        Busca todos os clientes de uma conta específica.

        Args:
            marketplace_shop_id: ID da conta no marketplace
            pin: PIN do usuário
            marketplace_type: Tipo do marketplace

        Returns:
            Lista de clientes da conta
        """
        try:
            # Verifica se é um colaborador
            from app.services.user.models import users
            from app.utils.context_manager import get_db_session

            with get_db_session() as db:
                user = db.query(users).filter(users.pin == pin).first()

                if not user:
                    return []

                # Se for colaborador, usa o PIN do master para a timeline
                master_pin = user.master_pin if user.is_colab else None
                timeline_pin = master_pin if master_pin else pin

                # Busca clientes pela timeline do usuário
                timeline_key = self._format_user_timeline_key(timeline_pin)
                client_keys = self.cache.redis.smembers(timeline_key)

                if not client_keys:
                    return []

                # Converte bytes para string se necessário
                keys_str = [key.decode("utf-8") if isinstance(key, bytes) else key for key in client_keys]

                # Filtra chaves da conta específica
                prefix = f"clients:{marketplace_type}:{marketplace_shop_id}:"
                matching_keys = [k for k in keys_str if isinstance(k, str) and k.startswith(prefix)]

                if not matching_keys:
                    return []

                # Busca os dados dos clientes
                clients_data = self.get_many(matching_keys)

                # Limpa referências inválidas e renova TTL
                for ref_key, payload in clients_data.items():
                    if payload is None:
                        self.cache.redis.srem(timeline_key, ref_key)

                # Retorna apenas clientes válidos
                return [client for client in clients_data.values() if client is not None]

        except Exception as e:
            logger.error(f"Erro ao buscar clientes da conta {marketplace_shop_id}: {e}")
            return []

    def _load_clients_from_orders(self, marketplace_shop_id: str, pin: str, marketplace_type: str) -> List[Dict[str, Any]]:
        """
        Carrega clientes a partir dos pedidos existentes no cache.

        Args:
            marketplace_shop_id: ID da conta no marketplace
            pin: PIN do usuário
            marketplace_type: Tipo do marketplace

        Returns:
            Lista de clientes extraídos dos pedidos
        """
        try:
            # Busca pedidos da conta
            from app.cache.repositories.marketplace.meli.claims_cache import MeliClaimsCache
            from app.cache.repositories.marketplace.meli.orders_cache import MeliOrdersCache

            orders_repo = MeliOrdersCache()
            orders = orders_repo.get_account_orders(marketplace_shop_id, pin, marketplace_type)

            if not orders:
                logger.info(f"Nenhum pedido encontrado para a conta {marketplace_shop_id}")
                return []

            # Agrupa pedidos por cliente e cria índices de relacionamento
            clients_map: Dict[str, Dict[str, Any]] = {}
            order_to_client: Dict[str, str] = {}
            shipping_to_client: Dict[str, str] = {}

            for order in orders:
                # Extrai dados do cliente usando o extrator apropriado
                client_data = self._extractor_registry.extract_client_from_order(order, marketplace_type)

                if not client_data:
                    continue

                client_id = client_data.get("client_id")
                if not client_id:
                    continue

                # Índices de relacionamento (pedido e envio)
                order_id = str(order.get("order_id")) if order.get("order_id") is not None else None
                if order_id:
                    order_to_client[order_id] = client_id
                shipping_id = str(order.get("shipping_id")) if order.get("shipping_id") else None
                if shipping_id:
                    shipping_to_client[shipping_id] = client_id

                # Se o cliente já existe, mescla os dados
                if client_id in clients_map:
                    clients_map[client_id] = self._extractor_registry.merge_client_with_order(clients_map[client_id], order, marketplace_type)
                else:
                    base_client = client_data.copy()
                    base_client.setdefault("claims", [])
                    clients_map[client_id] = base_client

            # Integra claims relacionadas (por order/shipping ou buyer nos players)
            try:
                claims_repo = MeliClaimsCache()
                claims = claims_repo.get_claims_for_account(pin=pin, marketplace_type=marketplace_type, marketplace_shop_id=marketplace_shop_id)
            except Exception as e:
                logger.error(f"Erro ao buscar claims para enriquecimento de clientes: {e}")
                claims = []

            if claims:
                for claim in claims:
                    claimed_resource = claim.get("resource")
                    resource_id = claim.get("resource_id")
                    claim_id = str(claim.get("id")) if claim.get("id") is not None else None
                    if not claim_id:
                        continue

                    linked_client_id: Optional[str] = None

                    # 1) Relaciona por pedido
                    if claimed_resource == "order" and resource_id is not None:
                        linked_client_id = order_to_client.get(str(resource_id))

                    # 2) Relaciona por envio (shipment/shipping)
                    if linked_client_id is None and claimed_resource in {"shipment", "shipping"} and resource_id is not None:
                        linked_client_id = shipping_to_client.get(str(resource_id))

                    # 3) Fallback: relaciona por buyer nos players (não cria cliente novo)
                    if linked_client_id is None:
                        try:
                            players = claim.get("players", []) or []
                            buyer_player = next((p for p in players if p.get("type") in ("buyer", "receiver") and p.get("role") in ("complainant", "buyer")), None)
                            if buyer_player and buyer_player.get("user_id") is not None:
                                candidate_client_id = str(buyer_player.get("user_id"))
                                if candidate_client_id in clients_map:
                                    linked_client_id = candidate_client_id
                        except Exception:
                            pass

                    # Anexa referência da claim ao cliente encontrado
                    if linked_client_id and linked_client_id in clients_map:
                        client_entry = clients_map[linked_client_id]
                        claims_list = client_entry.setdefault("claims", [])
                        if claim_id not in claims_list:
                            claims_list.append(claim_id)

            # Salva clientes no cache
            saved_clients = []
            for client_id, client_data in clients_map.items():
                try:
                    # Salva no cache individual
                    client_key = self._format_client_key(marketplace_type, marketplace_shop_id, client_id)
                    self.cache.set(client_key, client_data)

                    # Adiciona à timeline do usuário
                    timeline_key = self._format_user_timeline_key(pin)
                    self.cache.redis.sadd(timeline_key, client_key)

                    saved_clients.append(client_data)

                except Exception as e:
                    logger.error(f"Erro ao salvar cliente {client_id} no cache: {e}")

            logger.info(f"Carregados {len(saved_clients)} clientes para a conta {marketplace_shop_id}")
            return saved_clients

        except Exception as e:
            logger.error(f"Erro ao carregar clientes dos pedidos para conta {marketplace_shop_id}: {e}")
            return []

    def _load_client_from_db(self, client_id: str, marketplace_type: str, marketplace_shop_id: str) -> Optional[Dict[str, Any]]:
        """
        Carrega um cliente específico do banco de dados.

        Nota: Como não salvamos clientes no banco, este método sempre retorna None.
        O carregamento real é feito através dos pedidos.

        Args:
            client_id: ID do cliente
            marketplace_type: Tipo do marketplace
            marketplace_shop_id: ID da conta no marketplace

        Returns:
            None (clientes não são persistidos no banco)
        """
        # Clientes não são persistidos no banco, apenas no cache
        # O carregamento é feito através dos pedidos
        return None
