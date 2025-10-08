"""
Extratores de dados de clientes para diferentes marketplaces.

Este módulo contém interfaces e implementações para extrair dados de clientes
a partir dos pedidos de diferentes marketplaces.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ClientDataExtractor(ABC):
    """
    Interface base para extração de dados de clientes dos pedidos.

    Segue o princípio da Inversão de Dependência (DIP) - módulos de alto nível
    não dependem de módulos de baixo nível, ambos dependem de abstrações.
    """

    @abstractmethod
    def extract_client_data(self, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extrai dados do cliente a partir dos dados do pedido.

        Args:
            order_data: Dados completos do pedido

        Returns:
            Dados do cliente ou None se não encontrar
        """
        pass

    @abstractmethod
    def get_marketplace_type(self) -> str:
        """
        Retorna o tipo de marketplace suportado por este extrator.

        Returns:
            Tipo do marketplace (ex: 'meli', 'amazon', etc.)
        """
        pass

    def _normalize_client_data(self, raw_client_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza dados do cliente para formato padrão.

        Args:
            raw_client_data: Dados brutos do cliente

        Returns:
            Dados normalizados do cliente
        """
        return {
            "client_id": raw_client_data.get("client_id"),
            "nickname": raw_client_data.get("nickname"),
            "orders": raw_client_data.get("orders", []),
            "claims": raw_client_data.get("claims", []),  # Preparado para futuras reclamações
            "total_orders": raw_client_data.get("total_orders", 0),
            "total_spent": raw_client_data.get("total_spent", 0),
            "first_order_date": raw_client_data.get("first_order_date"),
            "last_order_date": raw_client_data.get("last_order_date"),
        }
