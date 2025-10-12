"""
Módulo de serviços legislativos.

Fornece funcionalidades para análise e processamento de projetos de lei.
"""

# LegislativeController removido para evitar circular import
from app.services.legislative.models import AnaliseProjetoLei, AvaliacaoParametrica, RespostaAnaliseCompleta
from app.services.legislative.service import LegislativeService

__all__ = ["LegislativeService", "AnaliseProjetoLei", "AvaliacaoParametrica", "RespostaAnaliseCompleta"]
