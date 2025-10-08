"""
Extrator de dados de clientes para o Mercado Livre.

Este módulo implementa a extração de dados de clientes a partir dos pedidos
do Mercado Livre, seguindo a interface ClientDataExtractor.
"""

import logging
from typing import Any, Dict, Optional

from app.services.accounts.models import MarketplaceType

from .base import ClientDataExtractor

logger = logging.getLogger(__name__)


class MeliClientDataExtractor(ClientDataExtractor):
    """
    Extrator de dados de clientes para o Mercado Livre.

    Implementa o princípio da Responsabilidade Única (SRP) - tem apenas uma razão
    para mudar: alterações na estrutura de dados de clientes do Meli.
    """

    def get_marketplace_type(self) -> str:
        """Retorna o tipo de marketplace suportado."""
        return MarketplaceType.meli.value

    def extract_client_data(self, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extrai dados do cliente a partir dos dados do pedido do Meli.

        Args:
            order_data: Dados completos do pedido do Meli

        Returns:
            Dados do cliente ou None se não encontrar
        """
        try:
            # Extrai dados do buyer do pedido
            buyer_id = order_data.get("buyer_id")
            buyer_nickname = order_data.get("buyer_nickname")

            if not buyer_id:
                logger.warning("Pedido sem buyer_id, ignorando para extração de cliente")
                return None

            # Estrutura básica do cliente
            client_data = {
                "client_id": str(buyer_id),
                "nickname": buyer_nickname or f"cliente_{buyer_id}",
                "orders": [order_data.get("order_id")],  # Lista de IDs dos pedidos
                "claims": [],  # Preparado para futuras reclamações
                "total_orders": 1,
                "total_spent": float(order_data.get("total_amount", 0)) if order_data.get("total_amount") else 0,
                "first_order_date": order_data.get("date_created"),
                "last_order_date": order_data.get("date_created"),
                "marketplace_type": MarketplaceType.meli.value,
                "marketplace_shop_id": order_data.get("marketplace_shop_id"),
            }

            return self._normalize_client_data(client_data)

        except Exception as e:
            logger.error(f"Erro ao extrair dados do cliente do pedido {order_data.get('order_id')}: {e}")
            return None

    def merge_client_data(self, existing_client: Dict[str, Any], new_order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mescla dados de um novo pedido com dados existentes do cliente.

        Args:
            existing_client: Dados existentes do cliente
            new_order_data: Dados do novo pedido

        Returns:
            Dados atualizados do cliente
        """
        try:
            order_id = new_order_data.get("order_id")

            # Adiciona o pedido à lista se não existir
            orders = existing_client.get("orders", [])
            if order_id and order_id not in orders:
                orders.append(order_id)

            # Atualiza estatísticas
            total_spent = existing_client.get("total_spent", 0)
            new_amount = float(new_order_data.get("total_amount", 0)) if new_order_data.get("total_amount") else 0

            # Atualiza datas
            first_order_date = existing_client.get("first_order_date")
            last_order_date = existing_client.get("last_order_date")
            new_order_date = new_order_data.get("date_created")

            if new_order_date:
                if not first_order_date or new_order_date < first_order_date:
                    first_order_date = new_order_date
                if not last_order_date or new_order_date > last_order_date:
                    last_order_date = new_order_date

            # Retorna dados atualizados
            updated_client = existing_client.copy()
            updated_client.update(
                {
                    "orders": orders,
                    "total_orders": len(orders),
                    "total_spent": total_spent + new_amount,
                    "first_order_date": first_order_date,
                    "last_order_date": last_order_date,
                }
            )

            return updated_client

        except Exception as e:
            logger.error(f"Erro ao mesclar dados do cliente: {e}")
            return existing_client
