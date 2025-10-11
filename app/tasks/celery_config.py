# from datetime import timedelta

from celery import Celery
# from celery.schedules import crontab
from kombu import Exchange, Queue

from app.flask_config import Config

rabbitmq_host = Config.RABBITMQ_HOST
rabbitmq_port = Config.RABBITMQ_PORT
rabbitmq_user = Config.RABBITMQ_USER
rabbitmq_pass = Config.RABBITMQ_PASS
rabbitmq_vhost = Config.RABBITMQ_VHOST


broker_url = f"pyamqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}/{rabbitmq_vhost}"

default_exchange = Exchange("poo_tasks", type="direct")

# Lista única de módulos de tasks (DRY)
TASK_MODULES = [
    "app.tasks",
]

task_queues = (
    Queue("ai_queue", default_exchange, routing_key="ai"),
)

task_routes = {
}

# Configuração de tarefas periódicas
beat_schedule = {
}


def make_celery(app_name=__name__):
    # Configure Celery com RabbitMQ como broker, sem backend de resultados
    celery = Celery(
        app_name,
        broker=broker_url,
        backend=Config.REDIS_URL,
        include=TASK_MODULES,
    )

    # Configurações otimizadas para producer (Flask app)
    celery_config = {
        # Serialização
        "task_serializer": "json",
        "accept_content": ["json"],
        "result_serializer": "json",
        # Configuração de filas e rotas
        "task_queues": task_queues,
        "task_routes": task_routes,
        # Fuso horário e agenda
        "timezone": "America/Sao_Paulo",
        # Mantemos UTC habilitado para consistência de timestamps; o timezone afeta o Beat
        "enable_utc": True,
        # Tarefas periódicas
        "beat_schedule": beat_schedule,
        # Importação explícita de módulos de tasks para registro no worker
        "imports": TASK_MODULES,
        # Não precisamos criar filas automaticamente
        # Permite que o Celery declare filas se ainda não existirem (evita falhas em ambientes limpos)
        "task_create_missing_queues": True,
        # Configurações de producer para garantir entrega confiável
        "task_publish_retry": True,
        "task_publish_retry_policy": {
            "max_retries": 5,
            "interval_start": 0.2,
            "interval_step": 0.5,
            "interval_max": 5.0,
        },
        # metricas importantes para o grafana
        # Eventos e resultados: reduzir overhead por padrão
        "worker_send_task_events": False,
        "task_send_sent_event": False,
        "result_expires": 43200,  # 12 horas
        "task_ignore_result": True,
        # Configurações de heartbeat para detectar falhas na conexão
        # Intervalo um pouco mais agressivo para identificar quedas mais cedo
        "broker_heartbeat": 30,
        "broker_connection_timeout": 30,
        "broker_transport_options": {
            "confirm_publish": True,
            "visibility_timeout": 3600,
        },
        "broker_connection_retry": True,
        "broker_connection_max_retries": 10,
        "task_acks_late": True,
        "worker_prefetch_multiplier": 1,
        "task_reject_on_worker_lost": True,
        "task_acks_on_failure_or_timeout": True,
        # Limites para evitar exceder consumer_timeout do RabbitMQ (30 min)
        "task_soft_time_limit": 1400,  # 23m20s
        "task_time_limit": 1500,  # 25m
        # Otimizações para desempenho de envio
        "broker_pool_limit": 10,
    }

    celery.conf.update(celery_config)

    return celery


celery_app = make_celery("poo_tasks")
