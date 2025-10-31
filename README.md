## Documentação Técnica — projeto-poo-IA

### Visão geral
API em Flask estruturada com Application Factory, Blueprints versionados e camadas bem definidas para autenticação, IA e processamento de dados. Utiliza JWT em cookies, SQLAlchemy com MySQL (com fallback para SQLite em memória), Marshmallow para validação e Azure AI Inference como provedor de IA.

### Stack técnica
- **Backend**: Flask 3, Blueprints, Application Factory
- **Auth**: Flask-JWT-Extended (cookies HttpOnly), Redis (sessions/refresh management)
- **Banco**: SQLAlchemy + Flask-Migrate, MySQL (driver mysqlclient) — fallback SQLite memória
- **Validação**: Marshmallow (schemas)
- **IA**: Azure AI Inference (`azure-ai-inference`) via cliente próprio
- **Tarefas**: Celery + Redis (fila)
- **CORS**: configurado por ambiente, origins restritas

### Arquitetura e organização
- Application Factory registra extensões e blueprints:
```python
def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources=CORSConfig.get_api_cors_config())
    jwt.init_app(app)
    register_jwt_handlers(jwt)
    init_db(app)
    ma.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(os.path.dirname(__file__), "migrations"))
    from app.api.v1.blueprints import blueprint_v1 as api_v1_bp
    app.register_blueprint(api_v1_bp, url_prefix="/v1")
    return app
```

- Blueprints v1 e proteção por JWT (exceto `auth` e `health`):
```python
blueprint_v1 = Blueprint("v1", __name__)
blueprint_v1.register_blueprint(auth_bp, url_prefix="/auth")
blueprint_v1.register_blueprint(ia_bp, url_prefix="/ia")
blueprint_v1.register_blueprint(processing_bp, url_prefix="/processing")
blueprint_v1.register_blueprint(legislative_bp, url_prefix="/legislative")
blueprint_v1.register_blueprint(health_bp, url_prefix="/health")
protect_blueprint_with_jwt_except(blueprint_v1, {"auth", "health"})
```

- Configurações centrais (DB, JWT, Redis, GITHUB_TOKEN):
```python
class Config:
    REDIS_URL = os.getenv("REDIS_URL")
    # ...
    SQLALCHEMY_DATABASE_URI = _build_sqlalchemy_uri()
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SECURE = True if os.getenv("PRODUCTION") == "true" else False
    JWT_COOKIE_HTTPONLY = True
    JWT_COOKIE_SAMESITE = "Strict"
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
```

### Endpoints principais
- Base path: `/v1`

- Saúde
  - `GET /v1/health` — status da API e datetime

- Autenticação (cookies)
  - `POST /v1/auth/register`
  - `POST /v1/auth/login`
  - `POST /v1/auth/refresh`
  - `POST /v1/auth/logout`
  - `GET /v1/auth/me`

- IA
  - `GET /v1/ia` — health do serviço de IA
  - `POST /v1/ia/chat` — chat completion com validação e substituição de variáveis
  - `POST /v1/ia/complete` — completion com lista de mensagens
  - `GET /v1/ia/models` — lista simples de modelos

Exemplo (handlers IA):
```python
@ia_bp.route("/chat", methods=["POST"])
def chat_completion():
    schema = ChatCompletionSchema()
    data = schema.load_with_variables(request.get_json() or {})
    response = ai_controller.chat_completion(
        user_message=data["user_message"],
        system_message=data.get("system_message", "Você é um assistente útil."),
        temperature=data.get("temperature"),
        top_p=data.get("top_p"),
        max_tokens=data.get("max_tokens"),
        response_format=data.get("response_format", "text"),
        variables=data.get("variables"),
    )
    return success_response(response).to_json_response()
```

- Processamento de dados
  - `POST /v1/processing/process` — pipeline auto/ai/direct com validação e enriquecimento/persistência opcionais
  - `POST /v1/processing/ai/complete` — integra IA + processamento

```python
@processing_bp.route("/ai/complete", methods=["POST"])
def ai_complete_with_processing():
    ai_controller = AIController()
    ai_response = ai_controller.chat_completion(
        user_message=request_data.get("user_message"),
        system_message=request_data.get("system_message", "Você é um assistente útil."),
        variables=request_data.get("variables"),
        response_format=request_data.get("response_format", "text"),
    )
    if request_data.get("process_result", True):
        processing_result = processing_service.process_auto_detect(ai_response)
        return success_response({"ai_response": ai_response, "processing_result": processing_result}).to_json_response()
```

### Lógica de IA (camada de negócio)
- Controller aplica retry com exponential backoff, substituição de variáveis no prompt e delega a um cliente que implementa `AIClient` (DIP):
```python
class AIController:
    def chat_completion(self, user_message: str, system_message: str = "Você é um assistente útil.", ...):
        max_retries = 3
        base_delay = 60
        for attempt in range(max_retries):
            processed = self._process_message_with_variables(user_message, variables)
            messages = [SystemMessage(system_message), UserMessage(processed)]
            response = self._client.complete(messages=messages, ...)
            return response
        raise AIServiceError("Erro inesperado no chat completion")
```

- Cliente Azure: converte mensagens, aplica defaults de config, chama `ChatCompletionsClient.complete` e normaliza a resposta/erros:
```python
def complete(self, messages: List[AIMessage], temperature: Optional[float] = None, ...):
    azure_messages = self._convert_messages_to_azure_format(messages)
    temperature = temperature or self._config.temperature
    # ... monta request_params (model, top_p, max_tokens, response_format)
    response = self._client.complete(**request_params)
    return self._convert_response_to_dict(response)
```

- Validação de entrada (Marshmallow):
```python
class AIRequestSchema(Schema):
    messages = fields.List(fields.Nested(MessageSchema), required=True, validate=lambda x: len(x) > 0)
    temperature = fields.Float(load_default=None, validate=lambda x: x is None or 0.0 <= x <= 2.0)
    response_format = fields.Str(load_default=None, validate=lambda x: x is None or x in ["text", "json_object"])
```

### Segurança
- Proteção global por JWT em cookies HttpOnly; exceções: `auth`, `health`:
```python
def protect_blueprint_with_jwt_except(blueprint, excluded_blueprints: set[str]):
    # ...
    if name in normalized or short in normalized or name == "health":
        return
    verify_jwt_in_request()
```
- CORS restrito por ambiente (`Strict` SameSite; `Secure` em produção)
- Tratamento de rate limit/erros no cliente de IA e mapeamento para respostas padronizadas

### Modelos e persistência
- Base de modelos e `User` como exemplo:
```python
class BaseModel(db.Model):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
```

### Execução local
1) Python 3.10+
2) Criar venv e instalar deps:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
3) Variáveis de ambiente (exemplos mínimos):
```bash
set PRODUCTION=false
set JWT_SECRET_KEY=devsecret
set GITHUB_TOKEN=ghp_...
# Para MySQL (senão usa SQLite em memória)
set SQL_HOSTNAME=localhost
set SQL_DATABASE=pegdb
set SQL_USERNAME=root
set SQL_PASSWORD=senha
```
4) Rodar a API:
```bash
python run.py
# Servirá em http://localhost:5000
```

### SOLID no projeto
- **SRP (Responsabilidade Única)**: `AIController` (regras IA), `AzureAIClient` (integração externa), `schema.py` (validação), `responses.py` (formatação), `CORSConfig` (config CORS)
- **OCP (Aberto/Fechado)**: novas implementações de `AIClient` podem ser adicionadas sem alterar o controller
- **LSP**: qualquer cliente que implemente `AIClient` substitui o Azure com o mesmo contrato
- **ISP**: interfaces mínimas e específicas (`AIClient`, `AIMessage`)
- **DIP**: `AIController` depende da abstração `AIClient` e usa factory para o default

### Object Calisthenics (práticas aplicadas)
- Classes pequenas e focadas; validação isolada em schemas
- Baixa aninhamento e early-returns em handlers
- Tipos ricos (dataclasses para mensagens/respostas de IA)
- Sem acoplamento ao provedor (abstração `AIClient`)

### Próximos passos (sugestões)
- Documentar schemas de resposta detalhados (OpenAPI/Swagger)
- Adicionar testes de integração para endpoints IA e Processing
- Habilitar CSRF para cookies se houver necessidade de uso cross-site controlado
- Observabilidade (logs estruturados/Tracing) e métricas de uso de tokens IA


