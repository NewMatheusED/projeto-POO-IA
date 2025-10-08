from flask_jwt_extended import JWTManager

from app.auth.jwt_session_manager import check_if_token_revoked
from app.auth.refresh_token_manager import RefreshTokenManager
from app.utils.responses import ErrorCode, error_response


def register_jwt_handlers(jwt: JWTManager) -> None:
    @jwt.token_in_blocklist_loader
    def token_in_blocklist(jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
        token_type = jwt_payload.get("type")

        if token_type == "refresh":
            return RefreshTokenManager.is_refresh_token_blacklisted(jti)
        else:
            return check_if_token_revoked(jwt_header, jwt_payload)

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        token_type = jwt_payload.get("type")
        if token_type == "refresh":
            api = error_response("Refresh token expirado. Faça login novamente.", ErrorCode.SESSION_EXPIRED)
        else:
            api = error_response("Sessão expirada", ErrorCode.SESSION_EXPIRED)
        return api.to_json_response(401)

    @jwt.invalid_token_loader
    def invalid_token(reason: str):
        api = error_response("Token inválido", ErrorCode.INVALID_TOKEN, {"reason": reason})
        return api.to_json_response(401)

    @jwt.unauthorized_loader
    def missing_token(reason: str):
        api = error_response("Autenticação requerida", ErrorCode.UNAUTHORIZED, {"reason": reason})
        return api.to_json_response(401)

    @jwt.revoked_token_loader
    def revoked_token(jwt_header, jwt_payload):
        token_type = jwt_payload.get("type")
        if token_type == "refresh":
            api = error_response("Refresh token revogado. Faça login novamente.", ErrorCode.UNAUTHORIZED)
        else:
            api = error_response("Token revogado", ErrorCode.UNAUTHORIZED)
        return api.to_json_response(401)

    @jwt.needs_fresh_token_loader
    def needs_fresh(jwt_header, jwt_payload):
        api = error_response("Token precisa ser fresh", ErrorCode.UNAUTHORIZED)
        return api.to_json_response(401)
