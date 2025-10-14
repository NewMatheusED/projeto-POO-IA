"""
Processador de dados diretos via API.

Processa dados enviados diretamente via POST, simulando o formato que viria da IA.
"""

from typing import Any, Dict

from app.services.ia.data_processing.ai_processor import AIResponseProcessor
from app.services.ia.data_processing.interfaces import DataProcessingError, DataProcessor


class DirectDataProcessor(DataProcessor):
    """Processa dados enviados diretamente via API."""

    def __init__(self, variable_key: str = "variable"):
        """
        Inicializa o processador.

        Args:
            variable_key: Nome da chave que contém a variável principal
        """
        self.variable_key = variable_key

    def process(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa dados diretos da API.

        Args:
            raw_data: Dados enviados via POST

        Returns:
            Dados estruturados no mesmo formato que viria da IA

        Raises:
            DataProcessingError: Em caso de erro no processamento
        """
        try:
            # Valida dados obrigatórios
            self._validate_required_fields(raw_data)

            # Processa dados diretos
            processed_data = {
                "source": "direct_api",
                "model": "manual_input",
                "raw_content": raw_data.get("content", ""),
                "extracted_data": self._extract_structured_data(raw_data),
                "metadata": {"processing_timestamp": self._get_current_timestamp(), "variable_key": self.variable_key, "input_method": "direct_post"},
            }

            # Adiciona dados específicos se fornecidos
            if "usage" in raw_data:
                processed_data["usage"] = raw_data["usage"]

            if "model" in raw_data:
                processed_data["model"] = raw_data["model"]

            return processed_data

        except Exception as e:
            raise DataProcessingError(f"Erro ao processar dados diretos: {str(e)}")

    def _validate_required_fields(self, data: Dict[str, Any]) -> None:
        """
        Valida campos obrigatórios.

        Args:
            data: Dados para validar

        Raises:
            DataProcessingError: Se campos obrigatórios estão ausentes
        """
        required_fields = ["content"]
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            raise DataProcessingError(f"Campos obrigatórios ausentes: {missing_fields}")

    def _extract_structured_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai dados estruturados dos dados diretos.

        Args:
            data: Dados diretos da API

        Returns:
            Dados estruturados
        """
        extracted = {}

        # Extrai conteúdo principal
        content = data.get("content", "")
        extracted["content"] = content

        # Extrai a variável principal
        if self.variable_key in data:
            extracted[self.variable_key] = data[self.variable_key]
        else:
            # Tenta extrair do conteúdo se não fornecida diretamente
            main_variable = self._extract_main_variable_from_content(content)
            if main_variable:
                extracted[self.variable_key] = main_variable

        # Extrai dados adicionais se fornecidos
        additional_fields = ["confidence", "sentiment", "category", "priority"]
        for field in additional_fields:
            if field in data:
                extracted[field] = data[field]

        # Extrai metadados customizados
        if "metadata" in data:
            extracted["custom_metadata"] = data["metadata"]

        return extracted

    def _extract_main_variable_from_content(self, content: str) -> str:
        """
        Extrai a variável principal do conteúdo.

        Args:
            content: Conteúdo para extrair a variável

        Returns:
            Variável principal extraída
        """
        # Se o conteúdo é simples, usa ele mesmo como variável
        if len(content.strip()) < 100 and "\n" not in content:
            return content.strip()

        # Para conteúdo mais complexo, tenta extrair a primeira informação relevante
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("//"):
                return line

        # Fallback: retorna o conteúdo completo
        return content.strip()

    def _get_current_timestamp(self) -> str:
        """Retorna timestamp atual."""
        from datetime import datetime

        return datetime.now().isoformat()


class HybridProcessor(DataProcessor):
    """Processador híbrido que detecta automaticamente a fonte dos dados."""

    def __init__(self, variable_key: str = "variable"):
        """
        Inicializa o processador híbrido.

        Args:
            variable_key: Nome da chave que contém a variável principal
        """
        self.variable_key = variable_key
        self.ai_processor = AIResponseProcessor(variable_key)
        self.direct_processor = DirectDataProcessor(variable_key)

    def process(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa dados detectando automaticamente a fonte.

        Args:
            raw_data: Dados para processar

        Returns:
            Dados estruturados

        Raises:
            DataProcessingError: Em caso de erro no processamento
        """
        # Detecta a fonte dos dados
        source = self._detect_data_source(raw_data)

        if source == "ai":
            return self.ai_processor.process(raw_data)
        else:
            return self.direct_processor.process(raw_data)

    def _detect_data_source(self, data: Dict[str, Any]) -> str:
        """
        Detecta se os dados vêm da IA ou são diretos.

        Args:
            data: Dados para analisar

        Returns:
            "ai" ou "direct" baseado na estrutura dos dados
        """
        # Se tem campos específicos da IA, é resposta da IA
        ai_indicators = ["choices", "model", "usage", "finish_reason"]
        if any(indicator in data for indicator in ai_indicators):
            return "ai"

        # Se tem campos específicos de dados diretos
        direct_indicators = ["content", "variable"]
        if any(indicator in data for indicator in direct_indicators):
            return "direct"

        # Se não consegue detectar, assume direto
        return "direct"
