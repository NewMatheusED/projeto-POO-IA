"""
Serviço base de autenticação para APIs externas.

Implementa funcionalidades comuns para autenticação OAuth e outros métodos,
incluindo cache de tokens e renovação automática.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .config import MarketplaceConfig
from .interfaces import OAuthCredentials


class BaseAuthService:
    """Serviço base de autenticação com funcionalidades comuns."""

    def __init__(self, config: MarketplaceConfig):
        """Inicializa o serviço de autenticação."""
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._credentials_cache: Optional[OAuthCredentials] = None
        self._cache_expiry: Optional[datetime] = None

    def authenticate(self, client_id: str, client_secret: str) -> OAuthCredentials:
        """Autentica e retorna credenciais."""
        raise NotImplementedError("Método deve ser implementado pela classe filha")

    def refresh_token(self, refresh_token: str) -> OAuthCredentials:
        """Renova token de acesso."""
        raise NotImplementedError("Método deve ser implementado pela classe filha")

    def validate_token(self, token: str) -> bool:
        """Valida se o token está válido."""
        raise NotImplementedError("Método deve ser implementado pela classe filha")

    def get_cached_credentials(self) -> Optional[OAuthCredentials]:
        """Retorna credenciais em cache se ainda válidas."""
        if not self._credentials_cache or not self._cache_expiry:
            return None

        if datetime.now() >= self._cache_expiry:
            self.logger.info("Credenciais em cache expiraram")
            self._credentials_cache = None
            self._cache_expiry = None
            return None

        return self._credentials_cache

    def cache_credentials(self, credentials: OAuthCredentials) -> None:
        """Armazena credenciais em cache."""
        self._credentials_cache = credentials

        if credentials.expires_in:
            # Subtrai 5 minutos para margem de segurança
            expiry_seconds = credentials.expires_in - 300
            self._cache_expiry = datetime.now() + timedelta(seconds=expiry_seconds)
        else:
            # Se não há informação de expiração, cache por 1 hora
            self._cache_expiry = datetime.now() + timedelta(hours=1)

        self.logger.info(f"Credenciais armazenadas em cache até {self._cache_expiry}")

    def clear_cache(self) -> None:
        """Limpa cache de credenciais."""
        self._credentials_cache = None
        self._cache_expiry = None
        self.logger.info("Cache de credenciais limpo")

    def get_valid_credentials(self) -> Optional[OAuthCredentials]:
        """Retorna credenciais válidas (do cache ou renovadas)."""
        # Tenta obter do cache primeiro
        cached_credentials = self.get_cached_credentials()
        if cached_credentials:
            return cached_credentials

        # Se há refresh token em cache, tenta renovar
        if self._credentials_cache and self._credentials_cache.refresh_token:
            try:
                self.logger.info("Tentando renovar token usando refresh_token")
                new_credentials = self.refresh_token(self._credentials_cache.refresh_token)
                self.cache_credentials(new_credentials)
                return new_credentials
            except Exception as e:
                self.logger.error(f"Erro ao renovar token: {str(e)}")
                self.clear_cache()

        return None

    def _create_auth_data(self, grant_type: str, **kwargs) -> Dict[str, Any]:
        """Cria dados de autenticação padronizados."""
        data = {"grant_type": grant_type, "client_id": self.config.client_id, "client_secret": self.config.client_secret}

        if self.config.redirect_uri:
            data["redirect_uri"] = self.config.redirect_uri

        data.update(kwargs)
        return data

    def _parse_token_response(self, response_data: Dict[str, Any]) -> OAuthCredentials:
        """Converte resposta da API em objeto OAuthCredentials."""
        return OAuthCredentials(
            access_token=response_data.get("access_token", ""),
            refresh_token=response_data.get("refresh_token"),
            expires_in=response_data.get("expires_in"),
            token_type=response_data.get("token_type", "Bearer"),
        )
