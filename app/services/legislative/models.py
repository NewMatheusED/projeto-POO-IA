"""
Modelos para o serviço legislativo.

Define estruturas de dados e modelos de banco para análise legislativa.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base.models_base import BaseModel
from app.services.ia.interfaces import AIMessage


@dataclass
class AvaliacaoParametrica:
    """Modelo para avaliação paramétrica individual."""

    criterio: str
    nota: int

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {"criterio": self.criterio, "nota": self.nota}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AvaliacaoParametrica":
        """Cria instância a partir de dicionário."""
        return cls(criterio=data["criterio"], nota=data["nota"])


@dataclass
class AnaliseProjetoLei:
    """Modelo para análise completa de um projeto de lei."""

    project_id: str
    nota_media: float
    avaliacoes_parametricas: List[Dict[str, Any]]
    dados_votacao: Optional[Any] = None  # Será DadosVotacao do serviço votes

    # Metadados
    data_analise: Optional[str] = None
    modelo_ia: Optional[str] = None
    tokens_utilizados: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "project_id": self.project_id,
            "avaliacao_parametrica": self.avaliacoes_parametricas,
            "dados_votacao": self.dados_votacao,
            "nota_media": self.nota_media,
            "data_analise": self.data_analise,
            "modelo_ia": self.modelo_ia,
            "tokens_utilizados": self.tokens_utilizados,
        }

    @classmethod
    def from_ai_response(cls, project_id: str, ai_response: Dict[str, Any]) -> "AnaliseProjetoLei":
        """Cria instância a partir da resposta da IA."""
        # Calcula nota média (desconsiderando notas 0 - nulo)
        avaliacoes = ai_response.get("avaliacao_parametrica", [])
        notas_validas = [av.get("nota", 0) for av in avaliacoes if av.get("nota", 0) > 0]
        nota_media = sum(notas_validas) / len(notas_validas) if notas_validas else 0

        # Converte avaliações
        avaliacoes_obj = [AvaliacaoParametrica.from_dict(av) for av in avaliacoes]

        return cls(
            project_id=project_id,
            nota_media=round(nota_media, 2),
            avaliacoes_parametricas=[av.to_dict() for av in avaliacoes_obj],
        )


@dataclass
class RespostaAnaliseCompleta:
    """Modelo para resposta completa de análise."""

    success: bool
    project_id: str
    analise: Optional[AnaliseProjetoLei] = None
    error: Optional[str] = None
    has_votes: Optional[bool] = None
    processing_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "success": self.success,
            "project_id": self.project_id,
            "analise": self.analise.to_dict() if self.analise else None,
            "error": self.error,
            "has_votes": self.has_votes,
            "processing_time": self.processing_time,
        }


# === MODELOS DE BANCO DE DADOS ===


class ProjetoLei(BaseModel):
    """Modelo de banco para projetos de lei."""

    __tablename__ = "projetos_lei"

    codigo_projeto = Column(String(50), nullable=False, unique=True, index=True)
    nota_media = Column(Float, nullable=False, index=True)

    # Relacionamentos
    avaliacoes = relationship("AvaliacaoParametricaDB", back_populates="projeto", cascade="all, delete-orphan")

    # Índices
    __table_args__ = (
        Index("idx_projeto_codigo", "codigo_projeto"),
        Index("idx_projeto_nota", "nota_media"),
        {"extend_existing": True},
    )


class AvaliacaoParametricaDB(BaseModel):
    """Modelo de banco para avaliações paramétricas."""

    __tablename__ = "avaliacoes_parametricas"

    projeto_id = Column(Integer, ForeignKey("projetos_lei.id", ondelete="CASCADE"), nullable=False)
    criterio = Column(String(100), nullable=False, index=True)
    nota = Column(Integer, nullable=False, index=True)

    # Relacionamentos
    projeto = relationship("ProjetoLei", back_populates="avaliacoes")

    # Índices e constraints
    __table_args__ = (
        UniqueConstraint("projeto_id", "criterio", name="unique_projeto_criterio"),
        Index("idx_avaliacao_projeto", "projeto_id"),
        Index("idx_avaliacao_criterio", "criterio"),
        Index("idx_avaliacao_nota", "nota"),
        {"extend_existing": True},
    )


class DadosVotacaoDB(BaseModel):
    """Modelo de banco para dados de votação."""

    __tablename__ = "dados_votacao"

    projeto_id = Column(Integer, ForeignKey("projetos_lei.id", ondelete="CASCADE"), unique=True, nullable=False)
    total_votos = Column(Integer, nullable=False)
    votos_favoraveis = Column(Integer, nullable=False)
    votos_contrarios = Column(Integer, nullable=False)
    votos_abstencoes = Column(Integer, nullable=False)
    taxa_aprovacao = Column(Float, nullable=False)
    status_final = Column(String(50), nullable=False)
    data_votacao = Column(String(20))  # Data como string (ex: "2017-11-29")
    camara_votacao = Column(String(100))

    # Relacionamento
    projeto = relationship("ProjetoLei", backref="dados_votacao_db")
    votos_individuais = relationship("VotoIndividualDB", back_populates="dados_votacao", cascade="all, delete-orphan")

    # Índices
    __table_args__ = (
        Index("idx_votacao_projeto", "projeto_id"),
        Index("idx_votacao_status", "status_final"),
        {"extend_existing": True},
    )

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
            "votos_individuais": [voto.to_dict() for voto in self.votos_individuais]
        }


class VotoIndividualDB(BaseModel):
    """Modelo de banco para votos individuais dos senadores."""

    __tablename__ = "votos_individuais"

    dados_votacao_id = Column(Integer, ForeignKey("dados_votacao.id", ondelete="CASCADE"), nullable=False)
    nome_senador = Column(String(200), nullable=False)
    partido = Column(String(50))
    uf = Column(String(2))
    idade = Column(Integer)
    sexo = Column(String(1))
    qualidade_voto = Column(String(10), nullable=False)  # S, N, A, O

    # Relacionamento
    dados_votacao = relationship("DadosVotacaoDB", back_populates="votos_individuais")

    # Índices
    __table_args__ = (
        Index("idx_voto_dados_votacao", "dados_votacao_id"),
        Index("idx_voto_senador", "nome_senador"),
        Index("idx_voto_qualidade", "qualidade_voto"),
        Index("idx_voto_partido", "partido"),
        Index("idx_voto_uf", "uf"),
        {"extend_existing": True},
    )

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "nome_senador": self.nome_senador,
            "partido": self.partido,
            "uf": self.uf,
            "qualidade_voto": self.qualidade_voto,
        }


class LegislativeMessage(AIMessage):
    """Mensagem específica para análise legislativa."""

    def __init__(self, content: str, role: str = "user"):
        """
        Inicializa mensagem legislativa.

        Args:
            content: Conteúdo da mensagem
            role: Papel da mensagem (user, system, assistant)
        """
        self.content = content
        self.role = role

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {"role": self.role, "content": self.content}
