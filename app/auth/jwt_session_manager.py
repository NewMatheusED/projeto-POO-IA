"""
Gerenciador de sessão JWT otimizado.

Esta implementação usa apenas as chaves necessárias no Redis:
1. Blacklist para JTIs revogados (com TTL)
2. Dados de sessão existentes (que já tinham) + JTI integrado

Evita criar chaves extras como user_tokens:{user_id} para reduzir uso do Redis.
"""

import json
import logging
from datetime import datetime

from app.flask_config import Config
from app.utils.redis import get_redis_client

logger = logging.getLogger(__name__)


# Prefixos de chaves Redis para melhor organização
KEY_PREFIX = "auth"
ACCESS_TOKEN_PREFIX = f"{KEY_PREFIX}:access_token"
BLACKLIST_PREFIX = f"{KEY_PREFIX}:revoked:access_token"  # Corrigido para access_token
SESSION_PREFIX = f"{KEY_PREFIX}:session"


def get_active_sessions_by_user_id(user_id) -> list[dict]:
    """
    Retorna a lista de sessões ativas de um usuário pelo user_id.
    Se não houver sessões, retorna uma lista vazia.
    As sessões são salvas no redis com a chave sendo o user_id.
    E tem uma duração de 3 horas
    """
    redis_client = get_redis_client()
    sessions_json = redis_client.get(user_id)
    if sessions_json:
        try:
            return json.loads(sessions_json)
        except Exception as e:
            logger.error(f"Erro ao decodificar sessões do usuário {user_id}: {e}")
            return []
    return []


class OptimizedJWTManager:
    """
    Gerenciador JWT otimizado que usa o mínimo de chaves Redis possível.
    """

    @staticmethod
    def invalidate_user_previous_sessions(user_id: str) -> None:
        """
        Invalida sessões anteriores de um usuário de forma otimizada.

        Args:
            user_id (str): ID do usuário
        """
        try:
            # Buscar sessões existentes
            active_sessions = get_active_sessions_by_user_id(user_id)

            if active_sessions:
                redis_client = get_redis_client()
                tokens_invalidated = 0
                for session in active_sessions:
                    # Se a sessão tem JTI (session_id), adicionar à blacklist
                    jti = session.get("session_id")  # session_id agora é o JTI
                    expires_at = session.get("expires_at")
                    if jti and expires_at:
                        try:
                            # expires_at já é um timestamp
                            remaining_ttl = max(0, int(expires_at - datetime.now().timestamp()))

                            if remaining_ttl > 0:
                                redis_client.setex(f"{BLACKLIST_PREFIX}:{jti}", remaining_ttl, "revoked")
                                tokens_invalidated += 1
                                logger.info(f"Token {jti} adicionado à blacklist com TTL {remaining_ttl}")
                        except ValueError:
                            # Fallback para TTL padrão
                            ttl = int(Config.TOKEN_EXPIRATION.total_seconds())
                            redis_client.setex(f"{BLACKLIST_PREFIX}:{jti}", ttl, "revoked")
                            tokens_invalidated += 1
                            logger.info(f"Token {jti} adicionado à blacklist com TTL padrão {ttl}")

                if tokens_invalidated > 0:
                    logger.info(f"Invalidadas {tokens_invalidated} sessões anteriores do usuário {user_id}")
                else:
                    logger.info(f"Nenhuma sessão anterior encontrada para invalidar do usuário {user_id}")

        except Exception as e:
            logger.error(f"Erro ao invalidar sessões anteriores: {str(e)}")

    @staticmethod
    def is_jwt_blacklisted(jti: str) -> bool:
        """
        Verifica se um JWT está na blacklist.

        Args:
            jti (str): JWT ID

        Returns:
            bool: True se está na blacklist
        """
        try:
            redis_client = get_redis_client()
            is_blacklisted = redis_client.exists(f"{BLACKLIST_PREFIX}:{jti}") > 0
            logger.info(f"Verificando blacklist para JTI {jti}: {'BLACKLISTED' if is_blacklisted else 'VALID'}")
            return is_blacklisted
        except Exception as e:
            logger.error(f"Erro ao verificar blacklist: {str(e)}")
            return False


# Função callback para Flask-JWT-Extended
def check_if_token_revoked(jwt_header, jwt_payload) -> bool:
    """
    Callback para verificar se token foi revogado.

    Args:
        jwt_header: Header do JWT
        jwt_payload: Payload do JWT

    Returns:
        bool: True se revogado
    """
    jti = jwt_payload.get("jti")
    if not jti:
        logger.warning("JWT sem JTI encontrado")
        return False

    token_type = jwt_payload.get("type", "access")
    logger.info(f"Verificando revogação do token tipo {token_type} com JTI: {jti}")

    try:
        redis_client = get_redis_client()
        is_revoked = redis_client.exists(f"{BLACKLIST_PREFIX}:{jti}") > 0

        if is_revoked:
            logger.info(f"Token {jti} está revogado")
        else:
            logger.debug(f"Token {jti} está válido")

        return is_revoked
    except Exception as e:
        logger.error(f"Erro ao verificar revogação do token: {str(e)}")
        return False


# Funções utilitárias para facilitar uso
def invalidate_user_sessions(user_pin: str, master_pin: str = None) -> None:
    """Invalida sessões anteriores de um usuário."""
    # Para compatibilidade, usar user_pin como user_id
    OptimizedJWTManager.invalidate_user_previous_sessions(user_pin)


def revoke_all_user_tokens(user_id: str) -> None:
    """Revoga todos os JWTs de um usuário."""
    OptimizedJWTManager.invalidate_user_previous_sessions(user_id)
