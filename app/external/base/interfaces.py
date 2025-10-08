"""
Interfaces base para serviços externos.

Define contratos que devem ser implementados por todos os serviços externos,
garantindo consistência e facilitando testes e manutenção.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


@dataclass
class APIResponse:
    """Resposta padronizada de APIs externas."""

    status_code: int
    data: Dict[str, Any]
    headers: Dict[str, str]
    success: bool
    error_message: Optional[str] = None


# =============================================================================
# INTERFACES DE AUTENTICAÇÃO (OPCIONAIS)
# =============================================================================


@dataclass
class OAuthCredentials:
    """Credenciais OAuth 2.0."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    token_type: str = "Bearer"


@dataclass
class APIKeyCredentials:
    """Credenciais de API Key."""

    api_key: str
    header_name: str = "X-API-Key"


@dataclass
class BasicAuthCredentials:
    """Credenciais Basic Auth."""

    username: str
    password: str


# Union type para diferentes tipos de credenciais
AuthCredentials = Union[OAuthCredentials, APIKeyCredentials, BasicAuthCredentials]


class OAuthServiceInterface(ABC):
    """Interface para serviços OAuth 2.0."""

    @abstractmethod
    def authenticate(self, client_id: str, client_secret: str) -> OAuthCredentials:
        """Autentica usando client credentials."""
        pass

    @abstractmethod
    def authenticate_with_code(self, authorization_code: str) -> OAuthCredentials:
        """Autentica usando authorization code."""
        pass

    @abstractmethod
    def refresh_token(self, refresh_token: str) -> OAuthCredentials:
        """Renova token de acesso."""
        pass

    @abstractmethod
    def validate_token(self, token: str) -> bool:
        """Valida se o token está válido."""
        pass


class APIKeyServiceInterface(ABC):
    """Interface para serviços com API Key."""

    @abstractmethod
    def validate_key(self, api_key: str) -> bool:
        """Valida se a API key está válida."""
        pass


# =============================================================================
# INTERFACES DE CLIENTE API
# =============================================================================


class APIClientInterface(ABC):
    """Interface base para clientes de API externos."""

    @abstractmethod
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Realiza requisição GET."""
        pass

    @abstractmethod
    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Realiza requisição POST."""
        pass

    @abstractmethod
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Realiza requisição PUT."""
        pass

    @abstractmethod
    def delete(self, endpoint: str) -> APIResponse:
        """Realiza requisição DELETE."""
        pass


class AuthenticatedAPIClientInterface(APIClientInterface):
    """Interface para clientes de API que suportam autenticação."""

    @abstractmethod
    def set_credentials(self, credentials: AuthCredentials) -> None:
        """Define credenciais de autenticação."""
        pass


# =============================================================================
# INTERFACES DE MARKETPLACE
# =============================================================================


class MarketplaceInterface(ABC):
    """Interface base para marketplaces."""


class AuthenticatedMarketplaceInterface(MarketplaceInterface):
    """Interface para marketplaces que requerem autenticação."""

    @abstractmethod
    def authenticate(self, **kwargs) -> bool:
        """Autentica no marketplace."""
        pass


# =============================================================================
# INTERFACES DE E-MAIL
# =============================================================================


class EmailSenderInterface(ABC):
    """Contrato para serviços capazes de enviar e-mails."""

    @abstractmethod
    def send_email(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        pass
