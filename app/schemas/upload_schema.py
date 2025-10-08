"""
Schemas para sistema de upload de arquivos.

Define os schemas de validação para upload de arquivos,
seguindo o padrão FlexibleSchema do projeto.
"""

from marshmallow import fields, validate

from app.external.aws.r2.interfaces import FileType
from app.schemas.base_schema import FlexibleSchema


class FileUploadSchema(FlexibleSchema):
    """
    Schema para upload de arquivos.
    """

    filename = fields.Str(validate=validate.Length(min=1, max=255), error_messages={"invalid": "Nome do arquivo deve ter até 255 caracteres"}, required=True)

    content_type = fields.Str(validate=validate.Length(min=1, max=100), error_messages={"invalid": "Tipo de conteúdo deve ter até 100 caracteres"}, required=True)

    file_size = fields.Int(validate=validate.Range(min=1), error_messages={"invalid": "Tamanho do arquivo deve ser positivo"}, required=True)

    folder_path = fields.Str(validate=validate.Length(min=1, max=500), error_messages={"invalid": "Caminho da pasta deve ter até 500 caracteres"}, required=True)

    metadata = fields.Dict(keys=fields.Str(), values=fields.Raw(), allow_none=True, missing=None)

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            required_fields=["filename", "content_type", "file_size", "folder_path"],
            sensitive_fields=[],
            optional_fields=["metadata"],
            **kwargs,
        )


class UploadResultSchema(FlexibleSchema):
    """
    Schema para resultado de upload.
    """

    success = fields.Bool(required=True)
    file_url = fields.Str(allow_none=True, validate=validate.URL(), error_messages={"invalid": "URL do arquivo deve ser válida"})
    file_key = fields.Str(allow_none=True, validate=validate.Length(min=1, max=500), error_messages={"invalid": "Chave do arquivo deve ter até 500 caracteres"})
    file_size = fields.Int(allow_none=True, validate=validate.Range(min=0), error_messages={"invalid": "Tamanho do arquivo deve ser não negativo"})
    content_type = fields.Str(allow_none=True, validate=validate.Length(max=100), error_messages={"invalid": "Tipo de conteúdo deve ter até 100 caracteres"})
    error_message = fields.Str(allow_none=True, validate=validate.Length(max=1000), error_messages={"invalid": "Mensagem de erro deve ter até 1000 caracteres"})
    metadata = fields.Dict(keys=fields.Str(), values=fields.Raw(), allow_none=True)

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            required_fields=["success"],
            sensitive_fields=[],
            optional_fields=["file_url", "file_key", "file_size", "content_type", "error_message", "metadata"],
            **kwargs,
        )


class UploadConfigSchema(FlexibleSchema):
    """
    Schema para configuração de upload.
    """

    folder_path = fields.Str(validate=validate.Length(min=1, max=500), error_messages={"invalid": "Caminho da pasta deve ter até 500 caracteres"}, required=True)

    file_types = fields.List(fields.Enum(FileType), validate=validate.Length(min=1), error_messages={"invalid": "Pelo menos um tipo de arquivo deve ser especificado"}, required=True)

    max_size_mb = fields.Int(validate=validate.Range(min=1, max=1000), error_messages={"invalid": "Tamanho máximo deve estar entre 1 e 1000 MB"}, required=True)

    max_files = fields.Int(validate=validate.Range(min=1, max=50), error_messages={"invalid": "Número máximo de arquivos deve estar entre 1 e 50"}, required=True)

    allowed_extensions = fields.List(fields.Str(validate=validate.Length(min=1, max=10)), allow_none=True, missing=None)

    generate_unique_filename = fields.Bool(missing=True)
    preserve_original_filename = fields.Bool(missing=True)
    add_timestamp = fields.Bool(missing=True)

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            required_fields=["folder_path", "file_types", "max_size_mb", "max_files"],
            sensitive_fields=[],
            optional_fields=["allowed_extensions", "generate_unique_filename", "preserve_original_filename", "add_timestamp"],
            **kwargs,
        )


class BulkUploadSchema(FlexibleSchema):
    """
    Schema para upload em lote.
    """

    files = fields.List(fields.Nested(FileUploadSchema), validate=validate.Length(min=1, max=10), error_messages={"invalid": "Deve conter entre 1 e 10 arquivos"}, required=True)

    config = fields.Nested(UploadConfigSchema, required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            required_fields=["files", "config"],
            sensitive_fields=[],
            optional_fields=[],
            **kwargs,
        )


# Funções de conveniência para FileUpload
def create_file_upload_schema(context="response"):
    return FileUploadSchema(context=context)


def create_file_upload_create_schema():
    return FileUploadSchema(context="create")


# Funções de conveniência para UploadResult
def create_upload_result_schema(context="response"):
    return UploadResultSchema(context=context)


# Funções de conveniência para UploadConfig
def create_upload_config_schema(context="response"):
    return UploadConfigSchema(context=context)


def create_upload_config_create_schema():
    return UploadConfigSchema(context="create")


# Funções de conveniência para BulkUpload
def create_bulk_upload_schema(context="response"):
    return BulkUploadSchema(context=context)


def create_bulk_upload_create_schema():
    return BulkUploadSchema(context="create")
