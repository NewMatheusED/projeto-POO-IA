"""
Configurações de CORS para segurança.

Esta implementação define configurações seguras de CORS
para diferentes ambientes e domínios.
"""

from typing import Any, Dict, List

from app.flask_config import Config


class CORSConfig:
    """
    Configurações de CORS seguindo princípios SOLID.
    Responsabilidade única: gerenciar configurações de CORS.
    """

    # Domínios permitidos por ambiente
    PRODUCTION_ORIGINS = ["https://senate-tracker.com.br", "https://www.senate-tracker.com.br", "https://api.senate-tracker.com.br", "https://ia.senate-tracker.com.br"]

    DEVELOPMENT_ORIGINS = [
        "http://localhost:5173",
    ]

    # Headers permitidos
    ALLOWED_HEADERS = ["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"]

    # Métodos HTTP permitidos
    ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

    @classmethod
    def get_origins(cls) -> List[str]:
        """
        Retorna as origens permitidas baseadas no ambiente.

        Returns:
            List[str]: Lista de origens permitidas
        """
        is_production = Config.PRODUCTION == "true"

        if is_production:
            return cls.PRODUCTION_ORIGINS
        else:
            return cls.DEVELOPMENT_ORIGINS

    @classmethod
    def get_cors_config(cls) -> Dict[str, Any]:
        """
        Retorna a configuração completa de CORS.

        Returns:
            Dict[str, Any]: Configuração de CORS
        """
        return {"origins": cls.get_origins(), "supports_credentials": True, "allow_headers": cls.ALLOWED_HEADERS, "methods": cls.ALLOWED_METHODS, "max_age": 3600}  # Cache preflight por 1 hora

    @classmethod
    def get_api_cors_config(cls) -> Dict[str, Any]:
        """
        Retorna configuração específica para API.

        Returns:
            Dict[str, Any]: Configuração de CORS para API
        """
        return {
            r"/v1/*": cls.get_cors_config(),
            r"/auth/*": cls.get_cors_config(),
            r"/webhook/*": {"origins": cls.get_origins(), "supports_credentials": False, "methods": ["POST"]},  # Webhooks não precisam de credenciais
        }
