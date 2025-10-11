"""
Interfaces para processamento de dados.

Define contratos para processamento, enriquecimento e persistência de dados.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class DataProcessor(ABC):
    """Interface base para processadores de dados."""

    @abstractmethod
    def process(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa dados brutos e retorna dados estruturados.

        Args:
            raw_data: Dados brutos para processar

        Returns:
            Dados processados e estruturados

        Raises:
            DataProcessingError: Em caso de erro no processamento
        """
        pass


class DataEnricher(ABC):
    """Interface para enriquecimento de dados."""

    @abstractmethod
    def enrich(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriquece dados com informações de APIs externas.

        Args:
            data: Dados base para enriquecer

        Returns:
            Dados enriquecidos

        Raises:
            DataEnrichmentError: Em caso de erro no enriquecimento
        """
        pass


class DataPersister(ABC):
    """Interface para persistência de dados."""

    @abstractmethod
    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persiste dados no sistema.

        Args:
            data: Dados para persistir

        Returns:
            Dados salvos com identificadores

        Raises:
            DataPersistenceError: Em caso de erro na persistência
        """
        pass


class ProcessingPipeline(ABC):
    """Interface para pipeline de processamento completo."""

    @abstractmethod
    def execute(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa pipeline completo: processamento -> enriquecimento -> persistência.

        Args:
            raw_data: Dados brutos para processar

        Returns:
            Dados finais processados e persistidos

        Raises:
            ProcessingError: Em caso de erro em qualquer etapa
        """
        pass


# Exceções específicas
class DataProcessingError(Exception):
    """Exceção base para erros de processamento de dados."""

    pass


class DataEnrichmentError(DataProcessingError):
    """Erro no enriquecimento de dados."""

    pass


class DataPersistenceError(DataProcessingError):
    """Erro na persistência de dados."""

    pass


class ProcessingError(DataProcessingError):
    """Erro geral no pipeline de processamento."""

    pass
