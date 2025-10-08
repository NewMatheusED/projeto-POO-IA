import logging
from flask_jwt_extended import create_access_token, decode_token
from sqlalchemy.exc import IntegrityError

from app.utils.context_manager import get_db_session
from app.services.user.models import User, UserStatus
from app.services.user.schema import create_user_registration_schema, create_user_response_schema
from app.auth.jwt_session_manager import invalidate_user_sessions
from app.auth.refresh_token_manager import RefreshTokenManager
from app.flask_config import Config

logger = logging.getLogger(__name__)


class AuthController:
    """Controller simplificado para autenticação de usuários"""
    
    def __init__(self):
        self.registration_schema = create_user_registration_schema()
        self.response_schema = create_user_response_schema()

    def register_user(self, payload: dict):
        """
        Registra um novo usuário no sistema.
        
        Args:
            payload (dict): Dados do usuário (name, email, password)
            
        Returns:
            tuple: (success: bool, message: str, data: dict | None)
        """
        try:
            # Validar dados de entrada
            validated_data = self.registration_schema.load(payload)
            
            with get_db_session(session_label="register-user") as session_db:
                # Verificar se email já existe
                existing_user = session_db.query(User).filter_by(email=validated_data['email']).first()
                if existing_user:
                    return False, "Email já está em uso", None
                
                # Criar novo usuário
                new_user = User(
                    name=validated_data['name'],
                    email=validated_data['email'],
                    status=UserStatus.ACTIVE
                )
                
                # Definir senha com hash
                new_user.set_password(validated_data['password'])
                
                # Salvar no banco
                session_db.add(new_user)
                session_db.commit()
                session_db.refresh(new_user)
                
                # Serializar resposta
                user_data = self.response_schema.dump(new_user)
                
                logger.info(f"Usuário registrado com sucesso: {new_user.email}")
                return True, "Usuário registrado com sucesso", user_data
                
        except IntegrityError as e:
            logger.error(f"Erro de integridade no registro: {e}")
            return False, "Email já está em uso", None
        except Exception as e:
            logger.error(f"Erro ao registrar usuário: {e}")
            return False, "Erro interno ao registrar usuário", None

    def login(self, email: str, password: str):
        """
        Realiza login de um usuário.
        
        Args:
            email (str): Email do usuário
            password (str): Senha do usuário
            
        Returns:
            tuple: (success: bool, message: str | None, data: dict | None)
        """
        try:
            with get_db_session(session_label=f"login-{email}") as session_db:
                # Buscar usuário pelo email
                user = session_db.query(User).filter_by(email=email).first()
                
                if not user:
                    return False, "Credenciais inválidas", None
                
                # Verificar senha
                if not user.check_password(password):
                    return False, "Credenciais inválidas", None
                
                # Verificar se usuário está ativo
                if user.status != UserStatus.ACTIVE:
                    return False, "Usuário inativo", None
                
                # Serializar dados do usuário
                user_data = self.response_schema.dump(user)
                
                logger.info(f"Login realizado com sucesso: {user.email}")
                return True, None, user_data
                
        except Exception as e:
            logger.error(f"Erro ao realizar login: {e}")
            return False, "Erro interno ao realizar login", None

    def refresh_token(self, user_id: str):
        """
        Renova o access token para um usuário.
        
        Args:
            user_id (str): ID do usuário
            
        Returns:
            tuple: (success: bool, message: str | None, data: dict | None)
        """
        try:
            with get_db_session(session_label=f"refresh-{user_id}") as session_db:
                user = session_db.query(User).filter_by(id=user_id).first()
                
                if not user or user.status != UserStatus.ACTIVE:
                    return False, "Usuário não encontrado ou inativo", None
                
                # Criar novo access token
                access_token = create_access_token(
                    identity=str(user.id),
                    expires_delta=Config.TOKEN_EXPIRATION
                )
                
                # Extrair JTI do token
                decoded_token = decode_token(access_token)
                jti = decoded_token["jti"]
                
                # Criar refresh token
                refresh_token = RefreshTokenManager.create_refresh_token_for_user(
                    str(user.id), 
                    {"user_id": user.id, "email": user.email}
                )
                
                # Serializar dados do usuário
                user_data = self.response_schema.dump(user)
                
                return True, None, {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user_data": user_data,
                    "jti": jti
                }
                
        except Exception as e:
            logger.error(f"Erro ao renovar token: {e}")
            return False, "Erro interno ao renovar token", None

    def _create_access_token(self, identity, additional_claims=None, expires_delta=None):
        """Método auxiliar para criar access token"""
        return create_access_token(
            identity=identity,
            additional_claims=additional_claims,
            expires_delta=expires_delta
        )