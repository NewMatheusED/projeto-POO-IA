"""
Módulo de serviços de votos.

Fornece funcionalidades para verificação e obtenção de dados de votação.
"""

# Imports diretos para evitar circular import
from app.services.votes.controller import VotesController
from app.services.votes.service import SenateTrackerVotesService

__all__ = ["SenateTrackerVotesService", "VotesController"]
