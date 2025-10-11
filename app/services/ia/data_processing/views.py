"""
Views para processamento de dados.

Define endpoints para processamento de dados da IA e APIs diretas.
"""

from flask import Blueprint, request
from marshmallow import ValidationError

from app.services.ia.data_processing.controller import ProcessingService
from app.services.ia.data_processing.schemas import BatchProcessingResponseSchema, ProcessingRequestSchema
from app.utils.responses import error_response, success_response

# Cria blueprint
processing_bp = Blueprint("data_processing", __name__)

# Inicializa serviço
processing_service = ProcessingService()


@processing_bp.route("/", methods=["GET"])
def health_check():
    """Endpoint para verificar saúde do serviço de processamento."""
    return success_response({"message": "Serviço de processamento de dados está funcionando", "status": "healthy", "available_pipelines": ["default", "ai", "direct"]})


@processing_bp.route("/process", methods=["POST"])
def process_data():
    """
    Endpoint principal para processamento de dados.

    Detecta automaticamente se os dados vêm da IA ou são diretos.

    Body esperado:
    {
        "content": "Dados para processar",
        "variable": "valor da variável",  // opcional
        "confidence": 0.95,  // opcional
        "sentiment": "positive",  // opcional
        "source": "auto",  // opcional: "ai", "direct", "auto"
        "enable_enrichment": true,  // opcional
        "enable_persistence": true  // opcional
    }
    """
    try:
        # Valida dados de entrada
        schema = ProcessingRequestSchema()
        data = schema.load(request.get_json() or {})

        # Determina pipeline baseado na fonte
        source = data.get("source", "auto")

        if source == "ai":
            result = processing_service.process_with_ai_pipeline(data)
        elif source == "direct":
            result = processing_service.process_with_direct_pipeline(data)
        else:
            result = processing_service.process_auto_detect(data)

        if result["success"]:
            return success_response(result)
        else:
            return error_response("Erro no processamento", 500, result["error"])

    except ValidationError as e:
        return error_response("Dados inválidos", 400, e.messages)
    except Exception as e:
        return error_response("Erro interno do servidor", 500, str(e))


@processing_bp.route("/process/ai", methods=["POST"])
def process_ai_data():
    """
    Endpoint específico para dados da IA.

    Body esperado:
    {
        "content": "Resposta da IA",
        "model": "xai/grok-3-mini",
        "usage": {...},  // opcional
        "variable": "valor extraído"  // opcional
    }
    """
    try:
        # Valida dados de entrada
        schema = ProcessingRequestSchema()
        data = schema.load(request.get_json() or {})

        # Força uso do pipeline da IA
        result = processing_service.process_with_ai_pipeline(data)

        if result["success"]:
            return success_response(result)
        else:
            return error_response("Erro no processamento da IA", 500, result["error"])

    except ValidationError as e:
        return error_response("Dados inválidos", 400, e.messages)
    except Exception as e:
        return error_response("Erro interno do servidor", 500, str(e))


@processing_bp.route("/process/direct", methods=["POST"])
def process_direct_data():
    """
    Endpoint para dados enviados diretamente.

    Body esperado:
    {
        "content": "Dados para processar",
        "variable": "valor da variável",
        "confidence": 0.95,  // opcional
        "sentiment": "positive",  // opcional
        "category": "categoria",  // opcional
        "priority": 3  // opcional
    }
    """
    try:
        # Valida dados de entrada
        schema = ProcessingRequestSchema()
        data = schema.load(request.get_json() or {})

        # Força uso do pipeline direto
        result = processing_service.process_with_direct_pipeline(data)

        if result["success"]:
            return success_response(result)
        else:
            return error_response("Erro no processamento direto", 500, result["error"])

    except ValidationError as e:
        return error_response("Dados inválidos", 400, e.messages)
    except Exception as e:
        return error_response("Erro interno do servidor", 500, str(e))


@processing_bp.route("/process/batch", methods=["POST"])
def process_batch():
    """
    Endpoint para processamento em lote.

    Body esperado:
    {
        "items": [
            {
                "content": "Item 1",
                "variable": "valor1"
            },
            {
                "content": "Item 2",
                "variable": "valor2"
            }
        ]
    }
    """
    try:
        # Valida dados de entrada
        schema = BatchProcessingResponseSchema()
        data = schema.load(request.get_json() or {})

        # Processa lote
        controller = processing_service.get_controller("default")
        result = controller.process_batch(data["items"])

        return success_response(result)

    except ValidationError as e:
        return error_response("Dados inválidos", 400, e.messages)
    except Exception as e:
        return error_response("Erro interno do servidor", 500, str(e))


@processing_bp.route("/stats", methods=["GET"])
def get_stats():
    """Endpoint para obter estatísticas do processamento."""
    try:
        controller = processing_service.get_controller("default")
        stats = controller.get_processing_stats()

        return success_response(stats)

    except Exception as e:
        return error_response("Erro ao obter estatísticas", 500, str(e))


# Integração com o endpoint de IA existente
@processing_bp.route("/ai/complete", methods=["POST"])
def ai_complete_with_processing():
    """
    Endpoint que integra IA + processamento.

    Combina o chat completion da IA com o processamento automático.

    Body esperado:
    {
        "user_message": "Mensagem para a IA",
        "system_message": "Instruções do sistema",  // opcional
        "variables": {  // opcional
            "nome": "João"
        },
        "response_format": "text",  // opcional
        "process_result": true  // opcional, processa resultado automaticamente
    }
    """
    try:
        from app.services.ia.controller import AIController

        # Valida dados básicos
        request_data = request.get_json() or {}
        user_message = request_data.get("user_message")

        if not user_message:
            return error_response("user_message é obrigatório", 400)

        # Executa chat completion da IA
        ai_controller = AIController()
        ai_response = ai_controller.chat_completion(
            user_message=user_message,
            system_message=request_data.get("system_message", "Você é um assistente útil."),
            variables=request_data.get("variables"),
            response_format=request_data.get("response_format", "text"),
        )

        # Se solicitado, processa o resultado
        if request_data.get("process_result", True):
            processing_result = processing_service.process_auto_detect(ai_response)

            return success_response({"ai_response": ai_response, "processing_result": processing_result})
        else:
            return success_response({"ai_response": ai_response})

    except Exception as e:
        return error_response("Erro na integração IA + processamento", 500, str(e))
