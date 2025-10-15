"""
Controller para serviços legislativos.

Orquestra operações de análise legislativa integrando com outros serviços.
"""

from typing import Any, Dict, List, Optional

from app.services.legislative.models import RespostaAnaliseCompleta
from app.services.legislative.service import LegislativeService
from app.services.legislative.repository import LegislativeRepository
from app.services.votes.controller import VotesController


class LegislativeController:
    """Controller para operações legislativas."""

    def __init__(self, legislative_service: Optional[LegislativeService] = None, votes_controller: Optional[VotesController] = None, repository: Optional[LegislativeRepository] = None):
        """
        Inicializa o controller.

        Args:
            legislative_service: Serviço legislativo
            votes_controller: Controller de votos
            repository: Repository para operações de banco
        """
        self.legislative_service = legislative_service or LegislativeService()
        self.votes_controller = votes_controller or VotesController()
        self.repository = repository or LegislativeRepository()

    def analyze_project(self, project_id: str, check_votes: bool = True, ai_controller: Optional[Any] = None) -> RespostaAnaliseCompleta:
        """
        Analisa um projeto de lei completo.

        Args:
            project_id: Código do projeto
            check_votes: Se deve verificar votos antes de analisar
            ai_controller: Controller da IA (injetado)

        Returns:
            Resposta completa da análise
        """
        import time

        start_time = time.time()

        try:
            # 1. Verifica se o projeto tem votos (se solicitado)
            has_votes = True
            if check_votes:
                has_votes = self.votes_controller.check_project_has_votes(project_id)
                if not has_votes:
                    return RespostaAnaliseCompleta(
                        success=False,
                        project_id=project_id,
                        error=f"Projeto {project_id} não possui votos registrados e é irrelevante para análise",
                        has_votes=False,
                        processing_time=time.time() - start_time,
                    )

            # 2. Executa análise com IA (se controller fornecido)
            if ai_controller:
                ai_response = self._get_ai_analysis(project_id, ai_controller)
                if not ai_response:
                    return RespostaAnaliseCompleta(success=False, project_id=project_id, error="Erro na análise da IA", has_votes=has_votes, processing_time=time.time() - start_time)

                # 3. Processa resposta da IA
                analise = self.legislative_service.parse_ai_response(project_id, ai_response)

                # 4. Enriquece com dados de votos
                votes_data = self.votes_controller.get_project_votes(project_id, include_senator_details=True)
                if votes_data:
                    # Atribui dados de votos diretamente (já é um dict)
                    analise.dados_votacao = votes_data

                return RespostaAnaliseCompleta(success=True, project_id=project_id, analise=analise, has_votes=has_votes, processing_time=time.time() - start_time)
            else:
                # Retorna estrutura básica sem análise da IA
                return RespostaAnaliseCompleta(success=True, project_id=project_id, has_votes=has_votes, processing_time=time.time() - start_time)

        except Exception as e:
            return RespostaAnaliseCompleta(success=False, project_id=project_id, error=str(e), has_votes=has_votes if "has_votes" in locals() else None, processing_time=time.time() - start_time)

    def save_analysis_data(self, project_id: str, analysis_data: Dict[str, Any], validate: bool = True, check_votes: bool = True) -> RespostaAnaliseCompleta:
        """
        Salva dados de análise diretamente (do playground).

        Segue o MESMO fluxo da análise da IA para garantir consistência.

        Args:
            project_id: Código do projeto
            analysis_data: Dados de análise para salvar (mesmo formato da IA)
            validate: Se deve validar os dados antes de salvar
            check_votes: Se deve verificar votos antes de salvar

        Returns:
            Resposta da operação
        """
        import time

        start_time = time.time()

        try:
            # 0. Verifica se o projeto existe
            if self.repository.get_project_by_id(project_id):
                return RespostaAnaliseCompleta(
                    success=False,
                    project_id=project_id,
                    error=f"Projeto {project_id} encontrado e não pode ser salvo novamente",
                )

            # 1. Verifica votos (mesmo processo da IA)
            has_votes = True
            if check_votes:
                has_votes = self.votes_controller.check_project_has_votes(project_id)
                if not has_votes:
                    return RespostaAnaliseCompleta(
                        success=False,
                        project_id=project_id,
                        error=f"Projeto {project_id} não possui votos registrados e é irrelevante para análise",
                        has_votes=False,
                        processing_time=time.time() - start_time,
                    )

            # 2. Valida dados se solicitado
            if validate and not self.legislative_service.validate_analysis_data(analysis_data):
                return RespostaAnaliseCompleta(
                    success=False, project_id=project_id, error="Dados de análise inválidos - estrutura não confere com formato esperado", has_votes=has_votes, processing_time=time.time() - start_time
                )

            # 3. Converte para modelo estruturado (mesmo processo da IA)
            analise = self.legislative_service.parse_ai_response(project_id, analysis_data)

            # 4. Enriquece com dados de votos (incluindo detalhes dos senadores para persistência)
            votes_data = self.votes_controller.get_project_votes(project_id, include_senator_details=True)
            if votes_data:
                # Atribui dados de votos diretamente (já é um dict)
                analise.dados_votacao = votes_data

            # Persiste no banco de dados
            try:
                saved_project = self.repository.save_analysis(
                    project_id=project_id,
                    analysis_data=analysis_data,
                    votes_data=votes_data
                )
                analise.dados_votacao = votes_data  # Adiciona dados de votação à resposta
            except Exception as e:
                # Log do erro mas não falha a operação
                print(f"Erro ao salvar no banco: {str(e)}")
                analise.dados_votacao = votes_data

            return RespostaAnaliseCompleta(success=True, project_id=project_id, analise=analise, has_votes=has_votes, processing_time=time.time() - start_time)

        except Exception as e:
            return RespostaAnaliseCompleta(success=False, project_id=project_id, error=str(e), has_votes=has_votes if "has_votes" in locals() else None, processing_time=time.time() - start_time)

    def batch_analyze_projects(self, project_ids: List[str], ai_controller: Optional[Any] = None) -> Dict[str, Any]:
        """
        Analisa múltiplos projetos em lote.

        Args:
            project_ids: Lista de códigos de projetos
            ai_controller: Controller da IA

        Returns:
            Resultado do processamento em lote
        """
        results = []
        successful = 0
        failed = 0

        for project_id in project_ids:
            try:
                result = self.analyze_project(project_id, check_votes=True, ai_controller=ai_controller)
                results.append(result.to_dict())
                if result.success:
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                results.append({"success": False, "error": str(e), "project_id": project_id})
                failed += 1

        return {"success": failed == 0, "total_projects": len(project_ids), "successful": successful, "failed": failed, "results": results}

    def _get_ai_analysis(self, project_id: str, ai_controller: Any) -> Optional[Dict[str, Any]]:
        """
        Obtém análise da IA para o projeto.

        Args:
            project_id: Código do projeto
            ai_controller: Controller da IA

        Returns:
            Resposta da IA ou None se erro
        """
        try:
            # Constrói prompt do usuário
            user_message = self.legislative_service.build_user_prompt(project_id)

            # Executa análise com IA
            ai_response = ai_controller.chat_completion(user_message=user_message, system_message=self.legislative_service.get_system_prompt(), response_format="json_object")


            return ai_response

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"{project_id} - Erro na análise da IA: {str(e)}")
            return None
