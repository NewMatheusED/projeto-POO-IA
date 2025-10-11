"""
Gerenciador de tokens para serviços externos.

Implementa padrão Singleton para gerenciar tokens de acesso de forma centralizada,
seguindo princípios SOLID e facilitando a atualização dinâmica de tokens.
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from app.external.base.interfaces import OAuthCredentials
from app.services.accounts.models import marketplaceAccounts
from app.utils.context_manager import get_db_session


class TokenManager:
    """
    Gerenciador de tokens para serviços externos.

    Implementa padrão Singleton para garantir que todos os serviços
    usem os mesmos tokens atualizados.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TokenManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        """Inicializa o gerenciador de tokens."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tokens_cache: Dict[str, Tuple[str, datetime]] = {}
        self.ttl = timedelta(minutes=5)  # Tempo de vida do cache

    def get_token(self, marketplace_shop_id: str) -> Optional[str]:
        """
        Obtém token de acesso para um marketplace específico.

        Args:
            marketplace_shop_id: ID da conta do marketplace

        Returns:
            Token de acesso ou None se não encontrado
        """
        # Verifica se o token está em cache e ainda é válido
        if marketplace_shop_id in self.tokens_cache:
            token, timestamp = self.tokens_cache[marketplace_shop_id]
            if datetime.now() - timestamp < self.ttl:
                return token

        # Token não está em cache ou expirou, busca no banco
        token = self._get_token_from_db(marketplace_shop_id)

        # Atualiza o cache se encontrou o token
        if token:
            self.tokens_cache[marketplace_shop_id] = (token, datetime.now())

        return token

    def _get_token_from_db(self, marketplace_shop_id: str) -> Optional[str]:
        """
        Busca token de acesso no banco de dados.

        Args:
            marketplace_shop_id: ID da conta do marketplace

        Returns:
            Token de acesso ou None se não encontrado
        """
        try:
            with get_db_session() as db:
                account = db.query(marketplaceAccounts).filter_by(marketplace_shop_id=marketplace_shop_id).first()

                if account:
                    self.logger.debug(f"Token obtido do banco para marketplace_shop_id: {marketplace_shop_id}")
                    return account.access_token

                self.logger.warning(f"Conta não encontrada para marketplace_shop_id: {marketplace_shop_id}")
                return None
        except Exception as e:
            self.logger.error(f"Erro ao buscar token de acesso: {str(e)}")
            return None

    def update_token(self, marketplace_shop_id: str, token: str) -> None:
        """
        Atualiza token em cache (não atualiza no banco).

        Args:
            marketplace_shop_id: ID da conta do marketplace
            token: Novo token de acesso
        """
        self.tokens_cache[marketplace_shop_id] = (token, datetime.now())
        self.logger.info(f"Token atualizado em cache para marketplace_shop_id: {marketplace_shop_id}")

    def invalidate_token(self, marketplace_shop_id: str) -> None:
        """
        Invalida token em cache, forçando busca no banco na próxima chamada.

        Args:
            marketplace_shop_id: ID da conta do marketplace
        """
        if marketplace_shop_id in self.tokens_cache:
            del self.tokens_cache[marketplace_shop_id]
            self.logger.info(f"Token invalidado para marketplace_shop_id: {marketplace_shop_id}")

    def get_oauth_credentials(self, marketplace_shop_id: str) -> Optional[OAuthCredentials]:
        """
        Obtém credenciais OAuth para um marketplace específico.

        Args:
            marketplace_shop_id: ID da conta do marketplace

        Returns:
            Credenciais OAuth ou None se não encontrado
        """
        token = self.get_token(marketplace_shop_id)

        if not token:
            return None

        return OAuthCredentials(
            access_token=token,
            refresh_token="",
            expires_in=3600,
            token_type="Bearer",  # Não necessário para operações de leitura  # Valor padrão, não é relevante para as operações
        )

    def clear_cache(self) -> None:
        """Limpa todo o cache de tokens."""
        self.tokens_cache.clear()
        self.logger.info("Cache de tokens limpo")
