import re
from marshmallow import Schema, ValidationError, fields, validate
from app.schemas.base_schema import FlexibleSchema
from .models import User, UserStatus


def validate_name(value):
    """Valida nome do usuário"""
    if not value:
        raise ValidationError("O nome não pode estar vazio.")
    
    if len(value.strip()) < 2:
        raise ValidationError("O nome deve ter pelo menos 2 caracteres.")
    
    if len(value) > 255:
        raise ValidationError("O nome deve ter no máximo 255 caracteres.")


def validate_password(value):
    """Valida senha do usuário"""
    if not value:
        raise ValidationError("A senha não pode estar vazia.")
    
    if len(value) < 6:
        raise ValidationError("A senha deve ter pelo menos 6 caracteres.")
    
    if len(value) > 100:
        raise ValidationError("A senha deve ter no máximo 100 caracteres.")


def validate_email(value):
    """Valida email do usuário"""
    if not value:
        raise ValidationError("O email não pode estar vazio.")
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, value):
        raise ValidationError("Email inválido.")


class UserRegistrationSchema(Schema):
    """Schema para registro de usuário"""
    name = fields.Str(
        required=True,
        validate=validate_name,
        error_messages={"required": "Nome é obrigatório", "invalid": "Nome inválido"}
    )
    
    email = fields.Str(
        required=True,
        validate=validate_email,
        error_messages={"required": "Email é obrigatório", "invalid": "Email inválido"}
    )
    
    password = fields.Str(
        required=True,
        validate=validate_password,
        error_messages={"required": "Senha é obrigatória", "invalid": "Senha inválida"}
    )


class UserLoginSchema(Schema):
    """Schema para login de usuário"""
    email = fields.Str(
        required=True,
        validate=validate_email,
        error_messages={"required": "Email é obrigatório", "invalid": "Email inválido"}
    )
    
    password = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=100)],
        error_messages={"required": "Senha é obrigatória"}
    )


class UserSchema(FlexibleSchema):
    """Schema para resposta de usuário"""
    class Meta:
        model = User
        load_instance = True

    id = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)
    email = fields.Str(dump_only=True)
    status = fields.Enum(UserStatus, dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required_fields", [])
        kwargs.setdefault("sensitive_fields", ["id", "created_at", "updated_at"])
        super().__init__(*args, **kwargs)


def create_user_registration_schema():
    """Cria schema de registro de usuário"""
    return UserRegistrationSchema()


def create_user_login_schema():
    """Cria schema de login de usuário"""
    return UserLoginSchema()


def create_user_response_schema():
    """Cria schema de resposta de usuário"""
    return UserSchema()