from marshmallow import Schema, ValidationError, fields, post_load, pre_load
from marshmallow_sqlalchemy import SQLAlchemySchema

from app.database import db


class BaseSchema(SQLAlchemySchema):
    """Schema base com funcionalidades comuns para todos os schemas"""

    class Meta:
        sqla_session = db.session
        load_instance = True
        include_relationships = True
        include_fk = True


class TimestampMixin:
    """Mixin para campos de timestamp comuns"""

    # Usar fields.DateTime evita depender de Meta.model no momento da declaração
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class ValidationMixin:
    """Mixin com validações comuns"""

    @staticmethod
    def validate_cpf(value):
        """Validação básica de CPF"""
        if not value or len(value) != 11 or not value.isdigit():
            raise ValidationError("CPF deve conter 11 dígitos numéricos")
        return value

    @staticmethod
    def validate_cnpj(value):
        """Validação básica de CNPJ"""
        if value and (len(value) != 14 or not value.isdigit()):
            raise ValidationError("CNPJ deve conter 14 dígitos numéricos")
        return value

    @staticmethod
    def validate_phone(value):
        """Validação básica de telefone"""
        if not value or len(value) != 11 or not value.isdigit():
            raise ValidationError("Telefone deve conter 11 dígitos numéricos")
        return value

    @staticmethod
    def validate_email(value):
        """Validação básica de email"""
        if not value or "@" not in value:
            raise ValidationError("Email deve ter formato válido")
        return value


class FlexibleSchema(BaseSchema, TimestampMixin, ValidationMixin):
    """
    Schema base flexível que se adapta automaticamente ao contexto
    Pode ser usado como base para qualquer model
    """

    def __init__(self, *args, **kwargs):
        # Contexto de uso: 'create', 'update', 'response', 'login'
        self.context = kwargs.pop("context", "response")
        self.required_fields = kwargs.pop("required_fields", [])
        self.sensitive_fields = kwargs.pop("sensitive_fields", [])
        self.optional_fields = kwargs.pop("optional_fields", [])
        self.immutable_fields = kwargs.pop("immutable_fields", [])

        super().__init__(*args, **kwargs)

        # Ajusta validações baseado no contexto
        self._adjust_validation_for_context()

    def _adjust_validation_for_context(self):
        """Ajusta validações baseado no contexto de uso"""

        if self.context == "create":
            # Para criação, campos definidos como obrigatórios são required=True
            for field_name in self.required_fields:
                if field_name in self.fields:
                    self.fields[field_name].required = True

        elif self.context == "update":
            # Para atualização, todos os campos são opcionais
            for field_name in self.fields:
                if field_name not in ["id", "created_at", "updated_at"]:
                    self.fields[field_name].required = False

        elif self.context == "login":
            # Para login, apenas campos de login são obrigatórios
            for field_name in self.fields:
                if field_name not in self.required_fields:
                    self.fields[field_name].required = False
                    self.fields[field_name].load_only = True

        elif self.context == "response":
            # Para resposta, campos sensíveis são dump_only
            for field_name in self.sensitive_fields:
                if field_name in self.fields:
                    self.fields[field_name].dump_only = True

    @pre_load
    def preprocess_data(self, data, **kwargs):
        """Pré-processa dados antes da validação"""
        if self.context == "login":
            # Para login, mantém apenas campos necessários
            return {k: v for k, v in data.items() if k in self.required_fields}

        # Para contexto update, bloquear campos imutáveis
        if self.context == "update" and self.immutable_fields:
            for field in self.immutable_fields:
                if field in data:
                    raise ValidationError({field: [f"Campo '{field}' não pode ser alterado via esta rota"]})

        return data

    @post_load
    def postprocess_data(self, data, **kwargs):
        """Pós-processa dados após validação"""
        # Remove campos vazios para atualização
        if self.context == "update":
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if v is not None}
            # Quando load_instance=True, 'data' pode ser uma instância do modelo
            # Nesses casos, retornamos a instância e deixamos a camada superior extrair os valores
            return data
        return data

    def validate_required_fields(self, data):
        """Validação customizada para campos obrigatórios baseado no contexto"""
        errors = {}

        if self.context == "create":
            for field in self.required_fields:
                if field not in data or not data[field]:
                    errors[field] = [f"{field.title()} é obrigatório"]

        elif self.context == "login":
            for field in self.required_fields:
                if field not in data or not data[field]:
                    errors[field] = [f"{field.title()} é obrigatório"]

        if errors:
            raise ValidationError(errors)

        return data


class ErrorSchema(Schema):
    """Schema para padronização de erros de validação"""

    message = fields.Str(required=True)
    field = fields.Str(required=False)
    value = fields.Raw(required=False)
