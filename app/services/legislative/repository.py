"""
Repository para operações de banco de dados legislativas.

Responsável por persistir e recuperar dados de análise legislativa.
"""

from typing import Any, Dict, List, Optional
import logging

from app.database import db
from app.services.legislative.models import ProjetoLei, AvaliacaoParametricaDB, DadosVotacaoDB

logger = logging.getLogger(__name__)


class LegislativeRepository:
    """Repository para operações de banco de dados legislativas."""

    def save_analysis(self, project_id: str, analysis_data: Dict[str, Any], votes_data: Optional[Dict[str, Any]] = None) -> ProjetoLei:
        """
        Salva análise completa de um projeto de lei.

        Args:
            project_id: Código do projeto
            analysis_data: Dados da análise
            votes_data: Dados de votação (opcional)

        Returns:
            ProjetoLei salvo
        """
        # Verifica se já existe
        existing_project = self.get_project_by_id(project_id)
        
        if existing_project:
            logger.info(f"Projeto {project_id} já existe no banco (ID: {existing_project.id}) - Atualizando dados")
            projeto = existing_project
            
            # Atualiza dados do projeto
            projeto.contexto_epoca = analysis_data.get("contexto_epoca", projeto.contexto_epoca)
            projeto.resumo_objetivo = analysis_data.get("resumo_objetivo", projeto.resumo_objetivo)
            projeto.interpretacao_simplificada = analysis_data.get("interpretacao_simplificada", projeto.interpretacao_simplificada)
            projeto.nota_media = self._calculate_average_score(analysis_data.get("avaliacao_parametrica", []))
            
            # Remove avaliações antigas
            for avaliacao in projeto.avaliacoes:
                db.session.delete(avaliacao)
            
            # Remove dados de votação antigos
            if projeto.dados_votacao_db:
                db.session.delete(projeto.dados_votacao_db)
        else:
            # Cria novo projeto
            projeto = self._create_project(project_id, analysis_data)
        
        # Salva avaliações paramétricas
        self._save_parametric_evaluations(projeto.id, analysis_data.get("avaliacao_parametrica", []))
        
        # Salva dados de votação se disponíveis
        if votes_data:
            try:
                self._save_votes_data(projeto.id, votes_data)
            except Exception as e:
                logger.warning(f"Aviso: Não foi possível salvar dados de votação: {str(e)}")
                # Continua mesmo sem salvar os dados de votação
        
        db.session.commit()
        logger.info(f"Projeto {project_id} salvo/atualizado com sucesso (ID: {projeto.id})")
        return projeto

    def get_project_by_id(self, project_id: str) -> Optional[ProjetoLei]:
        """Busca projeto pelo código."""
        return ProjetoLei.query.filter_by(codigo_projeto=project_id).first()

    def get_project_with_evaluations(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Busca projeto com avaliações paramétricas."""
        projeto = self.get_project_by_id(project_id)
        if not projeto:
            return None
        
        return {
            "projeto": projeto,
            "avaliacoes": projeto.avaliacoes,
            "total_avaliacoes": len(projeto.avaliacoes)
        }

    def list_projects(self, limit: int = 50, offset: int = 0) -> List[ProjetoLei]:
        """Lista projetos com paginação."""
        return ProjetoLei.query.order_by(ProjetoLei.created_at.desc()).offset(offset).limit(limit).all()

    def get_projects_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas dos projetos."""
        total_projetos = ProjetoLei.query.count()
        projetos_com_avaliacoes = db.session.query(ProjetoLei).join(AvaliacaoParametricaDB).distinct().count()
        
        # Média das notas
        avg_nota = db.session.query(db.func.avg(ProjetoLei.nota_media)).scalar() or 0.0
        
        return {
            "total_projetos": total_projetos,
            "projetos_com_avaliacoes": projetos_com_avaliacoes,
            "nota_media_geral": round(avg_nota, 2)
        }

    def _create_project(self, project_id: str, analysis_data: Dict[str, Any]) -> ProjetoLei:
        """Cria novo projeto."""
        projeto = ProjetoLei(
            codigo_projeto=project_id,
            contexto_epoca=analysis_data.get("contexto_epoca", ""),
            resumo_objetivo=analysis_data.get("resumo_objetivo", ""),
            interpretacao_simplificada=analysis_data.get("interpretacao_simplificada", ""),
            nota_media=self._calculate_average_score(analysis_data.get("avaliacao_parametrica", []))
        )
        
        db.session.add(projeto)
        db.session.flush()
        return projeto

    def _update_project(self, projeto: ProjetoLei, analysis_data: Dict[str, Any]) -> None:
        """Atualiza projeto existente."""
        projeto.contexto_epoca = analysis_data.get("contexto_epoca", projeto.contexto_epoca)
        projeto.resumo_objetivo = analysis_data.get("resumo_objetivo", projeto.resumo_objetivo)
        projeto.interpretacao_simplificada = analysis_data.get("interpretacao_simplificada", projeto.interpretacao_simplificada)
        projeto.nota_media = self._calculate_average_score(analysis_data.get("avaliacao_parametrica", []))
        
        # Remove avaliações antigas
        for avaliacao in projeto.avaliacoes:
            db.session.delete(avaliacao)

    def _save_parametric_evaluations(self, projeto_id: int, avaliacoes: List[Dict[str, Any]]) -> None:
        """Salva avaliações paramétricas."""
        for avaliacao_data in avaliacoes:
            avaliacao = AvaliacaoParametricaDB(
                projeto_id=projeto_id,
                criterio=avaliacao_data.get("criterio", ""),
                resumo=avaliacao_data.get("resumo", ""),
                nota=avaliacao_data.get("nota", 0),
                justificativa=avaliacao_data.get("justificativa", "")
            )
            db.session.add(avaliacao)

    def _calculate_average_score(self, avaliacoes: List[Dict[str, Any]]) -> float:
        """Calcula nota média das avaliações, desconsiderando notas 0 (nulo)."""
        if not avaliacoes:
            return 0.0
        
        # Filtra apenas notas válidas (maiores que 0)
        notas_validas = [av.get("nota", 0) for av in avaliacoes if av.get("nota", 0) > 0]
        
        if not notas_validas:
            return 0.0
        
        total_notas = sum(notas_validas)
        return round(total_notas / len(notas_validas), 2)

    def _save_votes_data(self, projeto_id: int, votes_data: Dict[str, Any]) -> None:
        """Salva dados de votação."""
        from app.services.legislative.models import VotoIndividualDB
        
        # Remove dados de votação antigos se existirem
        existing_votes = DadosVotacaoDB.query.filter_by(projeto_id=projeto_id).first()
        if existing_votes:
            db.session.delete(existing_votes)

        # Cria novos dados de votação
        dados_votacao = DadosVotacaoDB(
            projeto_id=projeto_id,
            total_votos=votes_data.get("total_votos", 0),
            votos_favoraveis=votes_data.get("votos_favoraveis", 0),
            votos_contrarios=votes_data.get("votos_contrarios", 0),
            votos_abstencoes=votes_data.get("votos_abstencoes", 0),
            taxa_aprovacao=votes_data.get("taxa_aprovacao", 0.0),
            status_final=votes_data.get("status_final", "sem_votos"),
            data_votacao=votes_data.get("data_votacao"),
            camara_votacao=votes_data.get("camara_votacao")
        )
        db.session.add(dados_votacao)
        db.session.flush()  # Para obter o ID dos dados de votação
        
        # Salva votos individuais
        votos_individuais = votes_data.get("votos_individuais", [])
        
        for voto_data in votos_individuais:
            voto_individual = VotoIndividualDB(
                dados_votacao_id=dados_votacao.id,
                nome_senador=voto_data.get("NomeParlamentar", ""),
                partido=voto_data.get("SiglaPartidoParlamentar", ""),  # Nome correto da chave
                uf="",  # TODO: Será preenchido posteriormente via endpoint específico
                qualidade_voto=voto_data.get("QualidadeVoto", ""),
                justificativa=voto_data.get("JustificativaVoto", "")
            )
            db.session.add(voto_individual)

    def delete_project(self, project_id: str) -> bool:
        """Remove projeto e suas avaliações."""
        projeto = self.get_project_by_id(project_id)
        if not projeto:
            return False
        
        db.session.delete(projeto)
        db.session.commit()
        return True
