"""
Configurações base para serviços externos.

Define configurações comuns e validações para todos os serviços externos.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class BaseConfig:
    """Configuração base para serviços externos."""

    base_url: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    headers: Optional[Dict[str, str]] = None

    def __post_init__(self):
        """Valida configurações após inicialização."""
        self._validate_config()

    def _validate_config(self) -> None:
        """Valida se as configurações estão corretas."""
        if not self.base_url:
            raise ValueError("base_url é obrigatório")

        if self.timeout <= 0:
            raise ValueError("timeout deve ser maior que zero")

        if self.max_retries < 0:
            raise ValueError("max_retries não pode ser negativo")

        if self.retry_delay < 0:
            raise ValueError("retry_delay não pode ser negativo")

    def get_headers(self) -> Dict[str, str]:
        """Retorna headers padrão."""
        default_headers = {"Content-Type": "application/json", "User-Agent": "Senate-Tracker-API/1.0"}

        if self.headers:
            default_headers.update(self.headers)

        return default_headers


class MarketplaceConfig(BaseConfig):
    """Configuração específica para marketplaces."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        redirect_uri: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Inicializa configuração de marketplace."""
        super().__init__(base_url, timeout, max_retries, retry_delay, headers)

        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

        self._validate_marketplace_config()

    def _validate_marketplace_config(self) -> None:
        """Valida configurações específicas de marketplace."""
        if not self.client_id:
            raise ValueError("client_id é obrigatório")

        if not self.client_secret:
            raise ValueError("client_secret é obrigatório")
