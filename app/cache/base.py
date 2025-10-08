"""
Interfaces e classes base para o sistema de cache.

Este módulo define as interfaces e classes abstratas para o sistema de cache,
seguindo os princípios SOLID, especialmente o princípio de Inversão de Dependência.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")  # Tipo genérico para os valores armazenados no cache


class CacheStrategy(Generic[T], ABC):
    """
    Interface para estratégias de cache.

    Esta interface define os métodos que qualquer implementação de cache
    deve fornecer, permitindo a substituição de implementações sem alterar
    o código cliente.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """
        Busca um item do cache.

        Args:
            key: Chave do item no cache

        Returns:
            O valor armazenado ou None se não encontrado
        """
        pass

    @abstractmethod
    def set(self, key: str, value: T, ttl_seconds: int = 3600) -> bool:
        """
        Armazena um item no cache com TTL.

        Args:
            key: Chave para armazenar o item
            value: Valor a ser armazenado
            ttl_seconds: Tempo de vida em segundos

        Returns:
            True se armazenado com sucesso, False caso contrário
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Remove um item do cache.

        Args:
            key: Chave do item a ser removido

        Returns:
            True se removido com sucesso, False caso contrário
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Verifica se uma chave existe no cache.

        Args:
            key: Chave a ser verificada

        Returns:
            True se a chave existe, False caso contrário
        """
        pass

    @abstractmethod
    def get_many(self, keys: List[str]) -> Dict[str, Optional[T]]:
        """
        Busca múltiplos itens do cache em uma única operação.

        Args:
            keys: Lista de chaves a serem buscadas

        Returns:
            Dicionário com as chaves e seus valores (None para chaves não encontradas)
        """
        pass

    @abstractmethod
    def set_many(self, items: Dict[str, T], ttl_seconds: int = 3600) -> bool:
        """
        Armazena múltiplos itens no cache em uma única operação.

        Args:
            items: Dicionário com chaves e valores a serem armazenados
            ttl_seconds: Tempo de vida em segundos (padrão: 1 hora)

        Returns:
            True se todos os itens foram armazenados com sucesso, False caso contrário
        """
        pass

    @abstractmethod
    def delete_many(self, keys: List[str]) -> int:
        """
        Remove múltiplos itens do cache em uma única operação.

        Args:
            keys: Lista de chaves a serem removidas

        Returns:
            Número de chaves removidas com sucesso
        """
        pass

    @abstractmethod
    def get_by_pattern(self, pattern: str) -> Dict[str, T]:
        """
        Busca itens do cache que correspondem a um padrão.

        Args:
            pattern: Padrão de chave (ex: "user:123:*")

        Returns:
            Dicionário com as chaves e seus valores
        """
        pass

    @abstractmethod
    def delete_by_pattern(self, pattern: str) -> int:
        """
        Remove itens do cache que correspondem a um padrão.

        Args:
            pattern: Padrão de chave (ex: "user:123:*")

        Returns:
            Número de chaves removidas
        """
        pass


class Repository(Generic[T], ABC):
    """
    Repositório base com padrão Cache-Aside.

    Esta classe abstrata implementa o padrão Cache-Aside, tentando primeiro
    buscar dados do cache e, em caso de falha, buscando do banco de dados
    e atualizando o cache.
    """

    def __init__(self, cache_strategy: CacheStrategy[T], schema_factory: Optional[Callable] = None):
        """
        Inicializa o repositório com uma estratégia de cache e schema opcional.

        Args:
            cache_strategy: Estratégia de cache a ser utilizada
            schema_factory: Função que retorna um schema para serialização/deserialização
                            dos dados (ex: create_user_response_schema)
        """
        self.cache = cache_strategy
        self.schema_factory = schema_factory
        self.response_schema = schema_factory() if schema_factory else None

    @abstractmethod
    def get_from_database(self, id: str) -> Optional[T]:
        """
        Busca entidade do banco de dados.

        Args:
            id: Identificador da entidade

        Returns:
            Entidade encontrada ou None
        """
        pass

    @abstractmethod
    def save_to_database(self, entity: T) -> T:
        """
        Salva entidade no banco de dados.

        Args:
            entity: Entidade a ser salva

        Returns:
            Entidade salva (possivelmente com IDs atualizados)
        """
        pass

    def parse_id_from_key(self, key: str) -> Optional[str]:
        """
        Extrai o identificador interno a partir de uma chave externa formatada.

        Repositórios concretos devem sobrescrever quando utilizarem chaves externas
        (ex.: "ads:{marketplace_type}:{shop_id}:{entity_id}"). Se não aplicável,
        retorne None, e o método `get` tratará o parâmetro como ID direto.
        """
        return None

    def get(self, id: str) -> Optional[T]:
        """
        Implementação do padrão Cache-Aside.

        Tenta buscar do cache primeiro e, em caso de falha,
        busca do banco de dados e atualiza o cache.

        Args:
            id: Identificador da entidade

        Returns:
            Entidade encontrada ou None
        """
        # Tenta buscar do cache primeiro
        cached_entity = self.cache.get(id)

        # Se não encontrar no cache, tenta interpretar como chave externa
        if cached_entity is None:
            parsed_id = self.parse_id_from_key(id)
            lookup_id = parsed_id if parsed_id else id

            entity = self.get_from_database(lookup_id)

            # Se encontrou no banco, popula o cache sob a MESMA chave consultada
            if entity is not None:
                self.cache.set(id, entity)
                return entity

            return None

        return cached_entity

    def get_many(self, keys: List[str]) -> Dict[str, Optional[T]]:
        """
        Busca múltiplas chaves com fallback e hidratação automática.

        Para cada chave ausente, tenta extrair o ID interno via `parse_id_from_key`
        e reidrata a partir do banco; popula o cache sob a mesma chave consultada.
        """
        if not keys:
            return {}

        values = self.cache.get_many(keys)
        for key, value in list(values.items()):
            if value is not None:
                continue
            parsed_id = self.parse_id_from_key(key)
            lookup_id = parsed_id if parsed_id else key
            entity = self.get_from_database(lookup_id)
            if entity is None:
                values[key] = None
                continue
            self.cache.set(key, entity)
            values[key] = entity
        return values

    # (API mínima) Helpers específicos removidos em favor de get/get_many com hidratação embutida

    def save(self, id: str, entity: T) -> T:
        """
        Salva no banco e atualiza o cache.

        Args:
            id: Identificador da entidade
            entity: Entidade a ser salva

        Returns:
            Entidade salva
        """
        # Salva no banco primeiro
        saved_entity = self.save_to_database(entity)

        # Aplica o schema se disponível
        if self.response_schema:
            serialized_entity = self.response_schema.dump(saved_entity)
            # Atualiza o cache com a versão serializada
            self.cache.set(id, serialized_entity)
            # Hook pós-save para atualizações acopladas (timelines/derivações)
            try:
                self.after_save_update_cache(id, serialized_entity)
            except Exception:
                pass
            return serialized_entity

        # Atualiza o cache com a entidade original
        self.cache.set(id, saved_entity)
        # Hook pós-save
        try:
            self.after_save_update_cache(id, saved_entity)
        except Exception:
            pass

        return saved_entity

    def after_save_update_cache(self, id: str, saved_entity: T) -> None:
        """
        Atualizações acopladas ao save (ex.: timelines e chaves derivadas).

        Repositórios concretos devem sobrescrever quando precisarem atualizar
        SETs de timeline, chaves derivadas e TTLs relacionados.
        """
        return None

    def invalidate(self, id: str) -> bool:
        """
        Invalida o cache para uma entidade.

        Args:
            id: Identificador da entidade

        Returns:
            True se invalidado com sucesso, False caso contrário
        """
        return self.cache.delete(id)

    # Utilitários globais para escrita/atualização de cache em todos os repositórios

    def write_cache_value(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> bool:
        """
        Escreve um valor no cache em uma chave específica.

        Args:
            key: Chave de destino no Redis
            value: Payload a ser armazenado
            ttl_seconds: TTL customizado (opcional)

        Returns:
            True se gravado com sucesso, False caso contrário
        """
        try:
            return self.cache.set(key, value, ttl_seconds or self.cache.default_ttl)  # type: ignore[attr-defined]
        except Exception:
            return False

    def add_reference_to_sets(self, value_key: str, set_keys: List[str], ttl_seconds: Optional[int] = None) -> int:
        """
        Adiciona a referência de uma chave de valor a múltiplos SETs (timelines) e aplica TTL nos SETs.

        Args:
            value_key: Chave do valor (que será referenciada pelos SETs)
            set_keys: Lista de SETs (timelines) onde a referência deve ser adicionada
            ttl_seconds: TTL para os SETs (se None, usa 2x o default)

        Returns:
            Número de SETs atualizados
        """
        updated = 0
        try:
            redis = self.cache.redis  # type: ignore[attr-defined]
            default_ttl = getattr(self.cache, "default_ttl", 3600)  # type: ignore[attr-defined]
            expire_ttl = ttl_seconds if ttl_seconds is not None else int(default_ttl) * 2
            for set_key in set_keys:
                redis.sadd(set_key, value_key)
                redis.expire(set_key, expire_ttl)
                updated += 1
        except Exception:
            return updated
        return updated

    def get_values_by_set(self, set_key: str, fallback_loader: Optional[Callable[[str], Optional[T]]] = None, readd_on_success: bool = True) -> Dict[str, Optional[T]]:
        """
        Resolve um SET de referências retornando um mapa {referencia: valor}, com fallback opcional.

        Args:
            set_key: Chave do SET (timeline)
            fallback_loader: Função que reidrata um item ausente
            readd_on_success: Se True, re-adiciona referências recuperadas ao SET
        """
        try:
            # Reutiliza utilitário da estratégia de cache quando disponível
            resolver = getattr(self.cache, "get_values_by_set", None)  # type: ignore[attr-defined]
            if callable(resolver):
                return resolver(set_key, fallback_loader=fallback_loader, readd_on_success=readd_on_success)
        except Exception:
            pass

        # Fallback mínimo caso a estratégia não implemente o helper
        try:
            redis = self.cache.redis  # type: ignore[attr-defined]
            members = redis.smembers(set_key)
            member_keys = [m.decode("utf-8") if isinstance(m, bytes) else m for m in members]
            if not member_keys:
                return {}
            values_map = self.cache.get_many(member_keys)
            if fallback_loader:
                for k, v in list(values_map.items()):
                    if v is None:
                        recovered = fallback_loader(k)
                        values_map[k] = recovered
                        if readd_on_success and recovered is not None:
                            redis.sadd(set_key, k)
            return values_map
        except Exception:
            return {}

    def apply_schema(self, data: Any, many: bool = False) -> Any:
        """
        Aplica o schema aos dados, se disponível.

        Args:
            data: Dados a serem serializados
            many: Se True, trata data como uma lista de objetos

        Returns:
            Dados serializados ou os dados originais se não houver schema
        """
        if self.response_schema:
            return self.response_schema.dump(data, many=many)
        return data
