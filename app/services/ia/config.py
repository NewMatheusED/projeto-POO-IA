"""
Configuração específica para o serviço de IA.

Define configurações para comunicação com o GitHub AI Inference.
"""

from dataclasses import dataclass
from typing import Optional

from app.flask_config import Config
from app.external.base.config import BaseConfig


@dataclass
class AIConfig(BaseConfig):
    """Configuração para o serviço de IA."""
    
    model: str = "xai/grok-3-mini"
    token: str = ""
    endpoint: str = "https://models.github.ai/inference"
    temperature: float = 1.0
    top_p: float = 1.0
    max_tokens: Optional[int] = None
    response_format: str = "text"
    
    def __post_init__(self):
        """Valida configurações após inicialização."""
        self._validate_ai_config()
        super().__post_init__()
    
    def _validate_ai_config(self) -> None:
        """Valida configurações específicas de IA."""
        if not self.model:
            raise ValueError("model é obrigatório")
        
        if not self.token:
            raise ValueError("token é obrigatório")
        
        if not self.endpoint:
            raise ValueError("endpoint é obrigatório")
        
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("temperature deve estar entre 0.0 e 2.0")
        
        if not (0.0 <= self.top_p <= 1.0):
            raise ValueError("top_p deve estar entre 0.0 e 1.0")
        
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens deve ser maior que zero")
        
        if self.response_format not in ["text", "json_object"]:
            raise ValueError("response_format deve ser 'text' ou 'json_object'")


class AIConfigFactory:
    """Factory para criar configurações de IA."""
    
    @staticmethod
    def create_from_env() -> AIConfig:
        """Cria configuração de IA a partir de variáveis de ambiente."""
        return AIConfig(
            base_url="https://models.github.ai/inference",
            model="xai/grok-3-mini",
            token=Config.GITHUB_TOKEN,
            endpoint="https://models.github.ai/inference",
            temperature=1.0,
            top_p=1.0,
            max_tokens=None,
            response_format="text",
            timeout=30,
            max_retries=3,
            retry_delay=1.0
        )
