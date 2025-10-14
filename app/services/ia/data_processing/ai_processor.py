"""
Processador de dados da IA.

Processa dados vindos da resposta da IA e extrai informações estruturadas.
"""

import json
from typing import Any, Dict, Optional

from app.services.ia.data_processing.interfaces import DataProcessingError, DataProcessor


class AIResponseProcessor(DataProcessor):
    """Processa respostas da IA e extrai dados estruturados."""

    def __init__(self, variable_key: str = "variable"):
        """
        Inicializa o processador.

        Args:
            variable_key: Nome da chave que contém a variável principal
        """
        self.variable_key = variable_key

    def process(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa dados brutos da IA.

        Args:
            raw_data: Resposta bruta da IA

        Returns:
            Dados estruturados extraídos

        Raises:
            DataProcessingError: Em caso de erro no processamento
        """
        try:
            # Extrai conteúdo da resposta da IA
            ai_content = raw_data.get("content", "")
            model = raw_data.get("model", "")

            # Tenta extrair dados estruturados
            processed_data = {
                "source": "ai",
                "model": model,
                "raw_content": ai_content,
                "extracted_data": self._extract_structured_data(ai_content),
                "metadata": {"processing_timestamp": self._get_current_timestamp(), "variable_key": self.variable_key},
            }

            # Adiciona informações de uso se disponíveis
            if "usage" in raw_data:
                processed_data["usage"] = raw_data["usage"]

            return processed_data

        except Exception as e:
            raise DataProcessingError(f"Erro ao processar dados da IA: {str(e)}")

    def _extract_structured_data(self, content: str) -> Dict[str, Any]:
        """
        Extrai dados estruturados do conteúdo da IA.

        Args:
            content: Conteúdo da resposta da IA

        Returns:
            Dados estruturados extraídos
        """
        extracted = {}

        # Tenta extrair como JSON se possível
        json_data = self._try_extract_json(content)
        if json_data:
            extracted.update(json_data)

        # Para análise legislativa, a variável principal vem do contexto externo
        # Não precisa extrair do conteúdo da IA

        # Extrai outras informações relevantes
        extracted.update(self._extract_additional_info(content))

        return extracted

    def _try_extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Tenta extrair JSON do conteúdo."""
        try:
            # Procura por JSON no conteúdo
            start = content.find("{")
            end = content.rfind("}")

            if start != -1 and end != -1 and end > start:
                json_str = content[start : end + 1]
                return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    def _extract_additional_info(self, content: str) -> Dict[str, Any]:
        """Extrai informações adicionais do conteúdo."""
        additional = {}

        # Extrai confiança se mencionada
        if "confiança" in content.lower() or "confidence" in content.lower():
            additional["confidence_mentioned"] = True

        # Extrai sentimentos se mencionados
        sentiment_keywords = ["positivo", "negativo", "neutro", "positive", "negative", "neutral"]
        for keyword in sentiment_keywords:
            if keyword in content.lower():
                additional["sentiment"] = keyword
                break

        return additional

    def _get_current_timestamp(self) -> str:
        """Retorna timestamp atual."""
        from datetime import datetime

        return datetime.now().isoformat()


class AIJsonProcessor(AIResponseProcessor):
    """Processador especializado para respostas JSON da IA."""

    def _extract_structured_data(self, content: str) -> Dict[str, Any]:
        """
        Extrai dados de resposta JSON da IA.

        Args:
            content: Conteúdo JSON da IA

        Returns:
            Dados estruturados do JSON
        """
        # Tenta extrair JSON completo
        json_data = self._try_extract_json(content)
        if json_data:
            return json_data

        # Se não é JSON válido, usa processamento padrão
        return super()._extract_structured_data(content)
