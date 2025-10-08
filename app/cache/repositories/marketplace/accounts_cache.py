"""
Repositório para cache de contas de marketplace.

Este módulo implementa o repositório para cache de contas de marketplace,
utilizando o padrão Cache-Aside com Redis como backend de cache.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from app.cache.base import Repository
from app.cache.config import CacheConfig
from app.cache.redis_timeline import RedisTimelineCache
from app.services.accounts.models import marketplaceAccounts
from app.services.accounts.schema import create_accounts_response_schema
from app.services.user.models import users
from app.utils.context_manager import get_db_session

logger = logging.getLogger(__name__)


class AccountsCache(Repository[Dict[str, Any]]):
    """
    Repositório para cache de contas de marketplace.

    Implementa o padrão Cache-Aside para dados de contas de marketplace,
    utilizando Redis como backend de cache e schema para serialização.
    """

    def __init__(self):
        """
        Inicializa o repositório com a estratégia de cache para contas.
        """
        ttl = CacheConfig.get_ttl("accounts")

        # Define padrões de chaves personalizados para accounts
        key_patterns = {"external": "account:{marketplace_type}:{marketplace_shop_id}", "user_timeline": "user:{pin}:accounts:timeline"}

        cache_strategy = RedisTimelineCache[Dict[str, Any]](entity_type="accounts", ttl_seconds=ttl, key_patterns=key_patterns)
        super().__init__(cache_strategy, schema_factory=create_accounts_response_schema)

        # Mantém referência aos padrões para uso nos métodos
        self.key_patterns = key_patterns

    def _format_account_key(self, marketplace_type: str, marketplace_shop_id: str) -> str:
        """Formata a chave externa da conta."""
        return self.key_patterns["external"].format(marketplace_type=marketplace_type, marketplace_shop_id=marketplace_shop_id)

    def _format_user_timeline_key(self, pin: str) -> str:
        """Formata a chave da timeline do usuário."""
        return self.key_patterns["user_timeline"].format(pin=pin)

    # Permite que o base interprete chaves externas em get/get_many
    def parse_id_from_key(self, key: str) -> Optional[str]:
        try:
            parts = key.split(":")
            if len(parts) >= 3 and parts[0] == "account":
                return parts[2]
            return None
        except Exception:
            return None

    def get_from_database(self, account_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca dados da conta do banco de dados.

        Args:
            account_id: ID da conta (marketplace_shop_id)

        Returns:
            Dados da conta ou None se não encontrada
        """
        try:
            with get_db_session() as db:
                account = db.query(marketplaceAccounts).filter(marketplaceAccounts.marketplace_shop_id == account_id).first()

                if not account:
                    return None

                # Serializa ainda dentro da sessão para evitar DetachedInstance
                return self.apply_schema(account, many=False)
        except Exception as e:
            logger.error(f"Erro ao buscar conta do banco: {e}")
            return None
        finally:
            db.close()

    def save_to_database(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upsert de dados da conta no banco de dados. Atualiza somente campos enviados.

        Args:
            account_data: Dados da conta a serem atualizados/inseridos

        Returns:
            Dados da conta atualizados
        """
        try:
            with get_db_session() as db:
                if not account_data.get("marketplace_shop_id"):
                    raise ValueError("Campo 'marketplace_shop_id' é obrigatório")

                account = db.query(marketplaceAccounts).filter(marketplaceAccounts.marketplace_shop_id == account_data["marketplace_shop_id"]).first()

                if not account:
                    # Inserção requer payload mínimo
                    required_fields = ["marketplace_shop_id", "user_pin", "marketplace_name"]
                    missing = [f for f in required_fields if not account_data.get(f)]
                    if missing:
                        raise ValueError(f"Campos obrigatórios ausentes para inserir conta: {missing}")
                    account = marketplaceAccounts(marketplace_shop_id=account_data["marketplace_shop_id"], user_pin=account_data["user_pin"], marketplace_name=account_data["marketplace_name"])
                    db.add(account)

                # Atualiza parcialmente
                updatable_fields = ["marketplace_name", "marketplace_image", "status_parse", "orders_parse_status"]
                for field in updatable_fields:
                    if field in account_data and account_data[field] is not None:
                        setattr(account, field, account_data[field])

                db.commit()
                db.refresh(account)

                return account
        except Exception as e:
            logger.error(f"Erro ao salvar conta no banco: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def get_account(self, account_id: str, marketplace_type: str) -> Optional[Dict[str, Any]]:
        """
        Busca dados da conta utilizando o padrão Cache-Aside.

        Args:
            account_id: ID da conta (marketplace_shop_id)
            marketplace_type: Tipo de marketplace

        Returns:
            Dados da conta ou None se não encontrada
        """
        # Usa os padrões definidos no repositório
        key = self._format_account_key(marketplace_type, account_id)
        return self.cache.get(key) or self._load_account_from_db(account_id, marketplace_type)

    def _load_account_from_db(self, account_id: str, marketplace_type: str) -> Optional[Dict[str, Any]]:
        """
        Carrega a conta do banco de dados e armazena no cache.

        Args:
            account_id: ID da conta (marketplace_shop_id)
            marketplace_type: Tipo de marketplace

        Returns:
            Dados da conta ou None se não encontrada
        """
        account_data = self.get_from_database(account_id)
        if account_data:
            # Armazena no cache com a nova estrutura de chaves (chave externa)
            key = self._format_account_key(marketplace_type, account_id)
            self.cache.set(key, account_data)

            # Adiciona referência à timeline do usuário (não armazena dados)
            user_pin = account_data.get("user_pin")
            if user_pin:
                timeline_key = self._format_user_timeline_key(user_pin)
                self.cache.redis.sadd(timeline_key, key)
                self.cache.redis.expire(timeline_key, timedelta(seconds=self.cache.default_ttl * 2))
        return account_data

    def get_user_accounts(self, pin: str) -> List[Dict[str, Any]]:
        """
        Busca todas as contas de um usuário.

        Args:
            pin: PIN do usuário

        Returns:
            Lista de contas do usuário
        """
        try:
            # Verifica se é um colaborador
            with get_db_session() as db:
                user = db.query(users).filter(users.pin == pin).first()

                if not user:
                    return []

                # Se for colaborador, usa o PIN do master para a timeline
                master_pin = user.master_pin if user.is_colab else None
                timeline_pin = master_pin if master_pin else pin

                # Busca contas pela timeline do usuário
                timeline_key = self._format_user_timeline_key(timeline_pin)
                account_keys = self.cache.redis.smembers(timeline_key)

                if account_keys:
                    # Lê referências e usa get_many (com hidratação embutida via base)
                    keys_str = [key.decode("utf-8") if isinstance(key, bytes) else key for key in account_keys]
                    values_map = self.get_many(keys_str)

                    # Remove referências inválidas e renova TTL do SET
                    for ref_key, payload in values_map.items():
                        if payload is None:
                            self.cache.redis.srem(timeline_key, ref_key)
                    self.cache.redis.expire(timeline_key, timedelta(seconds=self.cache.default_ttl * 2))

                    if values_map:
                        logger.info(f"Contas do usuário {timeline_pin} resolvidas via timeline: {len(values_map)} contas")
                        return [v for v in values_map.values() if v is not None]

                # Busca do banco
                accounts = db.query(marketplaceAccounts).filter(marketplaceAccounts.user_pin == pin).all()

                # Serializa dentro da sessão para evitar DetachedInstance
                accounts_list = self.apply_schema(accounts, many=True)

                # Armazena cada conta individualmente no cache com a nova estrutura
                for account in accounts_list:
                    account_id = account["marketplace_shop_id"]
                    marketplace_type = account.get("marketplace_type")

                    # Armazena na estrutura principal de contas (chave externa)
                    account_key = self._format_account_key(marketplace_type, account_id)
                    self.cache.set(account_key, account)

                    # Adiciona referência à timeline do usuário
                    timeline_key = self._format_user_timeline_key(timeline_pin)
                    self.cache.redis.sadd(timeline_key, account_key)
                    self.cache.redis.expire(timeline_key, timedelta(seconds=self.cache.default_ttl * 2))

                return accounts_list
        except Exception as e:
            logger.error(f"Erro ao buscar contas do usuário: {e}")
            return []
        finally:
            db.close()

    def after_save_update_cache(self, id: str, saved_entity: Dict[str, Any]) -> None:
        """
        Após salvar uma conta, garante referência na timeline do usuário dono da conta.

        Requer id no formato account:{marketplace_type}:{marketplace_shop_id}
        """
        try:
            user_pin = saved_entity.get("user_pin")
            if not user_pin:
                return
            timeline_key = self._format_user_timeline_key(user_pin)
            self.add_reference_to_sets(id, [timeline_key])
        except Exception as e:
            logger.error(f"after_save_update_cache(AccountsCache) falhou: {e}")
