"""
Enriquecedor de dados.

Complementa dados processados com informações de APIs externas.
"""

import requests
from typing import Any, Dict, Optional

from app.services.ia.data_processing.interfaces import DataEnricher, DataEnrichmentError


class ExternalAPIEnricher(DataEnricher):
    """Enriquece dados com informações de APIs externas."""
    
    def __init__(self, api_config: Dict[str, Any]):
        """
        Inicializa o enriquecedor.
        
        Args:
            api_config: Configuração da API externa
        """
        self.api_config = api_config
        self.base_url = api_config.get("base_url", "")
        self.timeout = api_config.get("timeout", 30)
        self.headers = api_config.get("headers", {})
    
    def enrich(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriquece dados com informações externas.
        
        Args:
            data: Dados para enriquecer
            
        Returns:
            Dados enriquecidos
            
        Raises:
            DataEnrichmentError: Em caso de erro no enriquecimento
        """
        try:
            enriched_data = data.copy()
            
            # Extrai a variável principal para enriquecimento
            variable_key = data.get("metadata", {}).get("variable_key", "variable")
            main_variable = data.get("extracted_data", {}).get(variable_key)
            
            if not main_variable:
                raise DataEnrichmentError("Variável principal não encontrada para enriquecimento")
            
            # Enriquece com dados da API externa
            external_data = self._fetch_external_data(main_variable)
            if external_data:
                enriched_data["enriched_data"] = external_data
                enriched_data["metadata"]["enrichment_timestamp"] = self._get_current_timestamp()
                enriched_data["metadata"]["enrichment_source"] = self.api_config.get("name", "external_api")
            
            return enriched_data
            
        except Exception as e:
            raise DataEnrichmentError(f"Erro ao enriquecer dados: {str(e)}")
    
    def _fetch_external_data(self, variable: str) -> Optional[Dict[str, Any]]:
        """
        Busca dados da API externa.
        
        Args:
            variable: Variável para buscar dados
            
        Returns:
            Dados da API externa ou None se não encontrados
        """
        try:
            # Constrói URL da API
            endpoint = self.api_config.get("endpoint", "/search")
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            
            # Prepara parâmetros da requisição
            params = self._build_request_params(variable)
            
            # Faz requisição
            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"API externa retornou status {response.status_code}")
                return None
                
        except requests.RequestException as e:
            print(f"Erro na requisição para API externa: {str(e)}")
            return None
        except Exception as e:
            print(f"Erro inesperado ao buscar dados externos: {str(e)}")
            return None
    
    def _build_request_params(self, variable: str) -> Dict[str, Any]:
        """
        Constrói parâmetros para a requisição.
        
        Args:
            variable: Variável para incluir nos parâmetros
            
        Returns:
            Parâmetros da requisição
        """
        # Parâmetros padrão
        params = {
            "q": variable,
            "limit": 10
        }
        
        # Adiciona parâmetros customizados da configuração
        custom_params = self.api_config.get("params", {})
        params.update(custom_params)
        
        return params
    
    def _get_current_timestamp(self) -> str:
        """Retorna timestamp atual."""
        from datetime import datetime
        return datetime.now().isoformat()


class MockEnricher(DataEnricher):
    """Enriquecedor mock para desenvolvimento e testes."""
    
    def __init__(self, mock_data: Optional[Dict[str, Any]] = None):
        """
        Inicializa o enriquecedor mock.
        
        Args:
            mock_data: Dados mock para retornar
        """
        self.mock_data = mock_data or {
            "external_id": "mock_123",
            "additional_info": "Dados mock para desenvolvimento",
            "confidence_score": 0.95,
            "source": "mock_api"
        }
    
    def enrich(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriquece dados com informações mock.
        
        Args:
            data: Dados para enriquecer
            
        Returns:
            Dados enriquecidos com informações mock
        """
        enriched_data = data.copy()
        
        # Adiciona dados mock
        enriched_data["enriched_data"] = self.mock_data.copy()
        enriched_data["metadata"]["enrichment_timestamp"] = self._get_current_timestamp()
        enriched_data["metadata"]["enrichment_source"] = "mock_api"
        
        return enriched_data
    
    def _get_current_timestamp(self) -> str:
        """Retorna timestamp atual."""
        from datetime import datetime
        return datetime.now().isoformat()


class CompositeEnricher(DataEnricher):
    """Enriquecedor composto que executa múltiplos enriquecedores."""
    
    def __init__(self, enrichers: list[DataEnricher]):
        """
        Inicializa o enriquecedor composto.
        
        Args:
            enrichers: Lista de enriquecedores para executar
        """
        self.enrichers = enrichers
    
    def enrich(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriquece dados usando múltiplos enriquecedores.
        
        Args:
            data: Dados para enriquecer
            
        Returns:
            Dados enriquecidos por todos os enriquecedores
        """
        enriched_data = data.copy()
        
        for enricher in self.enrichers:
            try:
                enriched_data = enricher.enrich(enriched_data)
            except DataEnrichmentError as e:
                print(f"Erro em enriquecedor {type(enricher).__name__}: {str(e)}")
                # Continua com os outros enriquecedores mesmo se um falhar
                continue
        
        return enriched_data
