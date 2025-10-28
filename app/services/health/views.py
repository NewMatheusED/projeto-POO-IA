import logging
from datetime import datetime

from marshmallow import ValidationError

from flask import Blueprint, jsonify, request

from app.tasks.legislative_tasks import analyze_project
from app.tasks.celery_config import celery_app


logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__)

@health_bp.route("", methods=["GET"])
def health_check():
    """
    Endpoint simples de healthcheck.
    Retorna status da aplicação e data/hora atual do servidor.
    """
    logger.info("Healthcheck solicitado")
    return (
        jsonify(
            {
                "status": "up",
                "datetime": datetime.now().isoformat(),
            }
        ),
        200,
    )


@health_bp.route("/auto-analyze", methods=["POST"])
def start_auto_analysis():
    """
    Endpoint para iniciar análise automática de projetos (manual).
    
    Body esperado:
    {
        "limit": 3  // opcional: quantos projetos analisar (1-500, padrão: 5)
    }
    """
    try:
        data = request.get_json() or {}
        limit = data.get("limit", 5)
        
        # Valida limite
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            return jsonify({
                "success": False,
                "error": "Limit deve ser um número entre 1 e 500"
            }), 400
        
        # Inicia task de análise automática
        task = analyze_project.delay(limit=limit)
        
        return jsonify({
            "success": True,
            "task_id": task.id,
            "message": f"Análise automática iniciada - Limit: {limit} projetos",
            "status_url": f"/v1/health/status/{task.id}",
            "limit": limit
        }), 202
        
    except Exception as e:
        logger.error(f"Erro ao iniciar análise automática: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@health_bp.route("/status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    """
    Endpoint para verificar status de uma task.
    """
    try:
        task = celery_app.AsyncResult(task_id)
        
        if task.state == "PENDING":
            response = {
                "task_id": task_id,
                "state": task.state,
                "status": "Aguardando processamento..."
            }
        elif task.state == "PROGRESS":
            response = {
                "task_id": task_id,
                "state": task.state,
                "current": task.info.get("current", 0),
                "total": task.info.get("total", 0),
                "processed": task.info.get("processed", 0),
                "failed": task.info.get("failed", 0),
                "status": "Processando..."
            }
        elif task.state == "SUCCESS":
            response = {
                "task_id": task_id,
                "state": task.state,
                "result": task.result,
                "status": "Concluído com sucesso"
            }
        else:  # FAILURE ou outros estados
            response = {
                "task_id": task_id,
                "state": task.state,
                "error": str(task.info) if task.info else "Erro desconhecido",
                "status": "Falhou"
            }
            
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Erro ao verificar status da task {task_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
