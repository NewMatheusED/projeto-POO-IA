import os
from datetime import timedelta
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Carregando dotenv para variáveis de ambiente
load_dotenv(override=True)

# Declaração de variáveis de ambiente

# Variáveis de ambiente para conexão com o banco de dados
hostname = os.getenv("SQL_HOSTNAME")
database = os.getenv("SQL_DATABASE")
username = os.getenv("SQL_USERNAME")
password = os.getenv("SQL_PASSWORD")


def _build_sqlalchemy_uri() -> str:
    db_host = hostname or ""
    db_name = database or ""
    db_user = username or ""
    db_pass = quote_plus(password or "")

    # Se faltar informação essencial, usa SQLite em memória nos testes/ambientes sem .env
    if not (db_host and db_name and db_user):
        return "sqlite:///:memory:"

    return f"mysql+mysqldb://{db_user}:{db_pass}@{db_host}/{db_name}?charset=utf8mb4&connect_timeout=10"


class Config:

    REDIS_URL = os.getenv("REDIS_URL")

    REDIS_PASS = os.getenv("REDIS_PASSWORD")
    TOKEN_EXPIRATION = timedelta(minutes=15)

    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 1800, "pool_timeout": 30, "pool_size": 30, "max_overflow": 15, "pool_use_lifo": True}

    # URI do banco com fallback seguro para testes
    SQLALCHEMY_DATABASE_URI = _build_sqlalchemy_uri()

    # Desativar modificações de rastreamento para melhorar desempenho
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_AUTO_FLUSH = True

    PRODUCTION = os.getenv("PRODUCTION")

    DEBUG_MODE = True if PRODUCTION == "false" else False

    REDIS_URL = REDIS_URL

    # Desativando completamente o sistema de sessões do Flask
    SESSION_TYPE = None

    # Configurações JWT
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SECURE = True if os.getenv("PRODUCTION") == "true" else False
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_ACCESS_TOKEN_EXPIRES = TOKEN_EXPIRATION
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=3)
    JWT_COOKIE_SAMESITE = "Strict"
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    # Habilitar blacklist para revogação de tokens
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ["access", "refresh"]

    JWT_ACCESS_COOKIE_PATH = "/"
    JWT_ACCESS_COOKIE_NAME = "access_token"
    JWT_REFRESH_COOKIE_PATH = "/"
    JWT_REFRESH_COOKIE_NAME = "refresh_token"
    JWT_COOKIE_HTTPONLY = True
    JWT_COOKIE_DOMAIN = ".senate-tracker.com.br" if os.getenv("PRODUCTION") == "true" else None

    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
    RABBITMQ_PORT = os.getenv("RABBITMQ_PORT")
    RABBITMQ_USER = os.getenv("RABBITMQ_USER")
    RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
    RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST")
