"""
Configuração global para testes.

Este arquivo contém fixtures e configurações compartilhadas
entre todos os testes do projeto.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def _stub_r2_env(monkeypatch):
    """Garante variáveis de ambiente do R2 durante os testes."""
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("R2_ACCOUNT_ID", "test_account")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "test_key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "test_secret")
    monkeypatch.setenv("R2_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("R2_REGION", "auto")
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://test.r2.cloudflarestorage.com")


@pytest.fixture
def mock_redis_client():
    """Fixture para mock do cliente Redis."""
    redis_mock = Mock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = True
    redis_mock.scan_iter.return_value = []
    redis_mock.ttl.return_value = 300
    return redis_mock


@pytest.fixture
def mock_db_session():
    """Fixture para mock de sessão do banco de dados."""
    session_mock = Mock()
    session_mock.query.return_value.filter_by.return_value.first.return_value = None
    session_mock.add.return_value = None
    session_mock.commit.return_value = None
    session_mock.rollback.return_value = None
    return session_mock


@pytest.fixture
def mock_marketplace():
    """Fixture para mock do marketplace MercadoLivre."""
    marketplace_mock = Mock()
    marketplace_mock.authenticate_with_code.return_value = True
    marketplace_mock.get_user_info.return_value = {"id": "12345", "nickname": "test_user", "logo": "https://example.com/logo.jpg"}
    marketplace_mock.get_shipping_preferences.return_value = Mock()
    marketplace_mock.get_shipping_preferences.return_value.data = {"logistics": {"preference": "standard"}}
    marketplace_mock._current_credentials = Mock()
    marketplace_mock._current_credentials.access_token = "access_token_123"
    marketplace_mock._current_credentials.refresh_token = "refresh_token_123"
    marketplace_mock._current_credentials.expires_in = 3600
    return marketplace_mock


@pytest.fixture
def sample_user_data():
    """Fixture com dados de usuário de exemplo."""
    return {
        "pin": "BG_123456",
        "role": "master",
        "name": "Test User",
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now().timestamp() + 3600),
    }


@pytest.fixture
def sample_state_data():
    """Fixture com dados de state parameter de exemplo."""
    return {"pin": "BG_123456", "role": "master", "master_pin": None, "created_at": datetime.now().isoformat()}


@pytest.fixture
def sample_temp_token_data():
    """Fixture com dados de token temporário de exemplo."""
    return {"auth_code": "auth_code_123", "created_at": datetime.now().isoformat(), "status": "pending"}


@pytest.fixture
def mock_flask_app():
    """Fixture para aplicação Flask de teste."""
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["JWT_SECRET_KEY"] = "test-secret-key"
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_ALGORITHM"] = "HS256"
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"

    return app


@pytest.fixture
def mock_jwt_claims():
    """Fixture para claims JWT de exemplo."""
    return {"role": "master", "master_pin": None, "status": "active"}


@pytest.fixture
def mock_jwt_colab_claims():
    """Fixture para claims JWT de colaborador."""
    return {"role": "colab", "master_pin": "BG_MASTER123", "level": 1, "status": "active"}


@pytest.fixture(autouse=True)
def mock_logging():
    """Fixture para mock do sistema de logging."""
    with patch("app.auth.marketplace.meli.logger") as mock_logger:
        yield mock_logger


@pytest.fixture
def mock_config():
    """Fixture para mock das configurações da aplicação."""
    with patch("app.auth.marketplace.meli.Config") as mock_config_class:
        mock_config_class.MELI_CLIENT_ID = "test_app_id"
        mock_config_class.MELI_CLIENT_SECRET = "test_secret_key"
        mock_config_class.MELI_REDIRECT_URI = "http://localhost:5000/callback"
        mock_config_class.TOKEN_EXPIRATION = 3600
        yield mock_config_class
