"""
Controller principal para processamento de dados.

Orquestra o fluxo completo de processamento de dados da IA e APIs diretas.
"""

import time
from typing import Any, Dict, List, Optional

from app.services.ia.data_processing.pipeline import DataProcessingPipeline, BatchProcessingPipeline, PipelineFactory
from app.services.ia.data_processing.schemas import (
    ProcessingRequestSchema, ProcessingResponseSchema, BatchProcessingResponseSchema
)
from app.services.ia.data_processing.interfaces import ProcessingError


class DataProcessingController:
    """Controller principal para processamento de dados."""
    
    def __init__(self, pipeline: Optional[DataProcessingPipeline] = None):
        """
        Inicializa o controller.
        
        Args:
            pipeline: Pipeline personalizado (opcional)
        """
        self.pipeline = pipeline or PipelineFactory.create_default_pipeline()
    
    def process_single_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa um único item.
        
        Args:
            data: Dados para processar
            
        Returns:
            Resultado do processamento
            
        Raises:
            ProcessingError: Em caso de erro no processamento
        """
        start_time = time.time()
        
        try:
            # Valida dados de entrada
            schema = ProcessingRequestSchema()
            validated_data = schema.load(data)
            
            # Executa pipeline
            result = self.pipeline.execute(validated_data)
            
            # Calcula tempo de processamento
            processing_time = time.time() - start_time
            
            # Retorna resposta formatada
            return {
                "success": True,
                "data": result,
                "record_id": result.get("record_id"),
                "processing_time": processing_time
            }
            
        except ProcessingError as e:
            processing_time = time.time() - start_time
            return {
                "success": False,
                "error": str(e),
                "processing_time": processing_time
            }
        except Exception as e:
            processing_time = time.time() - start_time
            return {
                "success": False,
                "error": f"Erro inesperado: {str(e)}",
                "processing_time": processing_time
            }
    
    def process_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Processa múltiplos itens em lote.
        
        Args:
            items: Lista de itens para processar
            
        Returns:
            Resultado do processamento em lote
        """
        try:
            # Valida dados de entrada
            batch_schema = BatchProcessingResponseSchema()
            
            # Cria pipeline de lote
            batch_pipeline = BatchProcessingPipeline(self.pipeline)
            
            # Executa processamento em lote
            result = batch_pipeline.execute_batch(items)
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro no processamento em lote: {str(e)}",
                "processed_count": 0,
                "failed_count": len(items)
            }
    
    def process_ai_response(self, ai_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa resposta específica da IA.
        
        Args:
            ai_response: Resposta da IA
            
        Returns:
            Resultado do processamento
        """
        # Cria pipeline específico para IA
        ai_pipeline = PipelineFactory.create_ai_pipeline()
        
        # Processa resposta
        return ai_pipeline.execute(ai_response)
    
    def process_direct_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa dados enviados diretamente.
        
        Args:
            data: Dados diretos
            
        Returns:
            Resultado do processamento
        """
        # Cria pipeline específico para dados diretos
        direct_pipeline = PipelineFactory.create_direct_pipeline()
        
        # Processa dados
        return direct_pipeline.execute(data)
    
    def configure_pipeline(self, config: Dict[str, Any]) -> None:
        """
        Reconfigura o pipeline.
        
        Args:
            config: Nova configuração do pipeline
        """
        self.pipeline = PipelineFactory.create_default_pipeline(config)
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do processamento.
        
        Returns:
            Estatísticas do processamento
        """
        # TODO: Implementar coleta de estatísticas quando necessário
        return {
            "pipeline_type": type(self.pipeline).__name__,
            "config": self.pipeline.config,
            "status": "active"
        }


class ProcessingService:
    """Serviço de processamento com múltiplos controllers."""
    
    def __init__(self):
        """Inicializa o serviço."""
        self.controllers = {
            "default": DataProcessingController(),
            "ai": DataProcessingController(PipelineFactory.create_ai_pipeline()),
            "direct": DataProcessingController(PipelineFactory.create_direct_pipeline())
        }
    
    def process_with_ai_pipeline(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa usando pipeline específico para IA."""
        return self.controllers["ai"].process_single_item(data)
    
    def process_with_direct_pipeline(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa usando pipeline específico para dados diretos."""
        return self.controllers["direct"].process_single_item(data)
    
    def process_auto_detect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa com detecção automática da fonte."""
        return self.controllers["default"].process_single_item(data)
    
    def get_controller(self, type_name: str = "default") -> DataProcessingController:
        """Retorna controller específico."""
        return self.controllers.get(type_name, self.controllers["default"])
