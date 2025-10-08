FROM python:3.12-slim AS production
WORKDIR /app

# Instalar dependências de sistema sem recomendações extras
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        pkg-config \
        default-libmysqlclient-dev \
        gcc \
        tzdata \
        supervisor && \
    rm -rf /var/lib/apt/lists/*

ENV TZ=America/Sao_Paulo \
    PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
    MALLOC_TRIM_THRESHOLD_=131072 \
    MALLOC_MMAP_THRESHOLD_=65536

COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Criar usuário não-root para segurança
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Criar diretórios de logs e definir permissões
RUN mkdir -p /var/log/supervisor /app/logs /app/temp && \
    chown -R appuser:appuser /app

COPY --chown=appuser:appuser . .

# Expor porta
EXPOSE 5000

# Health check
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)" || exit 1

# Comando de execução
CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]