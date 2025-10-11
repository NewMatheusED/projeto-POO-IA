import logging

from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required, set_access_cookies, set_refresh_cookies, unset_jwt_cookies
from marshmallow import ValidationError

from app.auth.controller import AuthController
from app.auth.jwt_session_manager import invalidate_user_sessions
from app.auth.refresh_token_manager import RefreshTokenManager
from app.auth.utils import remove_single_user_session_by_user_id_hash, save_session_data
from app.services.user.schema import create_user_login_schema
from app.utils.responses import ErrorCode, error_response, success_response, validation_error_response_fields

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)
controller = AuthController()


@auth_bp.post("/register")
def register():
    """
    Endpoint para registro de novos usuários.
    """
    try:
        data = request.get_json() or {}

        # Usar controller para processar registro
        success, message, user_data = controller.register_user(data)

        if not success:
            return error_response(message=message, error_code=ErrorCode.VALIDATION_ERROR).to_json_response(400)

        # Criar resposta de sucesso
        api_response = success_response(data=user_data, message=message)
        return api_response.to_json_response(201)

    except ValidationError as e:
        return validation_error_response_fields(e).to_json_response(400)
    except Exception as e:
        logger.error(f"Erro no endpoint de registro: {e}")
        return error_response(message="Erro interno no registro", error_code=ErrorCode.INTERNAL_ERROR).to_json_response(500)


@auth_bp.post("/login")
def login():
    """
    Endpoint para login de usuários.
    """
    try:
        data = request.get_json() or {}

        # Usar schema para validação
        login_schema = create_user_login_schema()

        try:
            validated_data = login_schema.load(data)
        except ValidationError as e:
            return validation_error_response_fields(e).to_json_response(400)

        email = validated_data.get("email")
        password = validated_data.get("password")

        # Usar controller para processar login
        success, error_msg, user_data = controller.login(email, password)

        if not success:
            return error_response(message=error_msg, error_code=ErrorCode.UNAUTHORIZED).to_json_response(401)

        # Criar claims para o JWT
        claims = {"user_id": user_data["id"], "email": user_data["email"], "name": user_data["name"]}

        # Invalidar sessões anteriores do usuário
        invalidate_user_sessions(user_pin=str(user_data["id"]), master_pin=str(user_data["id"]))

        # Criar access token JWT
        from app.flask_config import Config

        access_token = controller._create_access_token(identity=str(user_data["id"]), additional_claims=claims, expires_delta=Config.TOKEN_EXPIRATION)

        # Extrair JTI do token
        from flask_jwt_extended import decode_token

        decoded_token = decode_token(access_token)
        jti = decoded_token["jti"]

        # Criar refresh token
        refresh_token = RefreshTokenManager.create_refresh_token_for_user(str(user_data["id"]), claims)

        # Extrair JTI do refresh token
        refresh_token_decoded = decode_token(refresh_token)
        refresh_token_jti = refresh_token_decoded.get("jti", "desconhecido")

        # Salvar dados da sessão no Redis
        save_session_data(user_data=user_data, refresh_token_jti=refresh_token_jti, session_id=jti, user_agent=request.headers.get("User-Agent"), ip_address=request.remote_addr)

        # Criar resposta de sucesso
        api_response = success_response(data=user_data, message="Login realizado com sucesso")

        # Criar resposta HTTP e adicionar cookies
        response, status_code = api_response.to_json_response(200)
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)

        return response, status_code

    except Exception as e:
        logger.error(f"Erro no endpoint de login: {e}")
        return error_response(message="Erro interno no login", error_code=ErrorCode.INTERNAL_ERROR).to_json_response(500)


@auth_bp.post("/refresh")
def refresh_token():
    """
    Endpoint para renovar o access token usando um refresh token válido.
    """
    try:

        @jwt_required(refresh=True)
        def _refresh_token_protected():
            # Obter claims do refresh token
            jwt_claims = get_jwt()
            user_id = jwt_claims.get("user_id")
            jti = jwt_claims.get("jti")

            if not user_id or not jti:
                return error_response(message="Token inválido", error_code=ErrorCode.INVALID_TOKEN).to_json_response(401)

            # Usar controller para processar refresh
            success, error_msg, data = controller.refresh_token(user_id)

            if not success:
                return error_response(message=error_msg, error_code=ErrorCode.UNAUTHORIZED).to_json_response(401)

            # Revogar refresh token atual
            RefreshTokenManager.revoke_refresh_token(jti, user_id)

            # Invalidar sessões anteriores
            invalidate_user_sessions(user_pin=user_id, master_pin=user_id)

            # Salvar dados da sessão
            save_session_data(user_data=data["user_data"], session_id=data["jti"], user_agent=request.headers.get("User-Agent"), ip_address=request.remote_addr)

            # Criar resposta de sucesso
            api_response = success_response(data=data["user_data"], message="Token renovado com sucesso")

            # Criar resposta HTTP e adicionar cookies
            response, status_code = api_response.to_json_response(200)
            set_access_cookies(response, data["access_token"])
            set_refresh_cookies(response, data["refresh_token"])

            return response, status_code

        # Executar função protegida
        return _refresh_token_protected()

    except Exception as e:
        logger.error(f"Erro ao renovar token: {e}")
        return error_response(message="Erro ao renovar token", error_code=ErrorCode.UNAUTHORIZED).to_json_response(401)


@auth_bp.post("/logout")
@jwt_required()
def logout():
    """
    Endpoint para realizar logout.
    """
    try:
        # Obter claims do token
        jwt_claims = get_jwt()
        user_id = jwt_claims.get("user_id")
        jti = jwt_claims.get("jti")

        if user_id:
            # Revogar access token atual
            invalidate_user_sessions(user_pin=user_id, master_pin=user_id)

            # Revogar refresh tokens do usuário
            RefreshTokenManager.revoke_all_user_refresh_tokens(user_id, user_id)

            # Remover sessão específica
            remove_single_user_session_by_user_id_hash(user_id, jti)

        # Criar resposta e remover cookies
        api_response = success_response(message="Logout realizado com sucesso")
        response, _ = api_response.to_json_response(200)
        unset_jwt_cookies(response)

        return response

    except Exception as e:
        logger.error(f"Erro ao realizar logout: {e}")
        return error_response(message="Erro ao realizar logout", error_code=ErrorCode.INTERNAL_ERROR).to_json_response(500)


@auth_bp.get("/me")
@jwt_required()
def get_current_user():
    """
    Endpoint para obter dados do usuário atual.
    """
    try:
        jwt_claims = get_jwt()
        user_id = jwt_claims.get("user_id")

        if not user_id:
            return error_response(message="Token inválido", error_code=ErrorCode.INVALID_TOKEN).to_json_response(401)

        # Buscar dados do usuário
        from app.database import get_db_session
        from app.services.user.models import User

        with get_db_session() as session_db:
            user = session_db.query(User).filter_by(id=user_id).first()

            if not user:
                return error_response(message="Usuário não encontrado", error_code=ErrorCode.NOT_FOUND).to_json_response(404)

            user_data = user.to_dict()

        return success_response(data=user_data, message="Dados do usuário obtidos com sucesso").to_json_response(200)

    except Exception as e:
        logger.error(f"Erro ao obter dados do usuário: {e}")
        return error_response(message="Erro ao obter dados do usuário", error_code=ErrorCode.INTERNAL_ERROR).to_json_response(500)
