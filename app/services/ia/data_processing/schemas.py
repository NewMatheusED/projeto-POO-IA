"""
Schemas de validação para processamento de dados.

Define schemas para validação de entrada e saída do pipeline de processamento.
"""

from marshmallow import Schema, ValidationError, fields, validates_schema


class ProcessingRequestSchema(Schema):
    """Schema para requisições de processamento."""

    # Dados básicos
    content = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)
    variable = fields.Str(load_default=None)

    # Campos específicos da IA (opcional)
    model = fields.Str(load_default=None)
    usage = fields.Dict(load_default=None)
    finish_reason = fields.Str(load_default=None)

    # Metadados opcionais
    confidence = fields.Float(load_default=None, validate=lambda x: x is None or 0.0 <= x <= 1.0)
    sentiment = fields.Str(load_default=None, validate=lambda x: x is None or x in ["positive", "negative", "neutral"])
    category = fields.Str(load_default=None)
    priority = fields.Int(load_default=None, validate=lambda x: x is None or 1 <= x <= 5)

    # Configurações de processamento
    source = fields.Str(load_default="direct", validate=lambda x: x in ["ai", "direct", "auto"])
    variable_key = fields.Str(load_default="variable")
    enable_enrichment = fields.Bool(load_default=True)
    enable_persistence = fields.Bool(load_default=True)

    # Metadados customizados
    metadata = fields.Dict(load_default=None)

    @validates_schema
    def validate_data(self, data, **kwargs):
        """Valida dados da requisição."""
        content = data.get("content", "")
        if len(content.strip()) < 3:
            raise ValidationError("Conteúdo deve ter pelo menos 3 caracteres")


class AIResponseSchema(Schema):
    """Schema para respostas da IA."""

    content = fields.Str(required=True)
    model = fields.Str(required=True)
    usage = fields.Dict(load_default=None)
    finish_reason = fields.Str(load_default=None)


class ProcessedDataSchema(Schema):
    """Schema para dados processados."""

    source = fields.Str(required=True)
    model = fields.Str(required=True)
    raw_content = fields.Str(required=True)
    extracted_data = fields.Dict(required=True)
    metadata = fields.Dict(required=True)

    # Dados opcionais
    usage = fields.Dict(load_default=None)
    enriched_data = fields.Dict(load_default=None)
    record_id = fields.Str(load_default=None)


class EnrichmentConfigSchema(Schema):
    """Schema para configuração de enriquecimento."""

    base_url = fields.Str(required=True)
    endpoint = fields.Str(load_default="/search")
    timeout = fields.Int(load_default=30, validate=lambda x: x > 0)
    headers = fields.Dict(load_default=None)
    params = fields.Dict(load_default=None)
    name = fields.Str(load_default="external_api")


class PersistenceConfigSchema(Schema):
    """Schema para configuração de persistência."""

    type = fields.Str(required=True, validate=lambda x: x in ["database"])
    table_name = fields.Str(load_default="processed_data")
    base_path = fields.Str(load_default="data/processed")
    database_config = fields.Dict(load_default={})


class PipelineConfigSchema(Schema):
    """Schema para configuração do pipeline completo."""

    # Processador
    variable_key = fields.Str(load_default="variable")
    auto_detect_source = fields.Bool(load_default=True)

    # Enriquecedor
    enable_enrichment = fields.Bool(load_default=True)
    enrichment_config = fields.Nested(EnrichmentConfigSchema, load_default=None)

    # Persistidor
    enable_persistence = fields.Bool(load_default=True)
    persistence_config = fields.Nested(PersistenceConfigSchema, load_default=None)


class BatchProcessingRequestSchema(Schema):
    """Schema para processamento em lote."""

    items = fields.List(fields.Nested(ProcessingRequestSchema), required=True, validate=lambda x: len(x) > 0)
    batch_config = fields.Nested(PipelineConfigSchema, load_default=None)

    @validates_schema
    def validate_batch_size(self, data, **kwargs):
        """Valida tamanho do lote."""
        items = data.get("items", [])
        if len(items) > 100:
            raise ValidationError("Lote não pode ter mais de 100 itens")


class ProcessingResponseSchema(Schema):
    """Schema para resposta do processamento."""

    success = fields.Bool(required=True)
    data = fields.Nested(ProcessedDataSchema, load_default=None)
    error = fields.Str(load_default=None)
    processing_time = fields.Float(load_default=None)
    record_id = fields.Str(load_default=None)


class BatchProcessingResponseSchema(Schema):
    """Schema para resposta do processamento em lote."""

    success = fields.Bool(required=True)
    processed_count = fields.Int(required=True)
    failed_count = fields.Int(required=True)
    total_processing_time = fields.Float(load_default=None)
    results = fields.List(fields.Nested(ProcessingResponseSchema), required=True)
    errors = fields.List(fields.Dict(), load_default=None)
