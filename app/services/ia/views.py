"""
Views para o serviço de IA.

Define endpoints REST para comunicação com IA.
"""

from flask import Blueprint, request
from marshmallow import ValidationError

from app.services.ia.controller import AIController
from app.services.ia.interfaces import AIAuthenticationError, AIConnectionError, AIServiceError
from app.services.ia.schema import AIRequestSchema, ChatCompletionSchema
from app.utils.responses import error_response, success_response

ia_bp = Blueprint("ia", __name__)


ai_controller = AIController()


@ia_bp.route("/", methods=["GET"])
def health_check():
    """Endpoint para verificar saúde do serviço de IA."""
    return success_response({"message": "Serviço de IA está funcionando", "status": "healthy"})


@ia_bp.route("/chat", methods=["POST"])
def chat_completion():
    """
    Endpoint para chat completion com IA.

    Body esperado:
    {
        "user_message": "Sua mensagem aqui",
        "system_message": "Você é um assistente útil.",  // opcional
        "temperature": 1.0,  // opcional
        "top_p": 1.0,  // opcional
        "max_tokens": 1000,  // opcional
        "response_format": "text",  // opcional: "text" ou "json_object"
        "variables": {  // opcional
            "nome": "João",
            "idade": 30
        }
    }
    """
    try:
        # Valida dados de entrada
        schema = ChatCompletionSchema()
        data = schema.load_with_variables(request.get_json() or {})

        # Executa chat completion
        response = ai_controller.chat_completion(
            user_message=data["user_message"],
            system_message=data.get("system_message", "Você é um assistente útil."),
            temperature=data.get("temperature"),
            top_p=data.get("top_p"),
            max_tokens=data.get("max_tokens"),
            response_format=data.get("response_format", "text"),
            variables=data.get("variables"),
        )

        return success_response(response)

    except ValidationError as e:
        return error_response("Dados inválidos", 400, e.messages)
    except AIServiceError as e:
        return error_response("Erro no serviço de IA", 500, str(e))
    except Exception as e:
        return error_response("Erro interno do servidor", 500, str(e))


@ia_bp.route("/complete", methods=["POST"])
def complete():
    """
    Endpoint para completion com lista de mensagens.

    Body esperado:
    {
        "messages": [
            {"role": "system", "content": "Você é um assistente útil."},
            {"role": "user", "content": "Sua mensagem aqui"}
        ],
        "temperature": 1.0,  // opcional
        "top_p": 1.0,  // opcional
        "max_tokens": 1000,  // opcional
        "response_format": "text"  // opcional: "text" ou "json_object"
    }
    """
    try:
        # Valida dados de entrada
        schema = AIRequestSchema()
        data = schema.load(request.get_json() or {})

        # Executa completion
        response = ai_controller.complete_with_messages(
            messages=data["messages"], temperature=data.get("temperature"), top_p=data.get("top_p"), max_tokens=data.get("max_tokens"), response_format=data.get("response_format", "text")
        )

        return success_response(response)

    except ValidationError as e:
        return error_response("Dados inválidos", 400, e.messages)
    except AIServiceError as e:
        return error_response("Erro no serviço de IA", 500, str(e))
    except Exception as e:
        return error_response("Erro interno do servidor", 500, str(e))


@ia_bp.route("/models", methods=["GET"])
def list_models():
    """Endpoint para listar modelos disponíveis."""
    # Por enquanto retorna o modelo configurado
    # Futuramente pode ser expandido para listar todos os modelos disponíveis
    return success_response({"models": ["xai/grok-3-mini"], "current_model": "xai/grok-3-mini"})


@ia_bp.errorhandler(AIConnectionError)
def handle_connection_error(e):
    """Handler para erros de conexão com IA."""
    return error_response("Erro de conexão com o serviço de IA", 503, str(e))


@ia_bp.errorhandler(AIAuthenticationError)
def handle_auth_error(e):
    """Handler para erros de autenticação com IA."""
    return error_response("Erro de autenticação com o serviço de IA", 401, str(e))
