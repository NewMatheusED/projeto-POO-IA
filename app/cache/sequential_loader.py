"""
Carregador sequencial de cache.

Este módulo implementa uma estratégia de carregamento sequencial de cache,
que executa as etapas na ordem definida sem verificações de prontidão.
"""

import enum
import logging
from typing import Dict, List, Union

logger = logging.getLogger(__name__)


class CacheDataType(enum.Enum):
    """
    Tipos de dados para carregamento no cache.

    Define os diferentes tipos de dados que podem ser carregados no cache,
    que serão processados na ordem definida pelo usuário.
    """

    ACCOUNT_INFO = "account_info"  # Informações básicas da conta
    ADS = "ads"  # Anúncios
    ORDERS = "orders"  # Pedidos
    CLIENTS = "clients"  # Clientes (baseado nos pedidos)


class SequentialCacheLoader:
    """
    Carregador sequencial de cache.

    Implementa uma estratégia de carregamento sequencial de cache,
    executando as etapas na ordem definida sem verificações de prontidão.
    """

    def __init__(self):
        """
        Inicializa o carregador sequencial de cache.
        """
        # Dados carregados durante o ciclo, reutilizados entre etapas
        self._loaded_accounts: List[Dict] = []

    def load_cache(self, pin: str, data_types: List[Union[CacheDataType, str]], marketplace_type: str, account_id: str) -> Dict[str, bool]:
        """
        Carrega os dados no cache na ordem especificada.

        Args:
            pin: PIN do usuário
            data_types: Lista de tipos de dados na ordem desejada
            marketplace_type: Tipo de marketplace

        Returns:
            Dicionário com resultados por tipo de dado
        """
        # Resultados por tipo de dado
        results = {}

        # Processa cada tipo de dado na ordem especificada
        for data_type in data_types:
            # Converte string para enum se necessário
            if isinstance(data_type, str):
                try:
                    data_type = CacheDataType(data_type)
                except ValueError:
                    logger.warning(f"Tipo de dado desconhecido: {data_type}")
                    results[data_type] = False
                    continue

            # Carrega o tipo de dado no cache com parâmetros corretos
            try:
                logger.info(f"Carregando {data_type.value} para conta {pin}")
                if data_type == CacheDataType.ACCOUNT_INFO:
                    success = self._load_account_info(pin)
                elif data_type == CacheDataType.ADS:
                    success = self._load_ads(pin, marketplace_type, account_id)
                elif data_type == CacheDataType.ORDERS:
                    success = self._load_orders(pin, marketplace_type, account_id)
                elif data_type == CacheDataType.CLIENTS:
                    success = self._load_clients(pin, marketplace_type, account_id)
                else:
                    logger.warning(f"Função de carregamento não encontrada para {data_type.value}")
                    success = False

                results[data_type.value] = success

                if not success:
                    logger.warning(f"Falha ao carregar {data_type.value} para conta {pin}")
            except Exception as e:
                logger.error(f"Erro ao carregar {data_type.value} para conta {pin}: {e}")
                results[data_type.value] = False

        return results

    def _load_account_info(self, pin: str) -> bool:
        """
        Carrega as informações da conta no cache.

        Args:
            pin: PIN do usuário
        Returns:
            True se carregado com sucesso, False caso contrário
        """
        try:
            from app.cache.repositories.marketplace.accounts_cache import AccountsCache

            # Inicializa o repositório
            accounts_repo = AccountsCache()

            # Carrega as informações da conta
            accounts = accounts_repo.get_user_accounts(pin)
            self._loaded_accounts = accounts or []

            logger.info(f"Informações da conta {pin} carregadas no cache: {len(self._loaded_accounts)} contas")
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar informações da conta {pin} no cache: {e}")
            return False

    def _load_orders(self, pin: str, marketplace_type: str, account_id: str) -> bool:
        """
        Carrega os pedidos no cache.

        Args:
            account_id: ID da conta
            pin: PIN do usuário
            marketplace_type: Tipo de marketplace

        Returns:
            True se carregado com sucesso, False caso contrário
        """
        try:
            from app.cache.repositories.marketplace.meli.orders_cache import MeliOrdersCache

            # Garante que as contas estejam carregadas
            if not self._loaded_accounts:
                self._load_account_info(pin)

            orders_repo = MeliOrdersCache()
            _ = orders_repo.get_account_orders(account_id, pin, marketplace_type)
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar pedidos para conta {pin} no cache: {e}")
            return False

    def _load_ads(self, pin: str, marketplace_type: str, account_id: str) -> bool:
        """
        Carrega os anúncios no cache.

        Args:
            account_id: ID da conta
            pin: PIN do usuário
            marketplace_type: Tipo de marketplace

        Returns:
            True se carregado com sucesso, False caso contrário
        """
        try:
            from app.cache.repositories.marketplace.meli.ads_cache import MeliAdsCache

            # Garante que as contas estejam carregadas
            if not self._loaded_accounts:
                self._load_account_info(pin)

            ads_repo = MeliAdsCache()
            _ = ads_repo.get_account_ads(account_id, pin, marketplace_type)

            logger.info(f"Anúncios da conta {account_id} carregados no cache")

            return True
        except Exception as e:
            logger.error(f"Erro ao carregar anúncios para conta {pin} no cache: {e}")
            return False

    def _load_clients(self, pin: str, marketplace_type: str, account_id: str) -> bool:
        """
        Carrega os clientes no cache baseado nos pedidos existentes.

        Args:
            pin: PIN do usuário
            marketplace_type: Tipo do marketplace
            account_id: ID da conta

        Returns:
            True se carregado com sucesso, False caso contrário
        """
        try:
            from app.cache.repositories.marketplace.clients_cache import ClientsCache

            # Garante que as contas estejam carregadas
            if not self._loaded_accounts:
                self._load_account_info(pin)

            clients_repo = ClientsCache()

            # Carrega clientes a partir dos pedidos
            clients = clients_repo._load_clients_from_orders(account_id, pin, marketplace_type)

            if clients:
                logger.info(f"Clientes da conta {account_id} carregados no cache: {len(clients)} clientes")
                return True
            else:
                logger.info(f"Nenhum cliente encontrado para a conta {account_id}")
                return True  # Não é erro se não houver clientes

        except Exception as e:
            logger.error(f"Erro ao carregar clientes para conta {pin} no cache: {e}")
            return False
