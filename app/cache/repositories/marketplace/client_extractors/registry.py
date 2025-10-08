"""
Registry de extratores de dados de clientes por marketplace.

Este módulo implementa o padrão Registry para gerenciar extratores de dados
de clientes para diferentes marketplaces, seguindo o princípio Open/Closed.
"""

import logging
from typing import Any, Dict, Optional

from .base import ClientDataExtractor

logger = logging.getLogger(__name__)


class ClientExtractorRegistry:
    """
    Registry de extratores de dados de clientes por marketplace.

    Implementa o princípio Open/Closed (OCP) - aberto para extensão,
    fechado para modificação. Novos marketplaces podem ser adicionados
    sem modificar o código existente.
    """

    def __init__(self):
        """Inicializa o registry com extratores padrão."""
        self._extractors: Dict[str, ClientDataExtractor] = {}
        self._register_default_extractors()

    def _register_default_extractors(self) -> None:
        """Registra extratores padrão para marketplaces conhecidos."""
        try:
            from .meli_extractor import MeliClientDataExtractor

            self.register_extractor(MeliClientDataExtractor())
            logger.info("Extratores padrão registrados com sucesso")

        except ImportError as e:
            logger.warning(f"Erro ao registrar extratores padrão: {e}")

    def register_extractor(self, extractor: ClientDataExtractor) -> None:
        """
        Registra um novo extrator para um marketplace.

        Args:
            extractor: Instância do extrator a ser registrado
        """
        marketplace_type = extractor.get_marketplace_type()
        self._extractors[marketplace_type] = extractor
        logger.info(f"Extrator registrado para marketplace: {marketplace_type}")

    def get_extractor(self, marketplace_type: str) -> Optional[ClientDataExtractor]:
        """
        Obtém o extrator para um marketplace específico.

        Args:
            marketplace_type: Tipo do marketplace

        Returns:
            Extrator do marketplace ou None se não encontrado
        """
        return self._extractors.get(marketplace_type)

    def get_supported_marketplaces(self) -> list[str]:
        """
        Retorna lista de marketplaces suportados.

        Returns:
            Lista de tipos de marketplace suportados
        """
        return list(self._extractors.keys())

    def extract_client_from_order(self, order_data: Dict[str, Any], marketplace_type: str) -> Optional[Dict[str, Any]]:
        """
        Extrai dados do cliente a partir de um pedido usando o extrator apropriado.

        Args:
            order_data: Dados do pedido
            marketplace_type: Tipo do marketplace

        Returns:
            Dados do cliente ou None se não conseguir extrair
        """
        extractor = self.get_extractor(marketplace_type)
        if not extractor:
            logger.warning(f"Extrator não encontrado para marketplace: {marketplace_type}")
            return None

        try:
            return extractor.extract_client_data(order_data)
        except Exception as e:
            logger.error(f"Erro ao extrair dados do cliente: {e}")
            return None

    def merge_client_with_order(self, existing_client: Dict[str, Any], new_order_data: Dict[str, Any], marketplace_type: str) -> Dict[str, Any]:
        """
        Mescla dados de um novo pedido com dados existentes do cliente.

        Args:
            existing_client: Dados existentes do cliente
            new_order_data: Dados do novo pedido
            marketplace_type: Tipo do marketplace

        Returns:
            Dados atualizados do cliente
        """
        extractor = self.get_extractor(marketplace_type)
        if not extractor:
            logger.warning(f"Extrator não encontrado para marketplace: {marketplace_type}")
            return existing_client

        try:
            # Verifica se o extrator tem método de merge específico
            if hasattr(extractor, "merge_client_data"):
                return extractor.merge_client_data(existing_client, new_order_data)
            else:
                # Fallback: recria dados do cliente com todos os pedidos
                return extractor.extract_client_data(new_order_data)

        except Exception as e:
            logger.error(f"Erro ao mesclar dados do cliente: {e}")
            return existing_client


# Instância global do registry
_client_extractor_registry = ClientExtractorRegistry()


def get_client_extractor_registry() -> ClientExtractorRegistry:
    """
    Obtém a instância global do registry de extratores.

    Returns:
        Instância do registry de extratores
    """
    return _client_extractor_registry
