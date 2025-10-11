import json
import logging
from datetime import datetime

from app.auth.jwt_session_manager import get_active_sessions_by_user_id
from app.flask_config import Config
from app.utils.redis import get_redis_client

logger = logging.getLogger(__name__)


def save_session_data(user_data, refresh_token_jti=None, session_id=None, user_agent=None, ip_address=None):
    """
    Salva dados da sessão do usuário no Redis.

    Args:
        user_data (dict): Dados do usuário
        refresh_token_jti (str): JTI do refresh token
        session_id (str): ID da sessão (JTI do access token)
        user_agent (str): User agent da requisição
        ip_address (str): Endereço IP da requisição
    """
    logger.info(f"user_data: {user_data}")
    redis_client = get_redis_client()

    # Usar user_id como chave principal
    user_id = str(user_data.get("id", user_data.get("pin")))

    existing_sessions = redis_client.get(user_id)
    sessions_list = []

    if existing_sessions:
        sessions_list = json.loads(existing_sessions)
        logger.info(f"Sessões existentes do usuário: {sessions_list}")

        # Remover sessões antigas do mesmo usuário
        sessions_list = [session for session in sessions_list if session.get("id") != user_data.get("id")]

    # Preparar dados da sessão
    session_data = {
        "id": user_data.get("id"),
        "email": user_data.get("email"),
        "name": user_data.get("name"),
        "refresh_token_jti": refresh_token_jti,
        "session_id": session_id,
        "user_agent": user_agent,
        "ip_address": ip_address,
        "expires_at": (datetime.now() + Config.TOKEN_EXPIRATION).timestamp(),
    }

    sessions_list.append(session_data)
    logger.info(f"sessions_list: {sessions_list}")

    # Salvar no Redis com TTL
    redis_client.set(user_id, json.dumps(sessions_list), ex=int(Config.TOKEN_EXPIRATION.total_seconds()))


def remove_single_user_session_by_user_id_hash(user_id, session_id):
    """
    Remove uma sessão específica de um usuário pelo user_id.

    Args:
        user_id (str): ID do usuário
        session_id (str): ID da sessão a ser removida

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        redis_client = get_redis_client()
        active_sessions = get_active_sessions_by_user_id(user_id)

        if not active_sessions:
            return True, f"Nenhuma sessão ativa encontrada para o usuário {user_id}"

        # Filtrar sessões, removendo a sessão especificada
        updated_sessions = []
        session_removed = False

        for session in active_sessions:
            if session.get("session_id") != session_id:
                updated_sessions.append(session)
            else:
                session_removed = True

        if session_removed:
            # Salvar sessões atualizadas
            if updated_sessions:
                redis_client.set(user_id, json.dumps(updated_sessions), ex=int(Config.TOKEN_EXPIRATION.total_seconds()))
            else:
                # Se não há mais sessões, remover a chave
                redis_client.delete(user_id)

            logger.info(f"Sessão {session_id} removida com sucesso para o usuário {user_id}")
            return True, "Sessão removida com sucesso"
        else:
            return False, f"Sessão {session_id} não encontrada para o usuário {user_id}"

    except Exception as e:
        logger.error(f"Erro ao remover sessão do usuário {user_id}: {str(e)}")
        return False, f"Erro ao remover sessão: {str(e)}"
