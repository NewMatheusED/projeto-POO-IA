"""
Modelos de dados para o serviço de IA.

Define estruturas de dados para mensagens e respostas da IA.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.services.ia.interfaces import AIMessage


@dataclass
class SystemMessage(AIMessage):
    """Mensagem do sistema para definir comportamento da IA."""
    
    content: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte a mensagem para dicionário."""
        return {
            "role": "system",
            "content": self.content
        }


@dataclass
class UserMessage(AIMessage):
    """Mensagem do usuário para a IA."""
    
    content: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte a mensagem para dicionário."""
        return {
            "role": "user",
            "content": self.content
        }


@dataclass
class AssistantMessage(AIMessage):
    """Mensagem da IA (para histórico de conversas)."""
    
    content: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte a mensagem para dicionário."""
        return {
            "role": "assistant",
            "content": self.content
        }


@dataclass
class AIResponse:
    """Resposta da IA."""
    
    content: str
    model: str
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte a resposta para dicionário."""
        return {
            "content": self.content,
            "model": self.model,
            "usage": self.usage,
            "finish_reason": self.finish_reason
        }


@dataclass
class AIRequest:
    """Requisição para a IA."""
    
    messages: list[AIMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    response_format: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte a requisição para dicionário."""
        data = {
            "messages": [msg.to_dict() for msg in self.messages]
        }
        
        if self.temperature is not None:
            data["temperature"] = self.temperature
            
        if self.top_p is not None:
            data["top_p"] = self.top_p
            
        if self.max_tokens is not None:
            data["max_tokens"] = self.max_tokens
            
        if self.response_format is not None:
            data["response_format"] = {"type": self.response_format}
            
        return data
