"""
Serviço de votos do Senate Tracker.

Fornece integração com APIs reais para verificação e obtenção de dados de votação.
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

from app.services.votes.models import DadosVotacao

logger = logging.getLogger(__name__)


class SenateTrackerVotesService:
    """Serviço para verificação e obtenção de dados de votos do Senate Tracker."""

    def __init__(self, api_config: Optional[Dict[str, Any]] = None):
        """
        Inicializa o serviço.

        Args:
            api_config: Configuração da API
        """
        self.api_config = api_config or {}
        self.base_url = self.api_config.get("base_url", "https://api.senate-tracker.com.br")
        self.timeout = self.api_config.get("timeout", 30)
        self.headers = self.api_config.get("headers", {"Content-Type": "application/json", "Accept": "application/json"})
        self.min_votes_threshold = self.api_config.get("min_votes", 1)

        # Cache simples em memória
        self._cache = {}
        self._cache_ttl = self.api_config.get("cache_ttl", 300)  # 5 minutos

    def check_project_has_votes(self, project_id: str) -> bool:
        """
        Verifica se um projeto possui votos registrados.

        Args:
            project_id: Código do projeto (ex: "PLS 49/2015")

        Returns:
            True se tem votos suficientes, False caso contrário
        """
        try:
            # Verifica cache primeiro
            cache_key = f"votes_check_{project_id}"
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]["data"]

            # Busca dados de votos
            votes_data = self._fetch_project_votes(project_id)
            has_votes = votes_data.get("total_votos", 0) >= self.min_votes_threshold

            # Atualiza cache
            self._update_cache(cache_key, has_votes)

            return has_votes

        except Exception as e:
            logger.error(f"Erro ao verificar votos para {project_id}: {str(e)}")
            return False

    def get_project_votes(self, project_id: str) -> Optional[DadosVotacao]:
        """
        Obtém dados completos de votação de um projeto.

        Args:
            project_id: Código do projeto

        Returns:
            DadosVotacao ou None se não encontrado
        """
        try:
            # Verifica cache primeiro
            cache_key = f"votes_data_{project_id}"
            if self._is_cache_valid(cache_key):
                cached_data = self._cache[cache_key]["data"]
                return DadosVotacao(**cached_data) if cached_data else None

            # Busca dados de votos
            votes_data_dict = self._fetch_project_votes(project_id)

            if votes_data_dict and votes_data_dict.get("total_votos", 0) >= self.min_votes_threshold:
                dados_votacao = DadosVotacao(**votes_data_dict)
                # Atualiza cache
                self._update_cache(cache_key, votes_data_dict)
                return dados_votacao
            else:
                # Cache resultado negativo
                self._update_cache(cache_key, None)
                return None

        except Exception as e:
            logger.error(f"Erro ao obter dados de votos para {project_id}: {str(e)}")
            return None

    def _fetch_project_votes(self, project_id: str) -> Dict[str, Any]:
        """
        Busca dados de votos para um projeto específico.

        Args:
            project_id: Código do projeto

        Returns:
            Dados de votos estruturados
        """
        try:
            # Parse do project_id
            sigla, numero, ano = self._parse_project_id(project_id)

            # Monta URL da API
            votes_url = urljoin(self.base_url, "/api/v1/votacoes/search")

            # Parâmetros da requisição
            params = {"sigla": sigla, "numero": numero, "ano": ano}

            logger.info(f"Buscando votos para {project_id} - {params}")

            # Faz requisição com retry
            response = self._make_request_with_retry(votes_url, params)

            if response and isinstance(response, dict):
                # Verifica se a resposta tem a estrutura esperada
                if "data" in response:
                    return self._parse_votes_response(response)
                else:
                    logger.warning(f"Resposta sem estrutura esperada para {project_id}: {response}")
                    return self._empty_votes_response()
            else:
                logger.warning(f"Nenhum voto encontrado para {project_id} (response: {response})")
                return self._empty_votes_response()

        except Exception as e:
            logger.error(f"Erro ao buscar votos para {project_id}: {str(e)}")
            return self._empty_votes_response()

    def _parse_project_id(self, project_id: str) -> tuple[str, str, str]:
        """
        Parse do project_id para extrair sigla, numero e ano.

        Args:
            project_id: Código do projeto (ex: "PLS 49/2015")

        Returns:
            Tupla com (sigla, numero, ano)
        """
        # Regex para extrair sigla, numero e ano
        pattern = r"([A-Z]+)\s+(\d+)/(\d{4})"
        match = re.match(pattern, project_id.strip())

        if match:
            sigla, numero, ano = match.groups()
            return sigla, numero, ano
        else:
            raise ValueError(f"Formato de project_id inválido: {project_id}")

    def _make_request_with_retry(self, url: str, params: Dict[str, Any], max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Faz requisição HTTP com retry automático.

        Args:
            url: URL da requisição
            params: Parâmetros da requisição
            max_retries: Número máximo de tentativas

        Returns:
            Resposta da API ou None em caso de falha
        """
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.info(f"Projeto não encontrado: {params}")
                    return None
                else:
                    logger.warning(f"Status {response.status_code} na tentativa {attempt + 1}")

            except requests.RequestException as e:
                logger.warning(f"Erro na tentativa {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    raise

        return None

    def _parse_votes_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse da resposta da API de votos do Senate Tracker.

        Args:
            response_data: Dados brutos da API

        Returns:
            Dados estruturados de votos
        """
        try:
            data = response_data.get("data", {})
            votes_data = data.get("Votos", {})
            votes_list = votes_data.get("Voto", [])

            if not votes_list:
                return self._empty_votes_response()

            # Conta votos por tipo (baseado na QualidadeVoto)
            favoraveis = 0
            contrarios = 0
            abstencoes = 0

            for vote in votes_list:
                qualidade = vote.get("QualidadeVoto", "").upper()
                if qualidade == "S":  # Sim/Favorável
                    favoraveis += 1
                elif qualidade == "N":  # Não/Contrário
                    contrarios += 1
                elif qualidade in ["A", "O"]:  # Abstenção/Omissão
                    abstencoes += 1

            total = len(votes_list)
            taxa_aprovacao = (favoraveis / total * 100) if total > 0 else 0.0


            return {
                "total_votos": total,
                "votos_favoraveis": favoraveis,
                "votos_contrarios": contrarios,
                "votos_abstencoes": abstencoes,
                "taxa_aprovacao": round(taxa_aprovacao, 2),
                "status_final": "aprovado" if taxa_aprovacao > 50 else "rejeitado",
                "data_votacao": data.get("DataHoraInicioReuniao", "").split("T")[0] if data.get("DataHoraInicioReuniao") else None,
                "camara_votacao": data.get("NomeColegiado", "").lower().replace("comissão", "").replace("de", "").strip(),
                "votos_individuais": votes_list  # Lista completa dos votos individuais
            }

        except Exception as e:
            logger.error(f"Erro ao fazer parse dos dados de votos: {str(e)}")
            return self._empty_votes_response()

    def _empty_votes_response(self) -> Dict[str, Any]:
        """Retorna resposta vazia para projetos sem votos."""
        return {"total_votos": 0, "votos_favoraveis": 0, "votos_contrarios": 0, "votos_abstencoes": 0, "taxa_aprovacao": 0.0, "status_final": "sem_votos", "data_votacao": None, "camara_votacao": None, "votos_individuais": []}

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Verifica se o cache é válido."""
        if cache_key not in self._cache:
            return False

        cache_entry = self._cache[cache_key]
        return time.time() - cache_entry["timestamp"] < self._cache_ttl

    def _update_cache(self, cache_key: str, data: Any) -> None:
        """Atualiza o cache com novos dados."""
        self._cache[cache_key] = {"data": data, "timestamp": time.time()}

        # Limpa cache antigo (simples implementação)
        current_time = time.time()
        expired_keys = [key for key, entry in self._cache.items() if current_time - entry["timestamp"] > self._cache_ttl]

        for key in expired_keys:
            del self._cache[key]

    def batch_check_votes(self, project_ids: List[str]) -> Dict[str, bool]:
        """
        Verifica votos para múltiplos projetos.

        Args:
            project_ids: Lista de códigos de projetos

        Returns:
            Dicionário com resultado para cada projeto
        """
        results = {}
        for project_id in project_ids:
            results[project_id] = self.check_project_has_votes(project_id)
        return results
