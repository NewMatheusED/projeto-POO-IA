"""
Rate Limiter para APIs externas.

Implementa controle de taxa de requisições para evitar bloqueios por excesso de chamadas.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional


class HttpMethod(Enum):
    """Enum para métodos HTTP."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

    @classmethod
    def from_string(cls, method: str) -> "HttpMethod":
        """Converte string para enum HttpMethod."""
        try:
            return cls[method.upper()]
        except KeyError:
            return cls.GET  # Método padrão se não reconhecido


@dataclass
class RateLimitConfig:
    """Configuração para rate limiting."""

    # Número máximo de requisições permitidas no período por método HTTP
    max_requests: Dict[HttpMethod, int] = field(default_factory=dict)

    # Período de tempo em segundos por método HTTP
    time_window: Dict[HttpMethod, int] = field(default_factory=dict)

    # Tempo de espera em segundos quando o limite é atingido por método HTTP
    wait_time: Dict[HttpMethod, int] = field(default_factory=dict)

    # Se True, bloqueia a thread quando o limite é atingido; se False, lança exceção
    block_on_limit: bool = True

    def __post_init__(self):
        """Inicializa valores padrão se não fornecidos."""
        # Valores padrão para todos os métodos
        default_max_requests = 60
        default_time_window = 60
        default_wait_time = 60

        # Garante que todos os métodos HTTP tenham configurações
        for method in HttpMethod:
            if method not in self.max_requests:
                self.max_requests[method] = default_max_requests
            if method not in self.time_window:
                self.time_window[method] = default_time_window
            if method not in self.wait_time:
                self.wait_time[method] = default_wait_time

    @classmethod
    def create_with_defaults(
        cls,
        get_max: int = 60,
        get_window: int = 60,
        get_wait: int = 60,
        post_max: int = 30,
        post_window: int = 60,
        post_wait: int = 120,
        put_max: int = 30,
        put_window: int = 60,
        put_wait: int = 120,
        delete_max: int = 20,
        delete_window: int = 60,
        delete_wait: int = 180,
        block_on_limit: bool = True,
    ) -> "RateLimitConfig":
        """
        Cria uma configuração com valores específicos para cada método HTTP.

        Args:
            get_max: Máximo de requisições GET permitidas no período
            get_window: Período de tempo em segundos para requisições GET
            get_wait: Tempo de espera em segundos quando o limite de GET é atingido
            post_max: Máximo de requisições POST permitidas no período
            post_window: Período de tempo em segundos para requisições POST
            post_wait: Tempo de espera em segundos quando o limite de POST é atingido
            put_max: Máximo de requisições PUT permitidas no período
            put_window: Período de tempo em segundos para requisições PUT
            put_wait: Tempo de espera em segundos quando o limite de PUT é atingido
            delete_max: Máximo de requisições DELETE permitidas no período
            delete_window: Período de tempo em segundos para requisições DELETE
            delete_wait: Tempo de espera em segundos quando o limite de DELETE é atingido
            block_on_limit: Se True, bloqueia a thread quando o limite é atingido

        Returns:
            Configuração de rate limit com valores específicos por método
        """
        max_requests = {
            HttpMethod.GET: get_max,
            HttpMethod.POST: post_max,
            HttpMethod.PUT: put_max,
            HttpMethod.DELETE: delete_max,
            HttpMethod.PATCH: put_max,  # Usa mesmos valores de PUT
            HttpMethod.HEAD: get_max,  # Usa mesmos valores de GET
            HttpMethod.OPTIONS: get_max,  # Usa mesmos valores de GET
        }

        time_window = {
            HttpMethod.GET: get_window,
            HttpMethod.POST: post_window,
            HttpMethod.PUT: put_window,
            HttpMethod.DELETE: delete_window,
            HttpMethod.PATCH: put_window,  # Usa mesmos valores de PUT
            HttpMethod.HEAD: get_window,  # Usa mesmos valores de GET
            HttpMethod.OPTIONS: get_window,  # Usa mesmos valores de GET
        }

        wait_time = {
            HttpMethod.GET: get_wait,
            HttpMethod.POST: post_wait,
            HttpMethod.PUT: put_wait,
            HttpMethod.DELETE: delete_wait,
            HttpMethod.PATCH: put_wait,  # Usa mesmos valores de PUT
            HttpMethod.HEAD: get_wait,  # Usa mesmos valores de GET
            HttpMethod.OPTIONS: get_wait,  # Usa mesmos valores de GET
        }

        return cls(max_requests=max_requests, time_window=time_window, wait_time=wait_time, block_on_limit=block_on_limit)


@dataclass
class RateLimitState:
    """Estado do rate limiter para um token específico."""

    # Lista de timestamps das requisições recentes por método HTTP
    request_timestamps: Dict[HttpMethod, list] = field(default_factory=lambda: {m: [] for m in HttpMethod})

    # Timestamp da última vez que o limite foi atingido por método HTTP
    last_limit_hit: Dict[HttpMethod, Optional[datetime]] = field(default_factory=lambda: {m: None for m in HttpMethod})

    # Se o token está atualmente limitado por método HTTP
    is_limited: Dict[HttpMethod, bool] = field(default_factory=lambda: {m: False for m in HttpMethod})


class RateLimitExceededError(Exception):
    """Exceção lançada quando o limite de requisições é excedido."""

    def __init__(self, retry_after: int, method: HttpMethod):
        self.retry_after = retry_after
        self.method = method
        super().__init__(f"Limite de requisições {method.value} excedido. Tente novamente em {retry_after} segundos.")


class RateLimiter:
    """
    Implementa controle de taxa de requisições para APIs externas.

    Monitora o número de requisições por token e método HTTP, aplicando limites conforme configurado.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        """Retorna a instância única do RateLimiter (Singleton)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Inicializa o rate limiter."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.token_states: Dict[str, RateLimitState] = {}
        self.default_config = RateLimitConfig()
        self.token_configs: Dict[str, RateLimitConfig] = {}

    def configure(self, token_id: str, config: RateLimitConfig) -> None:
        """
        Configura o rate limiter para um token específico.

        Args:
            token_id: Identificador do token (geralmente marketplace_shop_id)
            config: Configuração de rate limiting
        """
        self.token_configs[token_id] = config
        self.logger.info(f"Configurado rate limit para token {token_id}")

        # Log detalhado por método
        for method in HttpMethod:
            self.logger.info(f"  - {method.value}: {config.max_requests[method]} req/{config.time_window[method]}s, " f"espera de {config.wait_time[method]}s")

    def _get_config(self, token_id: str) -> RateLimitConfig:
        """Retorna a configuração para o token especificado ou a configuração padrão."""
        return self.token_configs.get(token_id, self.default_config)

    def _get_state(self, token_id: str) -> RateLimitState:
        """Retorna o estado para o token especificado, criando um novo se necessário."""
        if token_id not in self.token_states:
            self.token_states[token_id] = RateLimitState()
        return self.token_states[token_id]

    def _clean_old_requests(self, state: RateLimitState, config: RateLimitConfig, method: HttpMethod) -> None:
        """Remove timestamps de requisições antigos que estão fora da janela de tempo."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=config.time_window[method])

        # Filtra apenas timestamps dentro da janela de tempo
        state.request_timestamps[method] = [ts for ts in state.request_timestamps[method] if ts > cutoff]

    def _is_rate_limited(self, token_id: str, method: HttpMethod) -> bool:
        """
        Verifica se o token está atualmente limitado para o método específico.

        Args:
            token_id: Identificador do token
            method: Método HTTP a verificar

        Returns:
            True se o token estiver limitado, False caso contrário
        """
        state = self._get_state(token_id)
        config = self._get_config(token_id)

        # Se o token estiver em período de espera para este método
        if state.is_limited[method] and state.last_limit_hit[method]:
            wait_end = state.last_limit_hit[method] + timedelta(seconds=config.wait_time[method])
            if datetime.now() < wait_end:
                # Ainda está no período de espera
                return True
            else:
                # Período de espera terminou
                state.is_limited[method] = False
                state.request_timestamps[method] = []
                return False

        # Limpa requisições antigas
        self._clean_old_requests(state, config, method)

        # Verifica se excedeu o limite
        return len(state.request_timestamps[method]) >= config.max_requests[method]

    def _calculate_wait_time(self, token_id: str, method: HttpMethod) -> int:
        """
        Calcula o tempo de espera restante em segundos para um método específico.

        Args:
            token_id: Identificador do token
            method: Método HTTP

        Returns:
            Tempo de espera em segundos
        """
        state = self._get_state(token_id)
        config = self._get_config(token_id)

        if state.last_limit_hit[method]:
            wait_end = state.last_limit_hit[method] + timedelta(seconds=config.wait_time[method])
            remaining = (wait_end - datetime.now()).total_seconds()
            return max(0, int(remaining))

        # Se não estiver limitado mas estiver próximo do limite
        if state.request_timestamps[method]:
            oldest = min(state.request_timestamps[method])
            reset_time = (oldest + timedelta(seconds=config.time_window[method]) - datetime.now()).total_seconds()
            return max(0, int(reset_time))

        return 0

    def check_and_wait(self, token_id: str, method_str: str) -> None:
        """
        Verifica se o token está limitado para o método especificado e espera se necessário.

        Args:
            token_id: Identificador do token
            method_str: Método HTTP como string (GET, POST, etc.)

        Raises:
            RateLimitExceededError: Se o limite for excedido e block_on_limit=False
        """
        method = HttpMethod.from_string(method_str)
        state = self._get_state(token_id)
        config = self._get_config(token_id)

        # Verifica se está limitado
        if self._is_rate_limited(token_id, method):
            wait_time = self._calculate_wait_time(token_id, method)

            if not config.block_on_limit:
                # Não bloqueia, apenas lança exceção
                raise RateLimitExceededError(wait_time, method)

            # Bloqueia até que o limite seja liberado
            self.logger.warning(f"Rate limit atingido para token {token_id}, método {method.value}. " f"Aguardando {wait_time} segundos.")
            time.sleep(wait_time)

            # Reseta o estado após a espera
            state.is_limited[method] = False
            state.request_timestamps[method] = []

        # Registra a requisição atual
        state.request_timestamps[method].append(datetime.now())

    def register_request(self, token_id: str, method_str: str) -> None:
        """
        Registra uma requisição para o token e método.

        Args:
            token_id: Identificador do token
            method_str: Método HTTP como string (GET, POST, etc.)
        """
        method = HttpMethod.from_string(method_str)
        state = self._get_state(token_id)
        config = self._get_config(token_id)

        # Limpa requisições antigas
        self._clean_old_requests(state, config, method)

        # Adiciona a requisição atual
        state.request_timestamps[method].append(datetime.now())

        # Verifica se atingiu o limite após adicionar esta requisição
        if len(state.request_timestamps[method]) >= config.max_requests[method]:
            state.is_limited[method] = True
            state.last_limit_hit[method] = datetime.now()
            self.logger.warning(f"Rate limit atingido para token {token_id}, método {method.value}. " f"Próximas requisições serão limitadas.")

    def register_limit_hit(self, token_id: str, method_str: str, retry_after: Optional[int] = None) -> None:
        """
        Registra que o limite foi atingido (geralmente chamado quando a API retorna 429).

        Args:
            token_id: Identificador do token
            method_str: Método HTTP como string (GET, POST, etc.)
            retry_after: Tempo sugerido para espera (se fornecido pela API)
        """
        method = HttpMethod.from_string(method_str)
        state = self._get_state(token_id)
        config = self._get_config(token_id)

        state.is_limited[method] = True
        state.last_limit_hit[method] = datetime.now()

        # Se a API forneceu um tempo de espera, usa ele temporariamente para este método
        if retry_after is not None:
            # Cria uma cópia da configuração atual
            new_config = RateLimitConfig()

            # Copia todos os valores da configuração atual
            for m in HttpMethod:
                new_config.max_requests[m] = config.max_requests[m]
                new_config.time_window[m] = config.time_window[m]
                new_config.wait_time[m] = config.wait_time[m]

            # Atualiza apenas o tempo de espera para o método específico
            new_config.wait_time[method] = retry_after
            new_config.block_on_limit = config.block_on_limit

            # Atualiza a configuração do token
            self.token_configs[token_id] = new_config

        self.logger.warning(f"Rate limit atingido para token {token_id}, método {method.value}. " f"Aguardando {retry_after or config.wait_time[method]} segundos antes de novas requisições.")
