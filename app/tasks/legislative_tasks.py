"""
Tasks do Celery para automação da análise legislativa.

Rotina automatizada que:
1. Busca projetos no endpoint de emendas
2. Verifica se tem votos
3. Envia para IA analisar
4. Salva no banco
"""

import logging
import requests
from typing import Dict, List, Any, Optional

from app.services.legislative.controller import LegislativeController

from app.tasks.flask_app_context import flask_app_context

logger = logging.getLogger(__name__)

from .celery_config import celery_app

@celery_app.task(bind=True, name='app.tasks.legislative_tasks.analyze_project')
def analyze_project(self, limit: int = 5) -> Dict[str, Any]:
    """
    Task para processar projetos automaticamente.
    
    Args:
        limit: Quantos projetos processar (padrão: 5)
    
    Returns:
        Resultado do processamento
    """
    # Configura contexto da aplicação Flask para acesso ao banco
    with flask_app_context():

        try:
            logger.info(f"🚀 Iniciando análise automática de {limit} projetos")
        
            # 1. Busca projetos no endpoint de emendas
            projetos = buscar_projetos_emendas(limit=limit)
            
            if not projetos:
                logger.warning("Nenhum projeto encontrado")
                return {
                    "success": False,
                    "error": "Nenhum projeto encontrado",
                    "processed": 0,
                    "failed": 0
                }
            
            # 2. Processa cada projeto
            from app.services.ia.controller import AIController
            controller = LegislativeController()
            ai_controller = AIController()
            results = []
            processed = 0
            failed = 0
            skipped = 0
            
            for i, projeto in enumerate(projetos[:limit]):
                try:
                    project_id = projeto["project_id"]
                    logger.info(f"📋 Processando projeto {i+1}/{min(len(projetos), limit)}: {project_id}")
                    
                    # Verifica se o projeto já existe no banco
                    existing_project = controller.repository.get_project_by_id(project_id)
                    if existing_project:
                        logger.info(f"Projeto {project_id} já existe no banco (ID: {existing_project.id}) - Pulando análise")
                        results.append({
                            "project_id": project_id,
                            "success": True,
                            "has_votes": True,  # Assumimos que já foi analisado
                            "processing_time": 0.0,
                            "skipped": True,
                            "message": "Projeto já existe no banco"
                        })
                        skipped += 1
                        continue
                    
                    # Executa análise completa usando o controller COM IA
                    result = controller.analyze_project(
                        project_id=project_id,
                        check_votes=True,
                        ai_controller=ai_controller
                    )
                    
                    # Se a análise foi bem-sucedida, salva no banco
                    if result.success and result.analise:
                        try:
                            # Salva a análise no banco
                            analysis_dict = result.analise.to_dict()
                            saved_project = controller.repository.save_analysis(
                                project_id=project_id,
                                analysis_data=analysis_dict,
                                votes_data=result.analise.dados_votacao
                            )
                            logger.info(f"{project_id} - Dados salvos no banco com ID: {saved_project.id}")
                        except Exception as e:
                            logger.error(f"{project_id} - Erro ao salvar no banco: {str(e)}")
                            result.success = False
                            result.error = f"Análise concluída mas erro ao salvar: {str(e)}"
                    
                    results.append({
                        "project_id": project_id,
                        "success": result.success,
                        "has_votes": result.has_votes,
                        "processing_time": result.processing_time,
                        "error": result.error if not result.success else None
                    })
                    
                    if result.success:
                        processed += 1
                        logger.info(f"{project_id} - Análise concluída e salva com sucesso!")
                    else:
                        failed += 1
                        logger.warning(f"{project_id} - Falha: {result.error}")
                    
                    # Atualiza progresso
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i + 1,
                            'total': min(len(projetos), limit),
                            'processed': processed,
                            'failed': failed
                        }
                    )
                    
                except Exception as e:
                    failed += 1
                    error_msg = f"Erro ao processar {projeto.get('project_id', 'N/A')}: {str(e)}"
                    logger.error(error_msg)
                    results.append({
                        "project_id": projeto.get("project_id", "N/A"),
                        "success": False,
                        "error": error_msg
                    })
            
            # 3. Resultado final
            final_result = {
                "success": True,
                "total_found": len(projetos),
                "total_processed": min(len(projetos), limit),
                "processed": processed,
                "failed": failed,
                "skipped": skipped,
                "success_rate": (processed / (processed + failed) * 100) if (processed + failed) > 0 else 0,
                "results": results
            }
            
            logger.info(f"📊 Processamento concluído: {processed} sucessos, {failed} falhas, {skipped} pulados")
            return final_result
            
        except Exception as e:
            error_msg = f"Erro geral no processamento em lote: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "processed": 0,
                "failed": 0
            }


def buscar_projetos_emendas(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Busca projetos no endpoint de emendas do Senate Tracker.
    
    Args:
        limit: Quantos projetos buscar (padrão: 10)
    
    Returns:
        Lista de projetos encontrados
    """
    try:
        base_url = "https://api.senate-tracker.com.br"
        url = f"{base_url}/v1/processo/emendas/geral"
        # params = {
        #     "filtro": "PEC", 
        # }
        
        logger.info(f"Buscando {limit} projetos PLS automaticamente...")
        
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()

            if isinstance(data, dict) and "data" in data:
                emendas = data["data"]
                # Extrai projetos únicos (remove duplicatas de emendas)MS
                processos_unicos = {}
                for emenda in emendas:
                    if isinstance(emenda, dict) and "idProcesso" in emenda:
                        id_processo = emenda["idProcesso"]
                        if id_processo not in processos_unicos:
                            # Busca dados do projeto para obter project_id
                            project_data = buscar_dados_projeto(id_processo)
                            if project_data:
                                processos_unicos[id_processo] = project_data
                projetos = list(processos_unicos.values())
                logger.info(f"Encontrados {len(projetos)} projetos PLS")
                return projetos
            else:
                logger.warning("Estrutura de resposta inválida")
                return []
        else:
            logger.error(f"Erro na busca: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Erro ao buscar projetos: {str(e)}")
        return []

def buscar_dados_projeto(id_processo: str) -> Optional[Dict[str, Any]]:
    """
    Busca dados completos de um projeto usando o endpoint do Senate Tracker.
    
    Args:
        id_processo: ID do processo
    
    Returns:
        Dados do projeto ou None
    """
    try:
        base_url = "https://api.senate-tracker.com.br"
        url = f"{base_url}/v1/processo/{id_processo}"
        
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            projeto_data = data.get("data", {})
            
            # Extrai informações necessárias
            sigla = projeto_data.get("sigla", "")
            numero = projeto_data.get("numero", "")
            ano = projeto_data.get("ano", "")
            
            if sigla and numero and ano:
                project_id = f"{sigla} {numero}/{ano}"
                return {
                    "id_processo": id_processo,
                    "project_id": project_id,
                    "sigla": sigla,
                    "numero": numero,
                    "ano": ano,
                    "descricao": projeto_data.get("Ementa", "")[:200] + "..." if projeto_data.get("Ementa") else "N/A"
                }
            else:
                logger.warning(f"Projeto {id_processo} não tem todos os campos necessários")
                return None
        else:
            logger.warning(f"Projeto {id_processo} não encontrado (HTTP {response.status_code})")
            return None
            
    except Exception as e:
        logger.error(f"Erro ao buscar projeto {id_processo}: {str(e)}")
        return None


@celery_app.task(bind=True, name='app.tasks.legislative_tasks.automated_analysis')
def automated_analysis(self, limit: int = 10) -> Dict[str, Any]:
    """
    Task periódica para análise automática de projetos.
    Executada automaticamente pelo Celery Beat.
    
    Args:
        limit: Quantos projetos processar por execução (padrão: 10)
    
    Returns:
        Resultado do processamento
    """
    logger.info(f"🔄 Iniciando análise automática periódica - Limit: {limit} projetos")
    
    try:
        # Chama a task principal de análise
        result = analyze_project.delay(limit=limit)
        
        return {
            "success": True,
            "message": f"Análise automática iniciada - Limit: {limit} projetos",
            "task_id": result.id,
            "status_url": f"/v1/test/status/{result.id}"
        }
        
    except Exception as e:
        error_msg = f"Erro ao iniciar análise automática: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "task_id": None
        }
