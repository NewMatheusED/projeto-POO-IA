"""
Gerenciador de refresh tokens simplificado.

Esta implementação segue os princípios SOLID e Object Calisthenics para gerenciar
refresh tokens de forma eficiente, utilizando o Redis como armazenamento.

Implementação otimizada para um único token válido por usuário.
"""

import logging
from datetime import datetime

from flask_jwt_extended import create_refresh_token

from app.auth.jwt_session_manager import get_active_sessions_by_user_id
from app.flask_config import Config
from app.utils.redis import get_redis_client

logger = logging.getLogger(__name__)


class RefreshTokenManager:
    """
    Gerenciador de refresh tokens seguindo princípios SOLID.
    Responsabilidade única: gerenciar ciclo de vida dos refresh tokens.

    Esta implementação é otimizada para o caso onde cada usuário
    deve ter apenas um único token válido por vez.
    """

    # Prefixos de chaves Redis para melhor organização
    KEY_PREFIX = "auth"
    BLACKLIST_PREFIX = f"{KEY_PREFIX}:revoked:refresh"

    @staticmethod
    def create_refresh_token_for_user(user_id: str, additional_claims: dict = None):
        """
        Cria um refresh token para o usuário.
        Revoga qualquer token anterior do mesmo usuário.

        Args:
            user_id (str): ID do usuário
            additional_claims (dict): Claims adicionais para o token

        Returns:
            str: Refresh token gerado
        """
        claims = additional_claims or {}
        claims["user_id"] = user_id

        # Criar refresh token com tempo de expiração definido na configuração
        refresh_token = create_refresh_token(
            identity=user_id, 
            additional_claims=claims, 
            expires_delta=Config.JWT_REFRESH_TOKEN_EXPIRES
        )

        # Revogar tokens anteriores via blacklist
        try:
            redis_client = get_redis_client()

            logger.info(f"Revogando refresh tokens anteriores para usuário {user_id}")

            # Buscar sessões ativas
            sessions = get_active_sessions_by_user_id(user_id)
            if sessions:
                for session in sessions:
                    if session.get("refresh_token_jti"):
                        old_jti = session["refresh_token_jti"]
                        # Adicionar à blacklist
                        ttl = int(Config.JWT_REFRESH_TOKEN_EXPIRES.total_seconds())
                        redis_client.setex(f"{RefreshTokenManager.BLACKLIST_PREFIX}:{old_jti}", ttl, "revoked")
                        logger.info(f"Refresh token anterior ({old_jti}) do usuário {user_id} revogado")
                else:
                    logger.info(f"Nenhuma sessão ativa encontrada para revogar do usuário {user_id}")
            else:
                logger.info(f"Nenhuma sessão encontrada no Redis para usuário {user_id}")
        except Exception as e:
            logger.error(f"Erro ao revogar refresh tokens anteriores: {str(e)}")
            # Continuamos mesmo se falhar

        return refresh_token

    @staticmethod
    def is_refresh_token_valid(jti: str, user_id: str, request_ip: str = None) -> bool:
        """
        Verifica se um refresh token é válido.
        Agora usa apenas a blacklist para verificação.

        Args:
            jti (str): JTI do token
            user_id (str): ID do usuário (usado apenas para logging)
            request_ip (str, optional): IP do requisitante (não usado)

        Returns:
            bool: True se o token não estiver na blacklist
        """
        if not jti:
            logger.warning(f"JTI ausente para usuário {user_id}")
            return False

        try:
            redis_client = get_redis_client()
            is_revoked = redis_client.exists(f"{RefreshTokenManager.BLACKLIST_PREFIX}:{jti}") > 0

            if is_revoked:
                logger.info(f"Refresh token {jti} do usuário {user_id} está revogado")
                return False
            else:
                logger.debug(f"Refresh token {jti} do usuário {user_id} é válido")
                return True

        except Exception as e:
            logger.error(f"Erro ao verificar validade do refresh token: {str(e)}")
            return False

    @staticmethod
    def revoke_refresh_token(jti: str, user_id: str) -> bool:
        """
        Revoga um refresh token específico.

        Args:
            jti (str): JTI do token a ser revogado
            user_id (str): ID do usuário (usado apenas para logging)

        Returns:
            bool: True se revogado com sucesso
        """
        if not jti:
            logger.warning(f"JTI ausente para revogação do usuário {user_id}")
            return False

        try:
            redis_client = get_redis_client()
            
            # Adicionar à blacklist com TTL padrão
            ttl = int(Config.JWT_REFRESH_TOKEN_EXPIRES.total_seconds())
            redis_client.setex(f"{RefreshTokenManager.BLACKLIST_PREFIX}:{jti}", ttl, "revoked")
            
            logger.info(f"Refresh token {jti} do usuário {user_id} revogado com sucesso")
            return True

        except Exception as e:
            logger.error(f"Erro ao revogar refresh token {jti} do usuário {user_id}: {str(e)}")
            return False

    @staticmethod
    def revoke_all_user_refresh_tokens(user_id: str, master_pin: str = None) -> bool:
        """
        Revoga todos os refresh tokens de um usuário.

        Args:
            user_id (str): ID do usuário
            master_pin (str, optional): PIN do master (para compatibilidade)

        Returns:
            bool: True se todos os tokens foram revogados
        """
        try:
            redis_client = get_redis_client()

            # Buscar todas as sessões ativas do usuário
            sessions = get_active_sessions_by_user_id(user_id)
            
            if not sessions:
                logger.info(f"Nenhuma sessão encontrada para revogar do usuário {user_id}")
                return True

            tokens_revoked = 0
            for session in sessions:
                refresh_jti = session.get("refresh_token_jti")
                if refresh_jti:
                    ttl = int(Config.JWT_REFRESH_TOKEN_EXPIRES.total_seconds())
                    redis_client.setex(f"{RefreshTokenManager.BLACKLIST_PREFIX}:{refresh_jti}", ttl, "revoked")
                    tokens_revoked += 1
                    logger.info(f"Refresh token {refresh_jti} do usuário {user_id} revogado")

            logger.info(f"Total de {tokens_revoked} refresh tokens revogados para o usuário {user_id}")
            return True

        except Exception as e:
            logger.error(f"Erro ao revogar todos os refresh tokens do usuário {user_id}: {str(e)}")
            return False


# Função utilitária para facilitar uso
def is_refresh_token_blacklisted(jti: str) -> bool:
    """
    Verifica se um refresh token está na blacklist.

    Args:
        jti (str): JWT ID

    Returns:
        bool: True se está na blacklist
    """
    return not RefreshTokenManager.is_refresh_token_valid(jti, "unknown")