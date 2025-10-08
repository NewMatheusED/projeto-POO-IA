from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Union

from flask import Response, jsonify
from marshmallow import ValidationError


class ErrorCode(Enum):
    """Códigos de erro padronizados da aplicação"""

    # Erros de autenticação (1000-1999)
    UNAUTHORIZED = 1000
    INVALID_TOKEN = 1001
    SESSION_EXPIRED = 1002
    INSUFFICIENT_PERMISSIONS = 1003

    # Erros de validação (2000-2999)
    VALIDATION_ERROR = 2000
    INVALID_INPUT = 2001
    MISSING_REQUIRED_FIELD = 2002
    INVALID_FORMAT = 2003

    # Erros de negócio (3000-3999)
    BUSINESS_RULE_VIOLATION = 3000
    RESOURCE_NOT_FOUND = 3001
    RESOURCE_ALREADY_EXISTS = 3002
    OPERATION_NOT_ALLOWED = 3003
    MARKETPLACE_NOT_SUPPORTED = 3100
    MARKETPLACE_ACTION_NOT_SUPPORTED = 3101

    # Erros de sistema (4000-4999)
    INTERNAL_ERROR = 4000
    DATABASE_ERROR = 4001
    EXTERNAL_SERVICE_ERROR = 4002
    TIMEOUT_ERROR = 4003

    # Erros específicos do Mercado Livre (5000-5999)
    ML_API_ERROR = 5000
    ML_RATE_LIMIT = 5001
    ML_INVALID_TOKEN = 5002

    # Erros de pagamento (6000-6999)
    PAYMENT_ERROR = 6000
    INSUFFICIENT_FUNDS = 6001
    PAYMENT_METHOD_INVALID = 6002


@dataclass
class ApiResponse:
    """Estrutura padronizada para respostas da API"""

    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    error_code: Optional[Union[ErrorCode, int]] = None
    error_fields: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte a resposta para dicionário"""
        response = {"success": self.success, "data": self.data}

        if self.message:
            response["message"] = self.message

        if self.error_code:
            response["error_code"] = self.error_code.value if isinstance(self.error_code, ErrorCode) else self.error_code

        # Inclui campos de erro detalhados no topo quando houver
        if self.error_fields is not None:
            response["error_fields"] = self.error_fields

        return response

    def to_json_response(self, status_code: int = 200) -> Response:
        """Converte para resposta JSON do Flask com status code apropriado"""
        return jsonify(self.to_dict()), status_code


class ResponseFormatter:
    """Classe responsável por formatar respostas da API de forma consistente"""

    @staticmethod
    def success(data: Any = None, message: str = "Operação realizada com sucesso") -> ApiResponse:
        """Cria uma resposta de sucesso"""
        return ApiResponse(success=True, data=data, message=message)

    @staticmethod
    def error(message: str, error_code: Union[ErrorCode, int], data: Any = None) -> ApiResponse:
        """Cria uma resposta de erro"""
        return ApiResponse(success=False, data=data, message=message, error_code=error_code)

    @staticmethod
    def validation_error(message: str = "Erro de validação", data: Any = None, error_fields: Optional[Dict[str, Any]] = None) -> ApiResponse:
        """Cria uma resposta de erro de validação"""
        return ApiResponse(success=False, data=data, message=message, error_code=ErrorCode.VALIDATION_ERROR, error_fields=error_fields)

    @staticmethod
    def not_found(message: str = "Recurso não encontrado", data: Any = None) -> ApiResponse:
        """Cria uma resposta de recurso não encontrado"""
        return ResponseFormatter.error(message=message, error_code=ErrorCode.RESOURCE_NOT_FOUND, data=data)

    @staticmethod
    def unauthorized(message: str = "Acesso não autorizado", data: Any = None) -> ApiResponse:
        """Cria uma resposta de acesso não autorizado"""
        return ResponseFormatter.error(message=message, error_code=ErrorCode.UNAUTHORIZED, data=data)

    @staticmethod
    def internal_error(message: str = "Erro interno do servidor", data: Any = None) -> ApiResponse:
        """Cria uma resposta de erro interno"""
        return ResponseFormatter.error(message=message, error_code=ErrorCode.INTERNAL_ERROR, data=data)

    @staticmethod
    def business_error(message: str, data: Any = None) -> ApiResponse:
        """Cria uma resposta de erro de negócio"""
        return ResponseFormatter.error(message=message, error_code=ErrorCode.BUSINESS_RULE_VIOLATION, data=data)


# Funções de conveniência para uso direto
def success_response(data: Any = None, message: str = "Operação realizada com sucesso") -> ApiResponse:
    """Função de conveniência para resposta de sucesso"""
    return ResponseFormatter.success(data, message)


def error_response(message: str, error_code: Union[ErrorCode, int], data: Any = None) -> ApiResponse:
    """Função de conveniência para resposta de erro"""
    return ResponseFormatter.error(message, error_code, data)


def validation_error_fields_response(message: str = "Erro de validação", error_fields: Optional[Dict[str, Any]] = None, data: Any = None) -> ApiResponse:
    """Função de conveniência para erro de validação com campos detalhados no topo.

    Mantém compatibilidade com chamadas existentes.
    """
    return ResponseFormatter.validation_error(message=message, data=data, error_fields=error_fields)


def not_found_response(message: str = "Recurso não encontrado", data: Any = None) -> ApiResponse:
    """Função de conveniência para recurso não encontrado"""
    return ResponseFormatter.not_found(message, data)


def unauthorized_response(message: str = "Acesso não autorizado", data: Any = None) -> ApiResponse:
    """Função de conveniência para acesso não autorizado"""
    return ResponseFormatter.unauthorized(message, data)


def internal_error_response(message: str = "Erro interno do servidor", data: Any = None) -> ApiResponse:
    """Função de conveniência para erro interno"""
    return ResponseFormatter.internal_error(message, data)


def business_error_response(message: str, data: Any = None) -> ApiResponse:
    """Função de conveniência para erro de negócio"""
    return ResponseFormatter.business_error(message, data)


class AppError(Exception):
    """Exceção base da aplicação com código de erro padronizado."""

    def __init__(self, message: str, error_code: ErrorCode):
        super().__init__(message)
        self.message = message
        self.error_code = error_code

    def to_response(self) -> ApiResponse:
        return ApiResponse(success=False, data=None, message=self.message, error_code=self.error_code)


class MarketplaceNotSupportedError(AppError):
    def __init__(self, message: str = "Marketplace não suportado"):
        super().__init__(message=message, error_code=ErrorCode.MARKETPLACE_NOT_SUPPORTED)


class MarketplaceActionNotSupportedError(AppError):
    def __init__(self, message: str = "Ação não suportada para este marketplace"):
        super().__init__(message=message, error_code=ErrorCode.MARKETPLACE_ACTION_NOT_SUPPORTED)


def validation_error_response_fields(error: ValidationError):
    """
    Função auxiliar para formatar erros de validação do Marshmallow
    """
    # Marshmallow já entrega um dict field->list[str] em error.messages
    error_fields = error.messages if isinstance(error.messages, dict) else {"_schema": error.messages}
    return validation_error_fields_response(
        message="Erro de validação",
        error_fields=error_fields,
        data=None,
    ).to_json_response(400)
