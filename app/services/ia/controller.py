"""
Controller para o serviço de IA.

Implementa a lógica de negócio para comunicação com IA.
"""

from typing import Any, Dict, List, Optional

from app.services.ia.azure_client import AzureAIClient
from app.services.ia.config import AIConfigFactory
from app.services.ia.interfaces import AIClient, AIServiceError
from app.services.ia.models import SystemMessage, UserMessage


class AIController:
    """Controller para operações de IA."""

    def __init__(self, client: Optional[AIClient] = None):
        """
        Inicializa o controller de IA.

        Args:
            client: Cliente de IA (opcional, usa AzureAIClient por padrão)
        """
        self._client = client or self._create_default_client()

    def _create_default_client(self) -> AIClient:
        """Cria cliente padrão usando configuração de ambiente."""
        try:
            config = AIConfigFactory.create_from_env()
            return AzureAIClient(config)
        except Exception as e:
            raise AIServiceError(f"Erro ao criar cliente de IA: {str(e)}")

    def chat_completion(
        self,
        user_message: str,
        system_message: str = "Você é um assistente útil.",
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: str = "text",
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executa chat completion com a IA.

        Args:
            user_message: Mensagem do usuário
            system_message: Mensagem do sistema
            temperature: Temperatura para controle de aleatoriedade
            top_p: Parâmetro top_p para controle de diversidade
            max_tokens: Número máximo de tokens na resposta
            response_format: Formato da resposta ('text' ou 'json_object')
            variables: Variáveis para substituição na mensagem do usuário

        Returns:
            Resposta da IA

        Raises:
            AIServiceError: Em caso de erro
        """
        try:
            # Substitui variáveis na mensagem do usuário
            processed_user_message = self._process_message_with_variables(user_message, variables)

            # Cria mensagens
            messages = [SystemMessage(system_message), UserMessage(processed_user_message)]

            # Executa requisição para a IA
            response = self._client.complete(messages=messages, temperature=temperature, top_p=top_p, max_tokens=max_tokens, response_format=response_format)

            return response

        except Exception as e:
            raise AIServiceError(f"Erro no chat completion: {str(e)}")

    def complete_with_messages(
        self, messages: List[Dict[str, str]], temperature: Optional[float] = None, top_p: Optional[float] = None, max_tokens: Optional[int] = None, response_format: str = "text"
    ) -> Dict[str, Any]:
        """
        Executa completion com lista de mensagens.

        Args:
            messages: Lista de mensagens no formato [{"role": "user", "content": "..."}]
            temperature: Temperatura para controle de aleatoriedade
            top_p: Parâmetro top_p para controle de diversidade
            max_tokens: Número máximo de tokens na resposta
            response_format: Formato da resposta ('text' ou 'json_object')

        Returns:
            Resposta da IA

        Raises:
            AIServiceError: Em caso de erro
        """
        try:
            # Converte mensagens para objetos
            ai_messages = []
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content")

                if role == "system":
                    ai_messages.append(SystemMessage(content))
                elif role == "user":
                    ai_messages.append(UserMessage(content))
                else:
                    raise ValueError(f"Role inválido: {role}")

            # Executa requisição para a IA
            response = self._client.complete(messages=ai_messages, temperature=temperature, top_p=top_p, max_tokens=max_tokens, response_format=response_format)

            return response

        except Exception as e:
            raise AIServiceError(f"Erro no completion com mensagens: {str(e)}")

    def _process_message_with_variables(self, message: str, variables: Optional[Dict[str, Any]]) -> str:
        """
        Substitui variáveis na mensagem.

        Args:
            message: Mensagem original
            variables: Dicionário de variáveis para substituição

        Returns:
            Mensagem com variáveis substituídas
        """
        if not variables:
            return message

        processed_message = message
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            processed_message = processed_message.replace(placeholder, str(value))

        return processed_message
