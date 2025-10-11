"""
Schemas de validação para o serviço de IA.

Define schemas para validação de entrada e saída de dados.
"""

from typing import Any, Dict

from marshmallow import Schema, ValidationError, fields, validates_schema


class MessageSchema(Schema):
    """Schema para validação de mensagens."""

    role = fields.Str(required=True, validate=lambda x: x in ["system", "user", "assistant"])
    content = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)


class AIRequestSchema(Schema):
    """Schema para validação de requisições de IA."""

    messages = fields.List(fields.Nested(MessageSchema), required=True, validate=lambda x: len(x) > 0)
    temperature = fields.Float(load_default=None, validate=lambda x: x is None or 0.0 <= x <= 2.0)
    top_p = fields.Float(load_default=None, validate=lambda x: x is None or 0.0 <= x <= 1.0)
    max_tokens = fields.Int(load_default=None, validate=lambda x: x is None or x > 0)
    response_format = fields.Str(load_default=None, validate=lambda x: x is None or x in ["text", "json_object"])

    @validates_schema
    def validate_messages(self, data, **kwargs):
        """Valida se há pelo menos uma mensagem do usuário."""
        messages = data.get("messages", [])

        if not messages:
            raise ValidationError("Pelo menos uma mensagem é obrigatória")

        # Verifica se há mensagem do sistema e pelo menos uma do usuário
        # has_system = any(msg.get("role") == "system" for msg in messages)
        has_user = any(msg.get("role") == "user" for msg in messages)

        if not has_user:
            raise ValidationError("Pelo menos uma mensagem do usuário é obrigatória")


class AIResponseSchema(Schema):
    """Schema para validação de respostas de IA."""

    content = fields.Str(required=True)
    model = fields.Str(required=True)
    usage = fields.Dict(load_default=None)
    finish_reason = fields.Str(load_default=None)


class ChatCompletionSchema(Schema):
    """Schema para validação de chat completions."""

    user_message = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)
    system_message = fields.Str(load_default="Você é um assistente útil.")
    temperature = fields.Float(load_default=1.0, validate=lambda x: 0.0 <= x <= 2.0)
    top_p = fields.Float(load_default=1.0, validate=lambda x: 0.0 <= x <= 1.0)
    max_tokens = fields.Int(load_default=None, validate=lambda x: x is None or x > 0)
    response_format = fields.Str(load_default="text", validate=lambda x: x in ["text", "json_object"])
    variables = fields.Dict(load_default=None)

    def load_with_variables(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Carrega dados substituindo variáveis no user_message.

        Args:
            data: Dados da requisição

        Returns:
            Dados processados com variáveis substituídas
        """
        processed_data = data.copy()
        user_message = processed_data.get("user_message", "")
        variables = processed_data.get("variables", {})

        # Substitui variáveis no formato {variavel}
        if variables:
            for key, value in variables.items():
                placeholder = f"{{{key}}}"
                user_message = user_message.replace(placeholder, str(value))

        processed_data["user_message"] = user_message
        return processed_data
