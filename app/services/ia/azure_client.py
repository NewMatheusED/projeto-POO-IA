"""
Cliente Azure AI para comunicação com o GitHub AI Inference.

Implementa o cliente específico para o Azure AI Inference.
"""

from typing import Any, Dict, List, Optional

from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential

from app.services.ia.config import AIConfig
from app.services.ia.interfaces import AIAuthenticationError, AIClient, AIConnectionError, AIMessage, AIServiceError


class AzureAIClient(AIClient):
    """Cliente Azure AI para comunicação com o GitHub AI Inference."""

    def __init__(self, config: AIConfig):
        """
        Inicializa o cliente Azure AI.

        Args:
            config: Configuração do cliente de IA
        """
        self._config = config
        self._client = self._create_client()

    def _create_client(self) -> ChatCompletionsClient:
        """Cria o cliente Azure AI."""
        try:
            print(self._config.token)
            print(self._config.endpoint)
            return ChatCompletionsClient(endpoint=self._config.endpoint, credential=AzureKeyCredential(self._config.token))
        except Exception as e:
            raise AIConnectionError(f"Erro ao criar cliente Azure AI: {str(e)}")

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
        try:
            # Converte mensagens para formato Azure
            azure_messages = self._convert_messages_to_azure_format(messages)

            # Usa valores padrão da configuração se não especificados
            temperature = temperature or self._config.temperature
            top_p = top_p or self._config.top_p
            max_tokens = max_tokens or self._config.max_tokens
            response_format = response_format or self._config.response_format

            # Prepara parâmetros da requisição
            request_params = {"messages": azure_messages, "temperature": temperature, "top_p": top_p, "model": self._config.model}

            if max_tokens:
                request_params["max_tokens"] = max_tokens

            if response_format == "json_object":
                request_params["response_format"] = "json_object"

            # Envia requisição para a IA
            response = self._client.complete(**request_params)

            # Converte resposta para formato padronizado
            return self._convert_response_to_dict(response)

        except Exception as e:
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                raise AIAuthenticationError(f"Erro de autenticação: {str(e)}")
            elif "connection" in str(e).lower() or "timeout" in str(e).lower():
                raise AIConnectionError(f"Erro de conexão: {str(e)}")
            else:
                raise AIServiceError(f"Erro no serviço de IA: {str(e)}")

    def _convert_messages_to_azure_format(self, messages: List[AIMessage]) -> List[Dict[str, str]]:
        """Converte mensagens para formato do Azure AI."""
        azure_messages = []

        for message in messages:
            azure_message = message.to_dict()
            azure_messages.append(azure_message)

        return azure_messages

    def _convert_response_to_dict(self, response) -> Dict[str, Any]:
        """Converte resposta do Azure AI para dicionário."""
        try:
            content = response.choices[0].message.content
            model = response.model

            # Extrai informações de uso se disponíveis
            usage = None
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                }

            # Extrai finish_reason se disponível
            finish_reason = None
            if hasattr(response.choices[0], "finish_reason"):
                finish_reason = response.choices[0].finish_reason

            return {"content": content, "model": model, "usage": usage, "finish_reason": finish_reason}

        except (AttributeError, IndexError) as e:
            raise AIServiceError(f"Erro ao processar resposta da IA: {str(e)}")
