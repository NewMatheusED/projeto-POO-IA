"""
Utilitário para criar contexto da aplicação Flask para tasks do Celery.

Este módulo fornece funções para criar e gerenciar o contexto da aplicação Flask
dentro de tasks do Celery, que rodam em processos separados.
"""

import logging
from contextlib import contextmanager
from functools import wraps

from app import create_app

logger = logging.getLogger(__name__)

# Cache da instância da aplicação Flask para reutilização
_flask_app = None


def get_flask_app():
    """
    Obtém ou cria uma instância da aplicação Flask.

    Returns:
        Flask: Instância da aplicação Flask
    """
    global _flask_app

    if _flask_app is None:
        logger.info("Criando nova instância da aplicação Flask para tasks do Celery")
        _flask_app = create_app()

    return _flask_app


@contextmanager
def flask_app_context():
    """
    Gerenciador de contexto para criar contexto da aplicação Flask.

    Yields:
        Flask app context: Contexto da aplicação Flask
    """
    app = get_flask_app()
    with app.app_context():
        logger.debug("Contexto da aplicação Flask criado")
        yield
        logger.debug("Contexto da aplicação Flask encerrado")


def with_flask_app_context(func):
    """
    Decorador para executar uma função dentro do contexto da aplicação Flask.

    Args:
        func: Função a ser decorada

    Returns:
        Função decorada
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        with flask_app_context():
            return func(*args, **kwargs)

    return wrapper
