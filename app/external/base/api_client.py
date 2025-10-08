"""
Cliente base para APIs externas.

Implementa funcionalidades comuns para todos os clientes de API externos,
incluindo retry, logging e tratamento de erros.
"""

import logging
import unicodedata
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import BaseConfig
from .interfaces import APIClientInterface, APIResponse


class BaseAPIClient(APIClientInterface):
    """Cliente base para APIs externas com funcionalidades comuns."""

    def __init__(self, config: BaseConfig):
        """Inicializa o cliente com configurações."""
        self.config = config
        self.session = self._create_session()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _create_session(self) -> requests.Session:
        """Cria sessão HTTP com configurações de retry."""
        session = requests.Session()

        # Configuração de retry
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Headers padrão
        session.headers.update(self.config.get_headers())

        return session

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Executa requisição HTTP com tratamento de erros."""
        # Helpers locais para sanitização global
        invisible_chars = {"\u2060", "\u200b", "\u200c", "\u200d", "\ufeff"}

        def _clean_string(value: Any) -> Any:
            if not isinstance(value, str):
                return value
            # Normaliza para NFKC e remove invisíveis conhecidos
            s = unicodedata.normalize("NFKC", value)
            for ch in invisible_chars:
                s = s.replace(ch, "")
            # Remove não imprimíveis genéricos
            s = "".join(ch for ch in s if ch.isprintable())
            return s.strip()

        def _clean_mapping(mapping: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            if not isinstance(mapping, dict):
                return mapping
            cleaned: Dict[str, Any] = {}
            for k, v in mapping.items():
                ck = _clean_string(k)
                key = ck if ck != "" else str(k)
                if isinstance(v, dict):
                    cleaned[key] = _clean_mapping(v)
                elif isinstance(v, list):
                    cleaned[key] = [_clean_string(i) if isinstance(i, str) else i for i in v]
                else:
                    cleaned[key] = _clean_string(v)
            return cleaned

        # Sanitiza endpoint e parâmetros
        try:
            cleaned_endpoint = _clean_string(endpoint)
        except Exception:
            cleaned_endpoint = endpoint

        url = f"{self.config.base_url.rstrip('/')}/{cleaned_endpoint.lstrip('/')}"

        try:
            self.logger.info(f"Fazendo requisição {method.upper()} para {url} | params={params if params else {}}")

            # Normaliza params, data e headers
            norm_params = _clean_mapping(params) if params else None
            norm_data = _clean_mapping(data) if data else None
            norm_headers = _clean_mapping(headers) if headers else None

            response = self.session.request(method=method, url=url, params=norm_params, json=norm_data, timeout=self.config.timeout, headers=norm_headers)

            # Loga a URL final (com query string resolvida pela requests)
            try:
                self.logger.info(f"URL efetiva: {response.request.url}")
            except Exception:
                pass

            return self._process_response(response)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro na requisição para {url}: {str(e)}")
            return APIResponse(status_code=0, data={}, headers={}, success=False, error_message=str(e))

    def _process_response(self, response: requests.Response) -> APIResponse:
        """Processa resposta HTTP e retorna objeto padronizado."""
        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {"raw_content": response.text}

        success = 200 <= response.status_code < 300

        return APIResponse(status_code=response.status_code, data=data, headers=dict(response.headers), success=success, error_message=None if success else f"HTTP {response.status_code}")

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Realiza requisição GET."""
        return self._make_request("GET", endpoint, params=params, headers=headers)

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Realiza requisição POST."""
        return self._make_request("POST", endpoint, data=data, headers=headers)

    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Realiza requisição PUT."""
        return self._make_request("PUT", endpoint, data=data, headers=headers)

    def delete(self, endpoint: str, headers: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Realiza requisição DELETE."""
        return self._make_request("DELETE", endpoint, headers=headers)

    def close(self) -> None:
        """Fecha a sessão HTTP."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
