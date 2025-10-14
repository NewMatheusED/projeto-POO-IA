"""
Persistidor de dados para banco de dados.

Implementa persistência real em banco de dados.
"""

from typing import Any, Dict, Optional

from app.services.ia.data_processing.interfaces import DataPersistenceError, DataPersister


class DatabasePersister(DataPersister):
    """Persistidor para banco de dados real."""

    def __init__(self, database_config: Optional[Dict[str, Any]] = None):
        """
        Inicializa o persistidor de banco.

        Args:
            database_config: Configuração do banco de dados
        """
        self.database_config = database_config or {}
        # Usa a sessão do SQLAlchemy já configurada
        from app.database import db
        self._session = db.session

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Salva dados no banco de dados.

        Args:
            data: Dados para salvar

        Returns:
            Dados salvos com metadados
        """
        try:
            # Salva usando o repository legislativo se for análise legislativa
            if data.get("project_id") and "analysis_data" in data:
                from app.services.legislative.repository import LegislativeRepository
                repository = LegislativeRepository()
                
                saved_project = repository.save_analysis(
                    project_id=data["project_id"],
                    analysis_data=data["analysis_data"],
                    votes_data=data.get("dados_votacao")
                )
                
                data["id"] = saved_project.id
                data["metadata"] = data.get("metadata", {})
                data["metadata"]["persistence_status"] = "saved_to_db"
                data["metadata"]["persistence_type"] = "legislative_analysis"
                data["metadata"]["saved_at"] = self._get_timestamp()
            else:
                # Para outros tipos de dados, salva em tabela genérica
                self._save_generic_data(data)
                data["metadata"] = data.get("metadata", {})
                data["metadata"]["persistence_status"] = "saved_to_db"
                data["metadata"]["persistence_type"] = "generic_data"
                data["metadata"]["saved_at"] = self._get_timestamp()

            return data

        except Exception as e:
            self._session.rollback()
            raise DataPersistenceError(f"Erro ao salvar dados no banco: {str(e)}")

    def _get_timestamp(self) -> str:
        """Retorna timestamp atual."""
        from datetime import datetime

        return datetime.now().isoformat()

    def get_by_id(self, data_id: int) -> Optional[Dict[str, Any]]:
        """
        Retorna dados por ID.

        Args:
            data_id: ID dos dados

        Returns:
            Dados encontrados ou None
        """
        try:
            # Busca em projetos legislativos primeiro
            from app.services.legislative.models import ProjetoLei
            projeto = ProjetoLei.query.get(data_id)
            if projeto:
                return {
                    "id": projeto.id,
                    "project_id": projeto.codigo_projeto,
                    "analysis_data": {
                        "avaliacao_parametrica": [av.to_dict() for av in projeto.avaliacoes]
                    },
                    "dados_votacao": projeto.dados_votacao_db.to_dict() if projeto.dados_votacao_db else None
                }
            return None
        except Exception as e:
            print(f"Erro ao buscar dados por ID {data_id}: {str(e)}")
            return None

    def delete_by_id(self, data_id: int) -> bool:
        """
        Remove dados por ID.

        Args:
            data_id: ID dos dados

        Returns:
            True se removido, False se não encontrado
        """
        try:
            # Remove projeto legislativo
            from app.services.legislative.models import ProjetoLei
            projeto = ProjetoLei.query.get(data_id)
            if projeto:
                self._session.delete(projeto)
                self._session.commit()
                return True
            return False
        except Exception as e:
            self._session.rollback()
            print(f"Erro ao deletar dados ID {data_id}: {str(e)}")
            return False

    def _save_generic_data(self, data: Dict[str, Any]) -> None:
        """Salva dados genéricos em tabela de processamento."""
        # Por enquanto, apenas log - pode ser expandido futuramente
        print(f"Salvando dados genéricos: {data.get('type', 'unknown')}")
        # TODO: Implementar tabela genérica de processamento se necessário


# Função de conveniência para criar persistidor de banco
def create_database_persister(database_config: Optional[Dict[str, Any]] = None) -> DatabasePersister:
    """
    Cria persistidor de banco.

    Args:
        database_config: Configuração do banco de dados

    Returns:
        Instância do persistidor de banco
    """
    return DatabasePersister(database_config)
