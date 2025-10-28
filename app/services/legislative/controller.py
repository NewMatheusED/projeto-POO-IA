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

    def get_graph_partido_data(self) -> Dict[str, Any]:
        """
        Obtém dados para o gráfico de partido.

        Returns:
            Dados para o gráfico de partido
        """
        try:
            # TODO: Implementar lógica do gráfico de partido
            return {"message": "Funcionalidade em desenvolvimento"}
        except Exception as e:
            return None

    def generate_dados_pec(self) -> Dict[str, Any]:
        """
        Gera dados da tabela DADOS PEC baseado nos projetos de lei existentes.
        
        Mapeia os critérios de avaliação para os campos de impacto:
        - Impacto Social, Econômico, Político-Institucional, Constitucional, 
          Ambiental, Regional, Tecnológico, Geopolítico, Temporal
        
        Returns:
            Lista de dados PEC formatados
        """
        try:
            # Usa o mapeamento robusto centralizado
            criterio_to_impacto = self._get_criterio_mapping()
            
            # Busca todos os projetos com suas avaliações
            projetos = self.repository.get_all_projects_with_evaluations()
            
            if not projetos:
                return {
                    "success": True,
                    "total_pecs": 0,
                    "dados_pec": [],
                    "message": "Nenhum projeto encontrado no banco de dados"
                }
            
            dados_pec = []
            
            for projeto in projetos:
                # Valida se o projeto tem avaliações
                if not projeto.avaliacoes:
                    continue
                    
                # Inicializa campos de impacto
                impactos = {campo: 0 for campo in criterio_to_impacto.values()}
                
                # Processa avaliações paramétricas
                for avaliacao in projeto.avaliacoes:
                    criterio = avaliacao.criterio
                    nota = avaliacao.nota
                    
                    # Valida nota (deve ser inteiro)
                    if not isinstance(nota, int) or nota < 0:
                        continue
                    
                    # Mapeia critério para campo de impacto
                    if criterio in criterio_to_impacto:
                        campo_impacto = criterio_to_impacto[criterio]
                        impactos[campo_impacto] = nota
                
                # Calcula média (desconsiderando valores 0)
                notas_validas = [nota for nota in impactos.values() if nota > 0]
                media = round(sum(notas_validas) / len(notas_validas), 2) if notas_validas else 0.0
                
                # Determina qualidade baseada na média
                qualidade = "boa" if media >= 6 else "ruim"
                
                # Monta dados da PEC
                dados_pec.append({
                    "numero_pac": projeto.codigo_projeto,
                    "impacto_social": impactos["Impacto Social"],
                    "impacto_economico": impactos["Impacto Econômico"],
                    "impacto_politico_institucional": impactos["Impacto Político-Institucional"],
                    "impacto_constitucional": impactos["Impacto Constitucional"],
                    "impacto_ambiental": impactos["Impacto Ambiental"],
                    "impacto_regional": impactos["Impacto Regional"],
                    "impacto_tecnologico": impactos["Impacto Tecnológico"],
                    "impacto_geopolitico": impactos["Impacto Geopolítico"],
                    "impacto_temporal": impactos["Impacto Temporal"],
                    "media": media,
                    "qualidade": qualidade
                })
            
            return {
                "success": True,
                "total_pecs": len(dados_pec),
                "dados_pec": dados_pec
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "dados_pec": []
            }

    def generate_dados_sen(self) -> Dict[str, Any]:
        """
        Gera dados da tabela DADOS SEN baseado nos votos individuais dos senadores.
        
        Calcula impactos baseado nas PECs que o senador votou:
        - Se votou SIM para PEC ruim: subtrai do impacto
        - Se votou NÃO para PEC ruim: soma no impacto  
        - Se votou SIM para PEC boa: soma no impacto
        - Se votou NÃO para PEC boa: subtrai do impacto
        
        Returns:
            Lista de dados SEN formatados
        """
        try:
            # Busca todos os senadores únicos com seus votos
            senadores = self.repository.get_all_senators_with_votes()
            
            if not senadores:
                return {
                    "success": True,
                    "total_senadores": 0,
                    "dados_sen": [],
                    "message": "Nenhum senador com votos encontrado no banco de dados"
                }
            
            dados_sen = []
            
            for senador in senadores:
                # Valida dados básicos do senador
                if not senador.get('nome_senador') or not senador.get('votos'):
                    continue
                
                # Inicializa campos de impacto
                impactos = {
                    "Impacto Social": 0,
                    "Impacto Econômico": 0,
                    "Impacto Político-Institucional": 0,
                    "Impacto Constitucional": 0,
                    "Impacto Ambiental": 0,
                    "Impacto Regional": 0,
                    "Impacto Tecnológico": 0,
                    "Impacto Geopolítico": 0,
                    "Impacto Temporal": 0
                }
                
                # Processa cada voto do senador
                for voto in senador['votos']:
                    try:
                        projeto = voto.dados_votacao.projeto
                        qualidade_voto = voto.qualidade_voto
                        
                        # Valida qualidade do voto
                        if qualidade_voto not in ["S", "N", "A", "O"]:
                            continue
                        
                        # Obtém dados da PEC correspondente
                        pec_data = self._get_pec_data_for_senator(projeto)
                        if not pec_data:
                            continue
                        
                        # Aplica regras de cálculo baseado na qualidade do voto e da PEC
                        for campo, valor in pec_data["impactos"].items():
                            if campo in impactos and isinstance(valor, (int, float)) and valor > 0:
                                impacto_atual = impactos[campo]
                                
                                # Aplica regras de cálculo
                                if qualidade_voto == "S":  # Votou SIM
                                    if pec_data["qualidade"] == "ruim":
                                        # SIM para ruim: subtrai
                                        impactos[campo] = max(0, impacto_atual - int(valor))
                                    else:  # PEC boa
                                        # SIM para boa: soma
                                        impactos[campo] = impacto_atual + int(valor)
                                elif qualidade_voto == "N":  # Votou NÃO
                                    if pec_data["qualidade"] == "ruim":
                                        # NÃO para ruim: soma
                                        impactos[campo] = impacto_atual + int(valor)
                                    else:  # PEC boa
                                        # NÃO para boa: subtrai
                                        impactos[campo] = max(0, impacto_atual - int(valor))
                    except Exception as e:
                        # Log do erro mas continua processando outros votos
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Erro ao processar voto do senador {senador.get('nome_senador', 'desconhecido')}: {str(e)}")
                        continue
                
                # Calcula média (desconsiderando valores 0)
                valores_impacto = [valor for valor in impactos.values() if valor > 0]
                media = round(sum(valores_impacto) / len(valores_impacto), 2) if valores_impacto else 0.0
                
                # Monta dados do senador
                dados_sen.append({
                    "nome": senador.get('nome_senador', ''),
                    "partido": senador.get('partido', ''),
                    "idade": senador.get('idade'),
                    "estado": senador.get('uf', ''),
                    "genero": senador.get('sexo', ''),
                    "impacto_social": impactos["Impacto Social"],
                    "impacto_economico": impactos["Impacto Econômico"],
                    "impacto_politico_institucional": impactos["Impacto Político-Institucional"],
                    "impacto_constitucional": impactos["Impacto Constitucional"],
                    "impacto_ambiental": impactos["Impacto Ambiental"],
                    "impacto_regional": impactos["Impacto Regional"],
                    "impacto_tecnologico": impactos["Impacto Tecnológico"],
                    "impacto_geopolitico": impactos["Impacto Geopolítico"],
                    "impacto_temporal": impactos["Impacto Temporal"],
                    "media": media
                })
            
            return {
                "success": True,
                "total_senadores": len(dados_sen),
                "dados_sen": dados_sen
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "dados_sen": []
            }

    def _get_pec_data_for_senator(self, projeto) -> Optional[Dict[str, Any]]:
        """
        Obtém dados da PEC para cálculo de impacto do senador.
        
        Args:
            projeto: Projeto de lei
            
        Returns:
            Dados da PEC formatados ou None
        """
        try:
            # Usa o mesmo mapeamento robusto do generate_dados_pec
            criterio_to_impacto = self._get_criterio_mapping()
            
            # Inicializa campos de impacto
            impactos = {campo: 0 for campo in criterio_to_impacto.values()}
            
            # Processa avaliações paramétricas
            for avaliacao in projeto.avaliacoes:
                criterio = avaliacao.criterio
                nota = avaliacao.nota
                
                if criterio in criterio_to_impacto:
                    campo_impacto = criterio_to_impacto[criterio]
                    impactos[campo_impacto] = nota
            
            # Calcula média e qualidade
            notas_validas = [nota for nota in impactos.values() if nota > 0]
            media = round(sum(notas_validas) / len(notas_validas), 2) if notas_validas else 0.0
            qualidade = "boa" if media >= 6 else "ruim"
            
            return {
                "impactos": impactos,
                "media": media,
                "qualidade": qualidade
            }
            
        except Exception as e:
            return None

    def _get_criterio_mapping(self) -> Dict[str, str]:
        """
        Retorna o mapeamento robusto dos critérios para campos de impacto.
        
        Lida com inconsistências de nomenclatura na base de dados.
        
        Returns:
            Dicionário mapeando variações de critérios para campos padronizados
        """
        return {
            # Impacto Social - variações
            "Impacto Social": "Impacto Social",
            "Impacto_Social": "Impacto Social",
            "impacto_social": "Impacto Social",
            "Impacto Social/Comunitário": "Impacto Social",
            "Impacto Social/Comunitario": "Impacto Social",
            "impacto_social_comunitario": "Impacto Social",
            "Impacto_Social_Comunitario": "Impacto Social",
            
            # Impacto Econômico - variações
            "Impacto Econômico": "Impacto Econômico",
            "Impacto_Economico": "Impacto Econômico",
            "impacto_economico": "Impacto Econômico",
            "Impacto Economico": "Impacto Econômico",
            "Impacto Econômico/Financeiro": "Impacto Econômico",
            "Impacto Economico/Financeiro": "Impacto Econômico",
            "impacto_economico_financeiro": "Impacto Econômico",
            "Impacto_Economico_Financeiro": "Impacto Econômico",
            
            # Impacto Político-Institucional - variações
            "Impacto Político-Institucional": "Impacto Político-Institucional",
            "Impacto_Politico_Institucional": "Impacto Político-Institucional",
            "impacto_politico_institucional": "Impacto Político-Institucional",
            "Impacto Politico_Institucional": "Impacto Político-Institucional",
            "Impacto Político/Institucional": "Impacto Político-Institucional",
            "Impacto Politico/Institucional": "Impacto Político-Institucional",
            "Impacto Político-Institucional/Governamental": "Impacto Político-Institucional",
            "impacto_politico_institucional_governamental": "Impacto Político-Institucional",
            "Impacto_Politico_Institucional_Governamental": "Impacto Político-Institucional",
            
            # Impacto Constitucional - variações
            "Impacto Constitucional": "Impacto Constitucional",
            "Impacto_Constitucional": "Impacto Constitucional",
            "Impacto Legal/Constitucional": "Impacto Constitucional",
            "Impacto Legal_Constitucional": "Impacto Constitucional",
            "impacto_constitucional": "Impacto Constitucional",
            "Impacto Legal-Constitucional": "Impacto Constitucional",
            "impacto_constitucional_legal": "Impacto Constitucional",
            "impacto_legal_constitucional": "Impacto Constitucional",
            "Impacto_Legal_Constitucional": "Impacto Constitucional",
            
            # Impacto Ambiental - variações
            "Impacto Ambiental": "Impacto Ambiental",
            "Impacto_Ambiental": "Impacto Ambiental",
            "impacto_ambiental": "Impacto Ambiental",
            "Impacto Ambiental/Ecológico": "Impacto Ambiental",
            "Impacto Ambiental/Ecologico": "Impacto Ambiental",
            "impacto_ambiental_ecologico": "Impacto Ambiental",
            "Impacto_Ambiental_Ecologico": "Impacto Ambiental",

            # Impacto Regional - variações
            "Impacto Regional": "Impacto Regional",
            "Impacto_Regional": "Impacto Regional",
            "impacto_regional": "Impacto Regional",
            "Impacto Regional/Setorial": "Impacto Regional",
            "Impacto Regional_Setorial": "Impacto Regional",
            "Impacto Regional-Setorial": "Impacto Regional",
            "impacto_regional_setorial": "Impacto Regional",
            "Impacto_Regional_Setorial": "Impacto Regional",
            
            # Impacto Tecnológico - variações
            "Impacto Tecnológico": "Impacto Tecnológico",
            "Impacto_Tecnologico": "Impacto Tecnológico",
            "impacto_tecnologico": "Impacto Tecnológico",
            "Impacto Tecnologico": "Impacto Tecnológico",
            "Impacto Tecnológico/Inovação": "Impacto Tecnológico",
            "Impacto Tecnologico_Inovacao": "Impacto Tecnológico",
            "Impacto Tecnológico/Inovação": "Impacto Tecnológico",
            "Impacto Tecnologico/Inovacao": "Impacto Tecnológico",
            "impacto_tecnologico_inovacao": "Impacto Tecnológico",
            "Impacto_Tecnologico_Inovacao": "Impacto Tecnológico",
            
            # Impacto Geopolítico - variações
            "Impacto Geopolítico": "Impacto Geopolítico",
            "Impacto_Geopolitico": "Impacto Geopolítico",
            "impacto_geopolitico": "Impacto Geopolítico",
            "Impacto Geopolitico": "Impacto Geopolítico",
            "Impacto Internacional/Geopolítico": "Impacto Geopolítico",
            "Impacto Internacional_Geopolitico": "Impacto Geopolítico",
            "Impacto Internacional/Geopolitico": "Impacto Geopolítico",
            "impacto_geopolitico_internacional": "Impacto Geopolítico",
            "Impacto_Geopolitico_Internacional": "Impacto Geopolítico",
            
            # Impacto Temporal - variações
            "Impacto Temporal": "Impacto Temporal",
            "Impacto_Temporal": "Impacto Temporal",
            "impacto_temporal": "Impacto Temporal",
            "Impacto Temporal/Longo Prazo": "Impacto Temporal",
            "Impacto Temporal_Longo Prazo": "Impacto Temporal",
            "Impacto Temporal-Longo Prazo": "Impacto Temporal",
            "Impacto Temporal/Prazo": "Impacto Temporal",
            "impacto_temporal_longo_prazo": "Impacto Temporal",
            "Impacto_Temporal_Longo_Prazo": "Impacto Temporal",
        }

    def get_unique_criterios(self) -> List[str]:
        """
        Retorna lista de critérios únicos encontrados na base de dados.
        
        Útil para identificar inconsistências de nomenclatura.
        
        Returns:
            Lista de critérios únicos
        """
        try:
            from app.services.legislative.models import AvaliacaoParametricaDB
            from app.database import db
            
            # Busca todos os critérios únicos
            criterios = db.session.query(AvaliacaoParametricaDB.criterio).distinct().all()
            
            # Extrai apenas os valores (remove tuplas)
            criterios_list = [criterio[0] for criterio in criterios if criterio[0]]
            
            # Ordena alfabeticamente
            criterios_list.sort()
            
            return criterios_list
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao buscar critérios únicos: {str(e)}")
            return []