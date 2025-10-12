"""
Modelos para o serviço de votos.

Define estruturas de dados para votação de projetos.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DadosVotacao:
    """Modelo para dados de votação de um projeto."""

    total_votos: int
    votos_favoraveis: int
    votos_contrarios: int
    votos_abstencoes: int
    taxa_aprovacao: float
    status_final: str
    data_votacao: Optional[str] = None
    camara_votacao: Optional[str] = None
    votos_individuais: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "total_votos": self.total_votos,
            "votos_favoraveis": self.votos_favoraveis,
            "votos_contrarios": self.votos_contrarios,
            "votos_abstencoes": self.votos_abstencoes,
            "taxa_aprovacao": self.taxa_aprovacao,
            "status_final": self.status_final,
            "data_votacao": self.data_votacao,
            "camara_votacao": self.camara_votacao,
            "votos_individuais": self.votos_individuais
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DadosVotacao":
        """Cria instância a partir de dicionário."""
        return cls(
            total_votos=data.get("total_votos", 0),
            votos_favoraveis=data.get("votos_favoraveis", 0),
            votos_contrarios=data.get("votos_contrarios", 0),
            votos_abstencoes=data.get("votos_abstencoes", 0),
            taxa_aprovacao=data.get("taxa_aprovacao", 0.0),
            status_final=data.get("status_final", "sem_votos"),
            data_votacao=data.get("data_votacao"),
            camara_votacao=data.get("camara_votacao"),
            votos_individuais=data.get("votos_individuais", [])
        )
