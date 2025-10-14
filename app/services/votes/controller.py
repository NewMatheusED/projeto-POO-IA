"""
Controller para serviços de votos.

Orquestra operações relacionadas a votação de projetos de lei.
"""

from typing import Any, Dict, List, Optional

from app.services.votes.service import SenateTrackerVotesService


class VotesController:
    """Controller para operações de votos."""

    def __init__(self, votes_service: Optional[SenateTrackerVotesService] = None):
        """
        Inicializa o controller.

        Args:
            votes_service: Serviço de votos (opcional, usa serviço real por padrão)
        """
        self.votes_service = votes_service or SenateTrackerVotesService()

    def check_project_has_votes(self, project_id: str) -> bool:
        """
        Verifica se um projeto possui votos registrados.

        Args:
            project_id: Código do projeto

        Returns:
            True se tem votos suficientes, False caso contrário
        """
        return self.votes_service.check_project_has_votes(project_id)

    def get_project_votes(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém dados completos de votação de um projeto.

        Args:
            project_id: Código do projeto

        Returns:
            Dados de votação em formato dicionário ou None
        """
        votes_data = self.votes_service.get_project_votes(project_id)
        return votes_data.to_dict() if votes_data else None

    def batch_check_votes(self, project_ids: List[str]) -> Dict[str, bool]:
        """
        Verifica votos para múltiplos projetos.

        Args:
            project_ids: Lista de códigos de projetos

        Returns:
            Dicionário com resultado para cada projeto
        """
        return self.votes_service.batch_check_votes(project_ids)

    def get_relevant_projects(self, project_ids: List[str]) -> List[str]:
        """
        Filtra projetos que possuem votos (relevantes para análise).

        Args:
            project_ids: Lista de códigos de projetos

        Returns:
            Lista de projetos relevantes (com votos)
        """
        votes_results = self.batch_check_votes(project_ids)
        return [pid for pid, has_votes in votes_results.items() if has_votes]

    def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """
        Obtém status completo de um projeto.

        Args:
            project_id: Código do projeto

        Returns:
            Status completo do projeto
        """
        has_votes = self.check_project_has_votes(project_id)
        votes_data = self.get_project_votes(project_id)

        return {"project_id": project_id, "has_votes": has_votes, "status": "relevant" if has_votes else "irrelevant", "votes_data": votes_data, "can_analyze": has_votes}
