
from app.flask_config import Config

bind = "0.0.0.0:5000"

is_prod = Config.PRODUCTION == "true"

# Preload para compartilhar memória entre workers via COW e reduzir uso total
preload_app = True

# Reciclar processos mais frequentemente para economizar RAM
max_requests = 200  # Reciclar mais cedo
max_requests_jitter = 50

# Afinar timeouts e conexões
timeout = 60 if is_prod else 120
graceful_timeout = 30
keepalive = 5

# Seleção por ambiente
if is_prod:
    # Produção otimizada para VPS 1 core + 4GB RAM + 1 worker Celery
    worker_class = "gevent"
    workers = 1  # Apenas 1 worker para não competir com Celery
    threads = 1
    worker_connections = 10
    backlog = 64
else:
    # Desenvolvimento: sync simples
    worker_class = "sync"
    workers = 1  # Também reduzido para desenvolvimento
    threads = 2

# Logs no stdout/stderr para facilitar observabilidade em containers
accesslog = "-"
errorlog = "-"
