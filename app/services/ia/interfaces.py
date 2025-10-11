"""
Interfaces para o serviço de IA.

Define contratos que devem ser implementados pelos clientes de IA.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AIMessage(ABC):
    """Interface base para mensagens de IA."""

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Converte a mensagem para dicionário."""
        pass


class AIClient(ABC):
    """Interface para clientes de IA."""

    @abstractmethod
    def complete(
        self, messages: List[AIMessage], temperature: Optional[float] = None, top_p: Optional[float] = None, max_tokens: Optional[int] = None, response_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envia mensagens para a IA e retorna a resposta.

        Args:
            messages: Lista de mensagens para enviar
            temperature: Temperatura para controlar aleatoriedade
            top_p: Parâmetro top_p para controlar diversidade
            max_tokens: Número máximo de tokens na resposta
            response_format: Formato da resposta ('text' ou 'json_object')

        Returns:
            Resposta da IA em formato de dicionário

        Raises:
            AIServiceError: Em caso de erro na comunicação com a IA
        """
        pass


class AIServiceError(Exception):
    """Exceção base para erros do serviço de IA."""

    pass


class AIConnectionError(AIServiceError):
    """Erro de conexão com o serviço de IA."""

    pass


class AIAuthenticationError(AIServiceError):
    """Erro de autenticação com o serviço de IA."""

    pass


class AIValidationError(AIServiceError):
    """Erro de validação de parâmetros."""

    pass
