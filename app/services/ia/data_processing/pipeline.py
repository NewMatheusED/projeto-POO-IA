"""
Pipeline de processamento de dados.

Orquestra o fluxo completo: processamento -> enriquecimento -> persistência.
"""

import time
from typing import Any, Dict, List, Optional

from app.services.ia.data_processing.ai_processor import AIResponseProcessor
from app.services.ia.data_processing.direct_processor import DirectDataProcessor, HybridProcessor
from app.services.ia.data_processing.enricher import ExternalAPIEnricher, VoteEnricher
from app.services.ia.data_processing.interfaces import DataEnricher, DataPersister, DataProcessingError, DataProcessor, ProcessingError, ProcessingPipeline
from app.services.ia.data_processing.persister import DatabasePersister


class DataProcessingPipeline(ProcessingPipeline):
    """Pipeline completo de processamento de dados."""

    def __init__(self, processor: Optional[DataProcessor] = None, enricher: Optional[DataEnricher] = None, persister: Optional[DataPersister] = None, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa o pipeline de processamento.

        Args:
            processor: Processador de dados (opcional)
            enricher: Enriquecedor de dados (opcional)
            persister: Persistidor de dados (opcional)
            config: Configuração do pipeline (opcional)
        """
        self.config = config or {}
        self.processor = processor or self._create_default_processor()
        self.enricher = enricher or self._create_default_enricher()
        self.persister = persister or self._create_default_persister()

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
        start_time = time.time()

        try:
            # Etapa 1: Processamento
            processed_data = self._process_data(raw_data)

            # Etapa 2: Enriquecimento (se habilitado)
            if self.config.get("enable_enrichment", True):
                enriched_data = self._enrich_data(processed_data)
            else:
                enriched_data = processed_data

            # Etapa 3: Persistência (se habilitada)
            if self.config.get("enable_persistence", True):
                final_data = self._persist_data(enriched_data)
            else:
                final_data = enriched_data

            # Adiciona metadados de processamento
            processing_time = time.time() - start_time
            final_data["metadata"]["total_processing_time"] = processing_time
            final_data["metadata"]["pipeline_status"] = "completed"

            return final_data

        except Exception as e:
            processing_time = time.time() - start_time
            error_data = {"error": str(e), "metadata": {"processing_time": processing_time, "pipeline_status": "failed", "error_timestamp": self._get_current_timestamp()}}
            raise ProcessingError(f"Erro no pipeline: {str(e)}", error_data)

    def _process_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Executa etapa de processamento."""
        try:
            return self.processor.process(raw_data)
        except DataProcessingError as e:
            raise ProcessingError(f"Erro no processamento: {str(e)}")

    def _enrich_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Executa etapa de enriquecimento."""
        try:
            return self.enricher.enrich(data)
        except Exception as e:
            # Enriquecimento não é crítico, continua sem enriquecer
            print(f"Erro no enriquecimento (continuando): {str(e)}")
            return data

    def _persist_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Executa etapa de persistência."""
        try:
            return self.persister.save(data)
        except Exception as e:
            raise ProcessingError(f"Erro na persistência: {str(e)}")

    def _create_default_processor(self) -> DataProcessor:
        """Cria processador padrão."""
        variable_key = self.config.get("variable_key", "variable")

        if self.config.get("auto_detect_source", True):
            return HybridProcessor(variable_key)
        else:
            source = self.config.get("source", "direct")
            if source == "ai":
                return AIResponseProcessor(variable_key)
            else:
                return DirectDataProcessor(variable_key)

    def _create_default_enricher(self) -> DataEnricher:
        """Cria enriquecedor padrão."""
        enrichment_config = self.config.get("enrichment_config")

        if enrichment_config:
            return ExternalAPIEnricher(enrichment_config)
        else:
            return VoteEnricher()

    def _create_default_persister(self) -> DataPersister:
        """Cria persistidor padrão."""
        persistence_config = self.config.get("persistence_config", {})
        persistence_type = persistence_config.get("type", "database")

        if persistence_type == "database":
            return DatabasePersister(persistence_config.get("database_config"))
        else:
            return DatabasePersister()

    def _get_current_timestamp(self) -> str:
        """Retorna timestamp atual."""
        from datetime import datetime

        return datetime.now().isoformat()


class BatchProcessingPipeline:
    """Pipeline para processamento em lote."""

    def __init__(self, pipeline: DataProcessingPipeline):
        """
        Inicializa o pipeline de lote.

        Args:
            pipeline: Pipeline individual para processar cada item
        """
        self.pipeline = pipeline

    def execute_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Executa processamento em lote.

        Args:
            items: Lista de itens para processar

        Returns:
            Resultado do processamento em lote
        """
        start_time = time.time()
        results = []
        errors = []
        processed_count = 0
        failed_count = 0

        for i, item in enumerate(items):
            try:
                result = self.pipeline.execute(item)
                results.append({"success": True, "data": result, "record_id": result.get("record_id"), "index": i})
                processed_count += 1

            except ProcessingError as e:
                error_result = {"success": False, "error": str(e), "index": i, "item": item}
                results.append(error_result)
                errors.append(error_result)
                failed_count += 1

        total_time = time.time() - start_time

        return {
            "success": failed_count == 0,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "total_processing_time": total_time,
            "results": results,
            "errors": errors if errors else None,
        }


class PipelineFactory:
    """Factory para criar pipelines de processamento."""

    @staticmethod
    def create_default_pipeline(config: Optional[Dict[str, Any]] = None) -> DataProcessingPipeline:
        """Cria pipeline padrão."""
        return DataProcessingPipeline(config=config)

    @staticmethod
    def create_ai_pipeline(variable_key: str = "variable") -> DataProcessingPipeline:
        """Cria pipeline específico para dados da IA."""
        config = {"source": "ai", "variable_key": variable_key, "auto_detect_source": False}
        return DataProcessingPipeline(config=config)

    @staticmethod
    def create_direct_pipeline(variable_key: str = "variable") -> DataProcessingPipeline:
        """Cria pipeline específico para dados diretos."""
        config = {"source": "direct", "variable_key": variable_key, "auto_detect_source": False}
        return DataProcessingPipeline(config=config)

    @staticmethod
    def create_enriched_pipeline(enrichment_config: Dict[str, Any], variable_key: str = "variable") -> DataProcessingPipeline:
        """Cria pipeline com enriquecimento personalizado."""
        config = {"variable_key": variable_key, "enable_enrichment": True, "enrichment_config": enrichment_config}
        return DataProcessingPipeline(config=config)
