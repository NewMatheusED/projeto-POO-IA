"""
Configurações para o sistema de cache.

Este módulo define as configurações para o sistema de cache,
incluindo TTLs específicos por tipo de entidade e ambiente.
"""

import os

from app.flask_config import Config


class CacheConfig:
    """
    Configurações para o sistema de cache.

    Esta classe define as configurações para o sistema de cache,
    incluindo TTLs específicos por tipo de entidade e ambiente.
    """

    # Ambiente atual
    ENVIRONMENT = Config.PRODUCTION == "true" and "production" or "development"

    # TTLs padrão por tipo de entidade (em segundos)
    # Produção: TTLs mais longos para reduzir carga no banco
    # Desenvolvimento: TTLs mais curtos para facilitar testes
    TTL_CONFIG = {
        "production": {
            "uploads": 86400,  # 24 horas
            "user": 86400,  # 24 horas
            "accounts": 86400,  # 24 horas
            "ads": 2592000,  # 30 dias
            "orders": 2592000,  # 30 dias
            "visits": 2592000,  # 30 dias
            "clients": 2592000,  # 30 dias
            "claims": 2592000,  # 30 dias
        },
        "development": {
            "uploads": 86400,  # 24 horas
            "user": 86400,  # 24 horas
            "accounts": 86400,  # 24 horas
            "ads": 2592000,  # 30 dias
            "orders": 2592000,  # 30 dias
            "visits": 2592000,  # 30 dias
            "clients": 2592000,  # 30 dias
            "claims": 2592000,  # 30 dias
        },
        "testing": {
            "uploads": 86400,  # 24 horas
            "user": 86400,  # 24 horas
            "accounts": 86400,  # 24 horas
            "ads": 2592000,  # 30 dias
            "orders": 2592000,  # 30 dias
            "visits": 2592000,  # 30 dias
            "clients": 2592000,  # 30 dias
            "claims": 2592000,  # 30 dias
        },
    }

    # Configuração para tarefas de manutenção de cache
    CACHE_MAINTENANCE = {
        "production": {
            "cleanup_interval": 3600 * 6,  # 6 horas
        },
        "development": {
            "cleanup_interval": 3600,  # 1 hora
        },
        "testing": {
            "cleanup_interval": 60,  # 1 minuto
        },
    }

    @classmethod
    def get_ttl(cls, entity_type: str) -> int:
        """
        Obtém o TTL para um tipo de entidade no ambiente atual.

        Args:
            entity_type: Tipo de entidade

        Returns:
            TTL em segundos
        """
        # Se estamos em ambiente de teste
        if os.getenv("TESTING") == "true" or os.getenv("PYTEST_CURRENT_TEST"):
            return cls.TTL_CONFIG["testing"].get(entity_type, 10)

        # Ambiente normal (produção ou desenvolvimento)
        return cls.TTL_CONFIG[cls.ENVIRONMENT].get(entity_type, 300)

    @classmethod
    def get_maintenance_config(cls, config_key: str) -> int:
        """
        Obtém uma configuração de manutenção de cache para o ambiente atual.

        Args:
            config_key: Chave de configuração

        Returns:
            Valor da configuração
        """
        # Se estamos em ambiente de teste
        if os.getenv("TESTING") == "true" or os.getenv("PYTEST_CURRENT_TEST"):
            return cls.CACHE_MAINTENANCE["testing"].get(config_key, 60)

        # Ambiente normal (produção ou desenvolvimento)
        return cls.CACHE_MAINTENANCE[cls.ENVIRONMENT].get(config_key, 3600)
