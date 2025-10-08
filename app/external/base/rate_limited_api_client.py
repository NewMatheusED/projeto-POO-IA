"""
Cliente API com controle de rate limit.

Extende AuthenticatedAPIClient para adicionar controle de taxa de requisições.
"""

import logging
import time
from typing import Any, Dict, Optional

import requests

from .authenticated_api_client import AuthenticatedAPIClient
from .config import BaseConfig
from .interfaces import APIResponse
from .rate_limiter import RateLimitConfig, RateLimiter, RateLimitExceededError


class RateLimitedAPIClient(AuthenticatedAPIClient):
    """Cliente API com controle de rate limit."""

    def __init__(self, config: BaseConfig, token_id: str, rate_limit_config: Optional[RateLimitConfig] = None):
        """
        Inicializa o cliente com rate limiting.

        Args:
            config: Configuração base do cliente API
            token_id: Identificador único para este cliente (geralmente marketplace_shop_id)
            rate_limit_config: Configuração de rate limiting (opcional)
        """
        super().__init__(config)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.token_id = token_id

        # Obtém a instância singleton do rate limiter
        self.rate_limiter = RateLimiter.get_instance()

        # Configura o rate limiter para este token se uma configuração foi fornecida
        if rate_limit_config:
            self.rate_limiter.configure(token_id, rate_limit_config)

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> APIResponse:
        """
        Executa requisição HTTP com controle de rate limit.

        Sobrescreve o método da classe base para adicionar verificação de rate limit
        antes de fazer a requisição e para registrar a requisição após a chamada.
        """
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        try:
            # Verifica se pode fazer a requisição e aguarda se necessário
            # Passa o método HTTP para aplicar o limite específico
            self.rate_limiter.check_and_wait(self.token_id, method)

            self.logger.info(f"Fazendo requisição {method.upper()} para {url}")

            # Faz a requisição
            response = self.session.request(method=method, url=url, params=params, json=data, timeout=self.config.timeout, headers=headers)

            # Registra a requisição no rate limiter com o método específico
            self.rate_limiter.register_request(self.token_id, method)

            # Verifica se a resposta indica limite de requisições excedido
            if response.status_code == 429:
                # Extrai o tempo de espera sugerido do header, se disponível
                retry_after = self._extract_retry_after(response)

                # Registra o hit de limite no rate limiter para o método específico
                self.rate_limiter.register_limit_hit(self.token_id, method, retry_after)

                # Aguarda o tempo sugerido e tenta novamente
                wait_time = retry_after or 60  # Padrão de 60 segundos se não especificado
                self.logger.warning(f"Rate limit excedido para método {method}. Aguardando {wait_time} segundos antes de tentar novamente.")
                time.sleep(wait_time)

                # Tenta a requisição novamente após a espera
                return self._make_request(method, endpoint, params, data, headers)

            return self._process_response(response)

        except RateLimitExceededError as e:
            # Se o rate limiter está configurado para não bloquear
            self.logger.error(f"Limite de requisições excedido para {url}, método {e.method.value}: {str(e)}")
            return APIResponse(
                status_code=429,
                data={"error": "rate_limit_exceeded", "message": str(e), "retry_after": e.retry_after},
                headers={},
                success=False,
                error_message=f"Rate limit excedido para método {e.method.value}. Tente novamente em {e.retry_after} segundos.",
            )

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro na requisição para {url}: {str(e)}")
            return APIResponse(status_code=0, data={}, headers={}, success=False, error_message=str(e))

    def _extract_retry_after(self, response: requests.Response) -> Optional[int]:
        """
        Extrai o tempo de espera sugerido dos headers da resposta.

        Args:
            response: Resposta da requisição

        Returns:
            Tempo de espera em segundos ou None se não especificado
        """
        # Tenta obter do header padrão Retry-After
        retry_after = response.headers.get("Retry-After")

        # Tenta obter de headers específicos do Mercado Livre
        if not retry_after:
            retry_after = response.headers.get("X-RateLimit-Reset")

        if not retry_after:
            # Tenta obter da resposta JSON
            try:
                data = response.json()
                retry_after = data.get("retry_after") or data.get("wait") or data.get("reset")
            except Exception as e:
                self.logger.error(f"Erro ao extrair tempo de espera da resposta: {response.text} - {str(e)}")
                pass

        # Converte para inteiro se for string
        if retry_after and isinstance(retry_after, str) and retry_after.isdigit():
            return int(retry_after)
        elif retry_after and isinstance(retry_after, (int, float)):
            return int(retry_after)

        return None
