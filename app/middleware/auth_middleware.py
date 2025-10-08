from flask import g, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from app.utils.responses import ErrorCode, error_response


def restrict_blueprint_to_roles(blueprint, *allowed_roles: str):
    @blueprint.before_request
    def _check_role():
        # Evita verificação dupla quando o pai já autenticou
        # if not getattr(g, "jwt_verified", False):
        #     verify_jwt_in_request()
        role = (get_jwt() or {}).get("role")
        if role not in allowed_roles:
            api = error_response("Permissões insuficientes", ErrorCode.INSUFFICIENT_PERMISSIONS, None)
            return api.to_json_response(403)


def protect_blueprint_with_jwt_except(blueprint, excluded_blueprints: set[str]):
    normalized = {e.lstrip("/") for e in excluded_blueprints}

    @blueprint.before_request
    def _enforce_jwt():
        name = request.blueprint or ""
        short = name.rsplit(".", 1)[-1] if name else ""
        if name in normalized or short in normalized or name == "health":
            return
        verify_jwt_in_request()
        # Marca que o JWT já foi verificado neste request
        g.jwt_verified = True
