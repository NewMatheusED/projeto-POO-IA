"""
Views para análise legislativa.

Endpoints específicos para análise de projetos de lei.
"""

from flask import Blueprint, request
from marshmallow import Schema, ValidationError, fields

from app.services.ia.controller import AIController
from app.services.legislative.controller import LegislativeController
from app.services.votes.controller import VotesController
from app.utils.responses import error_response, success_response


# Cria blueprint
legislative_bp = Blueprint("legislative_analysis", __name__)

# Inicializa controllers
legislative_controller = LegislativeController()
votes_controller = VotesController()
ai_controller = AIController()


class ProjectAnalysisRequestSchema(Schema):
    """Schema para requisições de análise de projeto."""

    project_id = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)
    check_votes = fields.Bool(load_default=True)


class BatchAnalysisRequestSchema(Schema):
    """Schema para análise em lote."""

    project_ids = fields.List(fields.Str(), required=True, validate=lambda x: len(x) > 0)
    check_votes = fields.Bool(load_default=True)


class DirectSaveRequestSchema(Schema):
    """Schema para salvar dados diretos do playground."""

    project_id = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)
    analysis_data = fields.Dict(required=True)
    validate_data = fields.Bool(load_default=True)


@legislative_bp.route("/", methods=["GET"])
def health_check():
    """Endpoint para verificar saúde do serviço de análise legislativa."""
    return success_response(
        {"message": "Serviço de análise legislativa está funcionando", "status": "healthy", "features": ["análise_individual", "análise_lote", "verificação_votos"]}
    ).to_json_response()


@legislative_bp.route("/analyze", methods=["POST"])
def analyze_project():
    """
    Endpoint para análise individual de projeto de lei.

    Body esperado:
    {
        "project_id": "PLS 224/2017",
        "check_votes": true  // opcional, verifica se tem votos antes de analisar
    }
    """
    try:
        # Valida dados de entrada
        schema = ProjectAnalysisRequestSchema()
        data = schema.load(request.get_json() or {})

        # Executa análise
        result = legislative_controller.analyze_project(project_id=data["project_id"], check_votes=data.get("check_votes", True), ai_controller=ai_controller)

        if result.success:
            return success_response(result.to_dict()).to_json_response()
        else:
            return error_response("Erro na análise do projeto", 500, result.error).to_json_response()

    except ValidationError as e:
        return error_response("Dados inválidos", 400, e.messages).to_json_response()
    except Exception as e:
        return error_response("Erro interno do servidor", 500, str(e)).to_json_response()


@legislative_bp.route("/analyze/batch", methods=["POST"])
def analyze_batch():
    """
    Endpoint para análise em lote de projetos.

    Body esperado:
    {
        "project_ids": ["PLS 224/2017", "PEC 6/2019", "MPV 871/2019"],
        "check_votes": true  // opcional
    }
    """
    try:
        # Valida dados de entrada
        schema = BatchAnalysisRequestSchema()
        data = schema.load(request.get_json() or {})

        # Executa análise em lote
        result = legislative_controller.batch_analyze_projects(data["project_ids"], ai_controller)

        return success_response(result).to_json_response()

    except ValidationError as e:
        return error_response("Dados inválidos", 400, e.messages).to_json_response()
    except Exception as e:
        return error_response("Erro interno do servidor", 500, str(e)).to_json_response()


@legislative_bp.route("/check-votes/<project_id>", methods=["GET"])
def check_project_votes(project_id: str):
    """
    Endpoint para verificar se um projeto possui votos.

    Args:
        project_id: Código do projeto
    """
    try:
        status = votes_controller.get_project_status(project_id)
        return success_response(status).to_json_response()

    except Exception as e:
        return error_response("Erro ao verificar votos", 500, str(e)).to_json_response()


@legislative_bp.route("/prompts", methods=["GET"])
def get_prompts():
    """Endpoint para visualizar os prompts utilizados."""
    return success_response(
        {
            "system_prompt": legislative_controller.legislative_service.get_system_prompt(),
            "user_prompt_template": legislative_controller.legislative_service.get_user_prompt_template(),
            "description": "Prompts utilizados para análise de projetos de lei",
        }
    ).to_json_response()


@legislative_bp.route("/example-response", methods=["GET"])
def get_example_response():
    """Endpoint para visualizar exemplo de resposta esperada."""
    example = {
        "contexto_epoca": "Em 2017, o Brasil vivia um período de instabilidade política...",
        "resumo_objetivo": "O PLS 224/2017 propõe a criação de um marco regulatório...",
        "interpretacao_simplificada": "Na prática, essa lei significa que qualquer pessoa...",
        "avaliacao_parametrica": [
            {"criterio": "Impacto_Social", "resumo": "Regulamentação melhora segurança e privacidade...", "nota": 7, "justificativa": "Baseado na análise de redistribuição de recursos..."}
        ],
    }

    return success_response({"example": example, "description": "Exemplo de resposta JSON esperada da IA"}).to_json_response()


@legislative_bp.route("/save-direct", methods=["POST"])
def save_direct_analysis():
    """
    Endpoint para salvar dados de análise diretamente (do playground).

    Aceita dois formatos:
    
    1. Formato com wrapper (original):
    {
        "project_id": "PLS 224/2017",
        "analysis_data": {
            "contexto_epoca": "...",
            "resumo_objetivo": "...",
            "interpretacao_simplificada": "...",
            "avaliacao_parametrica": [...]
        },
        "validate_data": true
    }
    
    2. Formato direto da IA (novo):
    {
        "project_id": "PLS 224/2017",
        "contexto_epoca": "...",
        "resumo_objetivo": "...",
        "interpretacao_simplificada": "...",
        "avaliacao_parametrica": [...],
        "validate_data": true
    }
    """
    try:
        # Obtém dados da requisição
        request_data = request.get_json() or {}
        
        # Verifica se project_id está presente
        if "project_id" not in request_data:
            return error_response("project_id é obrigatório", 400).to_json_response()
        
        # Detecta formato automaticamente
        if "analysis_data" in request_data:
            # Formato com wrapper (original)
            analysis_data = request_data["analysis_data"]
            validate_data = request_data.get("validate_data", True)
        else:
            # Formato direto da IA
            analysis_data = {
                "contexto_epoca": request_data.get("contexto_epoca", ""),
                "resumo_objetivo": request_data.get("resumo_objetivo", ""),
                "interpretacao_simplificada": request_data.get("interpretacao_simplificada", ""),
                "avaliacao_parametrica": request_data.get("avaliacao_parametrica", [])
            }
            validate_data = request_data.get("validate_data", True)
        
        # Salva dados de análise (mesmo fluxo da IA)
        result = legislative_controller.save_analysis_data(
            project_id=request_data["project_id"],
            analysis_data=analysis_data,
            validate=validate_data,
            check_votes=True,  # SEMPRE verifica votos (mesmo fluxo da IA)
        )

        if result.success:
            return success_response(result.to_dict()).to_json_response()
        else:
            return error_response("Erro ao salvar análise", 500, result.error).to_json_response()

    except ValidationError as e:
        return error_response("Dados inválidos", 400, e.messages).to_json_response()
    except Exception as e:
        return error_response("Erro interno do servidor", 500, str(e)).to_json_response()
