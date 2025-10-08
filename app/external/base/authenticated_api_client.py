"""
Cliente API autenticado.

Extende BaseAPIClient para adicionar funcionalidades de autenticação.
"""

import logging
from typing import Optional

from .api_client import BaseAPIClient
from .config import BaseConfig
from .interfaces import APIKeyCredentials, AuthCredentials, AuthenticatedAPIClientInterface, BasicAuthCredentials, OAuthCredentials


class AuthenticatedAPIClient(BaseAPIClient, AuthenticatedAPIClientInterface):
    """Cliente API com suporte a autenticação."""

    def __init__(self, config: BaseConfig):
        """Inicializa o cliente autenticado."""
        super().__init__(config)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._current_credentials: Optional[AuthCredentials] = None

    def set_credentials(self, credentials: AuthCredentials) -> None:
        """Define credenciais de autenticação."""
        self._current_credentials = credentials
        self._apply_credentials(credentials)

    def _apply_credentials(self, credentials: AuthCredentials) -> None:
        """Aplica as credenciais na sessão HTTP."""
        if isinstance(credentials, OAuthCredentials):
            self._apply_oauth_credentials(credentials)
        elif isinstance(credentials, APIKeyCredentials):
            self._apply_api_key_credentials(credentials)
        elif isinstance(credentials, BasicAuthCredentials):
            self._apply_basic_auth_credentials(credentials)
        else:
            self.logger.warning(f"Tipo de credencial não suportado: {type(credentials)}")

    def _apply_oauth_credentials(self, credentials: OAuthCredentials) -> None:
        """Aplica credenciais OAuth."""
        auth_header = f"{credentials.token_type} {credentials.access_token}"
        self.session.headers.update({"Authorization": auth_header})
        self.logger.info("Credenciais OAuth aplicadas")

    def _apply_api_key_credentials(self, credentials: APIKeyCredentials) -> None:
        """Aplica credenciais de API Key."""
        self.session.headers.update({credentials.header_name: credentials.api_key})
        self.logger.info(f"API Key aplicada no header {credentials.header_name}")

    def _apply_basic_auth_credentials(self, credentials: BasicAuthCredentials) -> None:
        """Aplica credenciais Basic Auth."""
        import base64

        auth_string = f"{credentials.username}:{credentials.password}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        self.session.headers.update({"Authorization": f"Basic {encoded_auth}"})
        self.logger.info("Credenciais Basic Auth aplicadas")

    def get_credentials(self) -> Optional[AuthCredentials]:
        """Retorna as credenciais atuais."""
        return self._current_credentials

    def clear_credentials(self) -> None:
        """Remove credenciais da sessão."""
        self._current_credentials = None

        # Remove headers de autenticação comuns
        auth_headers = ["Authorization", "X-API-Key", "X-Auth-Token"]
        for header in auth_headers:
            if header in self.session.headers:
                del self.session.headers[header]

        self.logger.info("Credenciais removidas")
