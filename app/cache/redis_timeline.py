"""
Implementação de cache baseado em Redis com suporte a timeline.

Este módulo implementa o cache utilizando Redis como backend e organizando
os dados em uma estrutura de timeline por usuário/PIN.
"""

import json
import logging
from datetime import timedelta
from typing import Callable, Dict, List, Optional, Set, TypeVar

from app.cache.base import CacheStrategy
from app.cache.config import CacheConfig
from app.utils.redis import get_redis_client

T = TypeVar("T")  # Tipo genérico para os valores armazenados no cache

logger = logging.getLogger(__name__)


class RedisTimelineCache(CacheStrategy[T]):
    """
    Implementação de cache com Redis usando estrutura de timeline.

    Esta classe implementa a interface CacheStrategy utilizando Redis como backend
    e organizando os dados em uma estrutura hierárquica por entidade e marketplace.

    A estrutura de chaves segue o padrão:
    - Dados armazenados externamente: {entity_type}:{marketplace_type}:{marketplace_shop_id}:{entity_id}
    - Timeline do usuário (apenas referências): user:{pin}:{entity_type}:timeline

    Exemplos:
    - ads:mercadolivre:123456:MLB123 -> Dados do anúncio (armazenados externamente)
    - user:BG_123:ads:timeline -> Set com referências às chaves dos anúncios do usuário
    - orders:mercadolivre:123456:ORDER123 -> Dados do pedido (armazenados externamente)
    - user:BG_123:orders:timeline -> Set com referências às chaves dos pedidos do usuário

    Os colaboradores acessam os dados do seu master, compartilhando o mesmo
    cache para garantir consistência de dados.
    """

    def __init__(self, entity_type: str, ttl_seconds: int = None, key_patterns: Dict[str, str] = None):
        """
        Inicializa o cache com o tipo de entidade e TTL padrão.

        Args:
            entity_type: Tipo de entidade (ex: "accounts", "ads", "orders")
            ttl_seconds: Tempo de vida padrão em segundos (usa configuração se None)
            key_patterns: Dicionário com padrões de chaves personalizados
        """
        self.redis = get_redis_client()
        self.entity_type = entity_type
        self.default_ttl = ttl_seconds if ttl_seconds is not None else CacheConfig.get_ttl(entity_type)

        # Define padrões de chaves (usando padrões personalizados se fornecidos)
        self.key_patterns = key_patterns or {"external": f"{entity_type}:{{marketplace_type}}:{{marketplace_shop_id}}:{{entity_id}}", "user_timeline": f"user:{{pin}}:{entity_type}:timeline"}

    def _format_external_key(self, marketplace_type: str, marketplace_shop_id: str, entity_id: str) -> str:
        """Formata a chave externa usando o padrão definido."""
        return self.key_patterns["external"].format(marketplace_type=marketplace_type, marketplace_shop_id=marketplace_shop_id, entity_id=entity_id)

    def _format_user_timeline_key(self, pin: str) -> str:
        """Formata a chave da timeline do usuário usando o padrão definido."""
        return self.key_patterns["user_timeline"].format(pin=pin)

    def _format_key(self, pin: str, entity_id: str, master_pin: Optional[str] = None, marketplace_type: Optional[str] = None, marketplace_shop_id: Optional[str] = None) -> str:
        """
        Formata a chave do Redis conforme a estrutura hierárquica.

        Args:
            pin: PIN do usuário
            entity_id: ID da entidade
            master_pin: PIN do usuário master (se for um colaborador)
            marketplace_type: Tipo de marketplace (ex: "mercadolivre", "shopee")
            marketplace_shop_id: ID da loja no marketplace

        Returns:
            Chave formatada
        """
        # Se for um colaborador, usa o PIN do master
        effective_pin = master_pin if master_pin else pin

        # Caso especial para contas de usuário (accounts)
        if self.entity_type == "accounts":
            # Para uma conta específica
            if marketplace_type and entity_id:
                # Formato: account:{marketplace_type}:{marketplace_shop_id}
                return f"account:{marketplace_type}:{entity_id}"
            elif entity_id:
                # Formato antigo para compatibilidade: account:{marketplace_shop_id}
                return f"account:{entity_id}"
            else:
                # Referência a uma conta específica dentro do usuário
                # Formato: user:{pin}:account:{marketplace_type}:{marketplace_shop_id}
                if marketplace_type and marketplace_shop_id:
                    return f"user:{effective_pin}:account:{marketplace_type}:{marketplace_shop_id}"
                # Lista de contas do usuário não é mais usada como estrutura
                return f"user:{effective_pin}:accounts"

        # Para outros tipos de entidade (ads, orders, etc.)
        if marketplace_type and marketplace_shop_id and entity_id:
            # Chave completa com marketplace para uma entidade específica
            # Formato: {entity_type}:{marketplace_type}:{marketplace_shop_id}:{entity_id}
            return f"{self.entity_type}:{marketplace_type}:{marketplace_shop_id}:{entity_id}"
        elif marketplace_type and marketplace_shop_id:
            # Referência à coleção de entidades de um marketplace
            # Formato: {entity_type}:{marketplace_type}:{marketplace_shop_id}
            return f"{self.entity_type}:{marketplace_type}:{marketplace_shop_id}"
        elif entity_id:
            # Referência a uma entidade específica do usuário (sem marketplace)
            # Formato: user:{pin}:{entity_type}:{entity_id}
            return f"user:{effective_pin}:{self.entity_type}:{entity_id}"
        else:
            # Referência à coleção de entidades do usuário
            # Formato: user:{pin}:{entity_type}
            return f"user:{effective_pin}:{self.entity_type}"

    def _format_timeline_key(self, pin: str, master_pin: Optional[str] = None, marketplace_type: Optional[str] = None, marketplace_shop_id: Optional[str] = None) -> str:
        """
        Formata a chave da timeline para um usuário ou marketplace.

        Args:
            pin: PIN do usuário
            master_pin: PIN do usuário master (se for um colaborador)
            marketplace_type: Tipo de marketplace (ex: "mercadolivre", "shopee")
            marketplace_shop_id: ID da loja no marketplace

        Returns:
            Chave da timeline formatada
        """
        # Se for um colaborador, usa o PIN do master
        effective_pin = master_pin if master_pin else pin

        # Usa o padrão definido para a timeline
        return self._format_user_timeline_key(effective_pin)

    def _parse_key(self, key: str) -> Dict[str, str]:
        """
        Analisa uma chave formatada e extrai seus componentes.

        Args:
            key: Chave formatada

        Returns:
            Dicionário com os componentes da chave
        """
        parts = key.split(":")

        # Formato para usuário: user:{pin}:{entity_type}:{entity_id}
        if parts[0] == "user":
            if len(parts) >= 4 and parts[2] == "account":
                # user:{pin}:account:{marketplace_type}:{marketplace_shop_id}
                return {
                    "pin": parts[1],
                    "entity_type": "accounts",
                    "marketplace_type": parts[3] if len(parts) > 3 else None,
                    "marketplace_shop_id": parts[4] if len(parts) > 4 else None,
                    "entity_id": parts[4] if len(parts) > 4 else None,
                }
            else:
                # user:{pin}:{entity_type}:{entity_id}
                return {"pin": parts[1], "entity_type": parts[2], "entity_id": parts[3] if len(parts) > 3 else None, "marketplace_type": None, "marketplace_shop_id": None}

        # Formato para contas: account:{marketplace_type}:{marketplace_shop_id}
        elif parts[0] == "account":
            if len(parts) >= 3:
                # account:{marketplace_type}:{marketplace_shop_id}
                return {"pin": None, "entity_type": "accounts", "marketplace_type": parts[1], "marketplace_shop_id": parts[2], "entity_id": parts[2]}
            else:
                # account:{marketplace_shop_id} (formato antigo)
                return {"pin": None, "entity_type": "accounts", "marketplace_type": None, "marketplace_shop_id": parts[1], "entity_id": parts[1]}

        # Formato para entidades específicas: {entity_type}:{marketplace_type}:{marketplace_shop_id}:{entity_id}
        else:
            if len(parts) >= 4:
                # {entity_type}:{marketplace_type}:{marketplace_shop_id}:{entity_id}
                return {"pin": None, "entity_type": parts[0], "marketplace_type": parts[1], "marketplace_shop_id": parts[2], "entity_id": parts[3]}
            elif len(parts) == 3:
                # {entity_type}:{marketplace_type}:{marketplace_shop_id}
                return {"pin": None, "entity_type": parts[0], "marketplace_type": parts[1], "marketplace_shop_id": parts[2], "entity_id": None}
            else:
                # Formato desconhecido
                return {
                    "pin": None,
                    "entity_type": parts[0],
                    "marketplace_type": parts[1] if len(parts) > 1 else None,
                    "marketplace_shop_id": parts[2] if len(parts) > 2 else None,
                    "entity_id": parts[3] if len(parts) > 3 else None,
                }

    def get(self, key: str) -> Optional[T]:
        """
        Busca um item do cache.

        Args:
            key: Chave formatada do item

        Returns:
            O valor armazenado ou None se não encontrado
        """
        try:
            data = self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar do cache: {e}")
            return None

    def set(self, key: str, value: T, ttl_seconds: int = None) -> bool:
        """
        Armazena um item no cache com TTL.

        Args:
            key: Chave formatada para armazenar o item
            value: Valor a ser armazenado
            ttl_seconds: Tempo de vida em segundos (usa o padrão se None)

        Returns:
            True se armazenado com sucesso, False caso contrário
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        try:
            # Serializa o valor
            serialized = json.dumps(value)

            # Armazena no Redis com TTL
            result = self.redis.setex(key, timedelta(seconds=ttl), serialized)

            return bool(result)
        except Exception as e:
            logger.error(f"Erro ao armazenar no cache: {e}")
            return False

    def extend_ttl(self, key: str, ttl_seconds: int = None) -> bool:
        """
        Estende o TTL de um item existente no cache.

        Args:
            key: Chave formatada do item
            ttl_seconds: Novo tempo de vida em segundos (usa o padrão se None)

        Returns:
            True se estendido com sucesso, False caso contrário
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        try:
            # Verifica se a chave existe
            if not self.redis.exists(key):
                return False

            # Estende o TTL
            result = self.redis.expire(key, timedelta(seconds=ttl))

            return bool(result)
        except Exception as e:
            logger.error(f"Erro ao estender TTL no cache: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Remove um item do cache.

        Args:
            key: Chave formatada do item a ser removido

        Returns:
            True se removido com sucesso, False caso contrário
        """
        try:
            # Remove o item do Redis
            result = bool(self.redis.delete(key))

            return result
        except Exception as e:
            logger.error(f"Erro ao remover do cache: {e}")
            return False

    def exists(self, key: str) -> bool:
        """
        Verifica se uma chave existe no cache.

        Args:
            key: Chave formatada a ser verificada

        Returns:
            True se a chave existe, False caso contrário
        """
        try:
            return bool(self.redis.exists(key))
        except Exception as e:
            logger.error(f"Erro ao verificar existência no cache: {e}")
            return False

    def get_many(self, keys: List[str]) -> Dict[str, Optional[T]]:
        """
        Busca múltiplos itens do cache em uma única operação.

        Args:
            keys: Lista de chaves formatadas a serem buscadas

        Returns:
            Dicionário com as chaves e seus valores (None para chaves não encontradas)
        """
        try:
            # Usa pipeline para buscar múltiplos valores em uma única operação
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)

            results = pipe.execute()

            # Converte os resultados para o formato esperado
            return {key: json.loads(value) if value else None for key, value in zip(keys, results)}
        except Exception as e:
            logger.error(f"Erro ao buscar múltiplos itens do cache: {e}")
            return {key: None for key in keys}

    def set_many(self, items: Dict[str, T], ttl_seconds: int = None) -> bool:
        """
        Armazena múltiplos itens no cache em uma única operação.

        Args:
            items: Dicionário com chaves formatadas e valores a serem armazenados
            ttl_seconds: Tempo de vida em segundos (usa o padrão se None)

        Returns:
            True se todos os itens foram armazenados com sucesso, False caso contrário
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        try:
            # Usa pipeline para armazenar múltiplos valores em uma única operação
            pipe = self.redis.pipeline()

            for key, value in items.items():
                # Serializa o valor
                serialized = json.dumps(value)

                # Armazena no Redis com TTL
                pipe.setex(key, timedelta(seconds=ttl), serialized)

            # Executa todas as operações
            pipe.execute()

            return True
        except Exception as e:
            logger.error(f"Erro ao armazenar múltiplos itens no cache: {e}")
            return False

    def extend_many_ttl(self, keys: List[str], ttl_seconds: int = None) -> int:
        """
        Estende o TTL de múltiplos itens no cache em uma única operação.

        Args:
            keys: Lista de chaves formatadas
            ttl_seconds: Novo tempo de vida em segundos (usa o padrão se None)

        Returns:
            Número de chaves cujo TTL foi estendido com sucesso
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        try:
            # Usa pipeline para estender múltiplos TTLs em uma única operação
            pipe = self.redis.pipeline()

            for key in keys:
                # Verifica se a chave existe
                pipe.exists(key)

                # Estende o TTL
                pipe.expire(key, timedelta(seconds=ttl))

            # Executa todas as operações
            results = pipe.execute()

            # Conta o número de chaves cujo TTL foi estendido com sucesso
            # Os resultados das operações exists são os primeiros len(keys) resultados
            # Os resultados das operações expire são os próximos len(keys) resultados
            return sum(exists and extended for exists, extended in zip(results[: len(keys)], results[len(keys) : 2 * len(keys)]))
        except Exception as e:
            logger.error(f"Erro ao estender TTL de múltiplos itens no cache: {e}")
            return 0

    def delete_many(self, keys: List[str]) -> int:
        """
        Remove múltiplos itens do cache em uma única operação.

        Args:
            keys: Lista de chaves formatadas a serem removidas

        Returns:
            Número de chaves removidas com sucesso
        """
        try:
            # Usa pipeline para remover múltiplos valores em uma única operação
            pipe = self.redis.pipeline()

            for key in keys:
                # Remove o item do Redis
                pipe.delete(key)

            # Executa todas as operações
            results = pipe.execute()

            # Conta o número de chaves removidas com sucesso
            return sum(bool(result) for result in results)
        except Exception as e:
            logger.error(f"Erro ao remover múltiplos itens do cache: {e}")
            return 0

    def get_by_pattern(self, pattern: str) -> Dict[str, T]:
        """
        Busca itens do cache que correspondem a um padrão.

        Args:
            pattern: Padrão de chave (ex: "user:123:*")

        Returns:
            Dicionário com as chaves e seus valores
        """
        try:
            # Busca todas as chaves que correspondem ao padrão
            keys = self.redis.keys(pattern)

            if not keys:
                return {}

            # Usa pipeline para buscar múltiplos valores em uma única operação
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)

            results = pipe.execute()

            # Converte os resultados para o formato esperado
            return {key.decode("utf-8") if isinstance(key, bytes) else key: json.loads(value) if value else None for key, value in zip(keys, results)}
        except Exception as e:
            logger.error(f"Erro ao buscar itens por padrão do cache: {e}")
            return {}

    def delete_by_pattern(self, pattern: str) -> int:
        """
        Remove itens do cache que correspondem a um padrão.

        Args:
            pattern: Padrão de chave (ex: "user:123:*")

        Returns:
            Número de chaves removidas
        """
        try:
            # Busca todas as chaves que correspondem ao padrão
            keys = self.redis.keys(pattern)

            if not keys:
                return 0

            # Remove as chaves e atualiza as timelines
            return self.delete_many([key.decode("utf-8") if isinstance(key, bytes) else key for key in keys])
        except Exception as e:
            logger.error(f"Erro ao remover itens por padrão do cache: {e}")
            return 0

    def get_values_by_set(self, set_key: str, fallback_loader: Optional[Callable[[str], Optional[T]]] = None, readd_on_success: bool = True) -> Dict[str, Optional[T]]:
        """
        Resolve um SET de referências, buscando valores em lote e aplicando fallback para chaves ausentes.

        Args:
            set_key: Chave do SET de referências
            fallback_loader: Função para reidratar uma referência ausente. Recebe a referência (str) e deve retornar o payload (dict) ou None
            readd_on_success: Se True, regrava a referência no SET quando fallback recuperar o valor

        Returns:
            Dict mapeando referência -> valor (None quando não encontrado)
        """
        try:
            members = self.redis.smembers(set_key)
            member_keys = [m.decode("utf-8") if isinstance(m, bytes) else m for m in members]

            if not member_keys:
                return {}

            values_map = self.get_many(member_keys)

            # Fallback para ausentes
            if fallback_loader:
                missing_keys = [k for k, v in values_map.items() if v is None]
                if missing_keys:
                    for ref_key in missing_keys:
                        try:
                            recovered = fallback_loader(ref_key)
                            values_map[ref_key] = recovered
                            if readd_on_success and recovered is not None:
                                # Garante que a referência esteja no SET
                                self.redis.sadd(set_key, ref_key)
                        except Exception as e:
                            logger.error(f"Fallback falhou ao recuperar referência {ref_key}: {e}")

            return values_map
        except Exception as e:
            logger.error(f"Erro ao resolver SET de referências {set_key}: {e}")
            return {}

    def get_user_timeline(self, pin: str, master_pin: Optional[str] = None, marketplace_type: Optional[str] = None, marketplace_shop_id: Optional[str] = None) -> Set[str]:
        """
        Obtém todas as chaves na timeline de um usuário ou marketplace.

        Args:
            pin: PIN do usuário
            master_pin: PIN do usuário master (se for um colaborador)
            marketplace_type: Tipo de marketplace (ex: "mercadolivre", "shopee")
            marketplace_shop_id: ID da loja no marketplace

        Returns:
            Conjunto de chaves na timeline
        """
        try:
            # Timeline do usuário sempre
            timeline_pin = master_pin if master_pin else pin
            timeline_key = self._format_user_timeline_key(timeline_pin)

            keys = self.redis.smembers(timeline_key)

            return {key.decode("utf-8") if isinstance(key, bytes) else key for key in keys}
        except Exception as e:
            logger.error(f"Erro ao obter timeline: {e}")
            return set()

    def clear_user_timeline(self, pin: str, master_pin: Optional[str] = None, marketplace_type: Optional[str] = None, marketplace_shop_id: Optional[str] = None) -> int:
        """
        Limpa toda a timeline de um usuário ou marketplace, removendo todos os itens.

        Args:
            pin: PIN do usuário
            master_pin: PIN do usuário master (se for um colaborador)
            marketplace_type: Tipo de marketplace (ex: "mercadolivre", "shopee")
            marketplace_shop_id: ID da loja no marketplace

        Returns:
            Número de itens removidos
        """
        try:
            # Timeline do usuário sempre
            timeline_pin = master_pin if master_pin else pin
            timeline_key = self._format_user_timeline_key(timeline_pin)
            print(f"Timeline key pra remover: {timeline_key}")
            logger.info(f"Timeline key pra remover: {timeline_key}")

            # Obtém todas as chaves na timeline
            keys = self.redis.smembers(timeline_key)
            print(f"Keys pra remover: {keys}")
            logger.info(f"Keys pra remover: {keys}")

            if not keys:
                return 0

            # Converte bytes para string
            keys_str = [key.decode("utf-8") if isinstance(key, bytes) else key for key in keys]

            # Remove todos os itens
            count = self.delete_many(keys_str)

            # Remove a própria timeline
            self.redis.delete(timeline_key)

            return count
        except Exception as e:
            logger.error(f"Erro ao limpar timeline: {e}")
            return 0

    def get_user_entity(self, pin: str, entity_id: str, master_pin: Optional[str] = None, marketplace_type: Optional[str] = None, marketplace_shop_id: Optional[str] = None) -> Optional[T]:
        """
        Busca uma entidade específica.

        Args:
            pin: PIN do usuário
            entity_id: ID da entidade
            master_pin: PIN do usuário master (se for um colaborador)
            marketplace_type: Tipo de marketplace (ex: "mercadolivre", "shopee")
            marketplace_shop_id: ID da loja no marketplace

        Returns:
            A entidade ou None se não encontrada
        """
        key = self._format_key(pin, entity_id, master_pin, marketplace_type, marketplace_shop_id)
        return self.get(key)

    def set_user_entity(
        self, pin: str, entity_id: str, value: T, master_pin: Optional[str] = None, ttl_seconds: int = None, marketplace_type: Optional[str] = None, marketplace_shop_id: Optional[str] = None
    ) -> bool:
        """
        Armazena uma entidade específica.

        Args:
            pin: PIN do usuário
            entity_id: ID da entidade
            value: Valor a ser armazenado
            master_pin: PIN do usuário master (se for um colaborador)
            ttl_seconds: Tempo de vida em segundos (usa o padrão se None)
            marketplace_type: Tipo de marketplace (ex: "mercadolivre", "shopee")
            marketplace_shop_id: ID da loja no marketplace

        Returns:
            True se armazenado com sucesso, False caso contrário
        """
        # Gera a chave externa (onde os dados ficam armazenados)
        key = self._format_key(pin, entity_id, master_pin, marketplace_type, marketplace_shop_id)

        # Armazena os dados na chave externa
        stored = self.set(key, value, ttl_seconds)

        # Adiciona apenas a referência à timeline do usuário
        try:
            effective_pin = master_pin if master_pin else pin
            timeline_key = self._format_user_timeline_key(effective_pin)
            self.redis.sadd(timeline_key, key)
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            self.redis.expire(timeline_key, timedelta(seconds=ttl * 2))
        except Exception as e:
            logger.error(f"Erro ao atualizar timeline do usuário: {e}")
        return stored

    def extend_user_entity_ttl(
        self, pin: str, entity_id: str, master_pin: Optional[str] = None, ttl_seconds: int = None, marketplace_type: Optional[str] = None, marketplace_shop_id: Optional[str] = None
    ) -> bool:
        """
        Estende o TTL de uma entidade específica.

        Args:
            pin: PIN do usuário
            entity_id: ID da entidade
            master_pin: PIN do usuário master (se for um colaborador)
            ttl_seconds: Tempo de vida em segundos (usa o padrão se None)
            marketplace_type: Tipo de marketplace (ex: "mercadolivre", "shopee")
            marketplace_shop_id: ID da loja no marketplace

        Returns:
            True se estendido com sucesso, False caso contrário
        """
        key = self._format_key(pin, entity_id, master_pin, marketplace_type, marketplace_shop_id)
        extended = self.extend_ttl(key, ttl_seconds)
        # Estende o TTL da timeline do usuário
        try:
            effective_pin = master_pin if master_pin else pin
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            timeline_key = self._format_user_timeline_key(effective_pin)
            self.redis.expire(timeline_key, timedelta(seconds=ttl * 2))
        except Exception as e:
            logger.error(f"Erro ao estender TTL da timeline do usuário: {e}")
        return extended

    def delete_user_entity(self, pin: str, entity_id: str, master_pin: Optional[str] = None, marketplace_type: Optional[str] = None, marketplace_shop_id: Optional[str] = None) -> bool:
        """
        Remove uma entidade específica.

        Args:
            pin: PIN do usuário
            entity_id: ID da entidade
            master_pin: PIN do usuário master (se for um colaborador)
            marketplace_type: Tipo de marketplace (ex: "mercadolivre", "shopee")
            marketplace_shop_id: ID da loja no marketplace

        Returns:
            True se removido com sucesso, False caso contrário
        """
        key = self._format_key(pin, entity_id, master_pin, marketplace_type, marketplace_shop_id)
        removed = self.delete(key)
        # Remove também da timeline do usuário
        try:
            effective_pin = master_pin if master_pin else pin
            timeline_key = self._format_user_timeline_key(effective_pin)
            self.redis.srem(timeline_key, key)
        except Exception as e:
            logger.error(f"Erro ao remover chave da timeline do usuário: {e}")
        return removed

    def get_all_user_entities(self, pin: str, master_pin: Optional[str] = None, marketplace_type: Optional[str] = None, marketplace_shop_id: Optional[str] = None) -> Dict[str, T]:
        """
        Busca todas as entidades de um usuário ou marketplace.

        Args:
            pin: PIN do usuário
            master_pin: PIN do usuário master (se for um colaborador)
            marketplace_type: Tipo de marketplace (ex: "mercadolivre", "shopee")
            marketplace_shop_id: ID da loja no marketplace

        Returns:
            Dicionário com os IDs das entidades e seus valores
        """
        # Lê sempre pela timeline do usuário, que referencia chaves externas
        timeline_pin = master_pin if master_pin else pin
        timeline_key = self._format_user_timeline_key(timeline_pin)

        try:
            keys = self.redis.smembers(timeline_key)
            if not keys:
                return {}

            # Busca valores em lote
            keys_str = [key.decode("utf-8") if isinstance(key, bytes) else key for key in keys]
            values = self.get_many(keys_str)

            # Extrai IDs e monta o resultado
            result: Dict[str, T] = {}
            for key, value in values.items():
                key_parts = self._parse_key(key)
                if key_parts.get("entity_id"):
                    result[key_parts["entity_id"]] = value

            return result
        except Exception as e:
            logger.error(f"Erro ao obter entidades pela timeline do usuário: {e}")
            return {}

    def extend_all_user_entities_ttl(
        self, pin: str, master_pin: Optional[str] = None, ttl_seconds: int = None, marketplace_type: Optional[str] = None, marketplace_shop_id: Optional[str] = None
    ) -> int:
        """
        Estende o TTL de todas as entidades de um usuário ou marketplace.

        Args:
            pin: PIN do usuário
            master_pin: PIN do usuário master (se for um colaborador)
            ttl_seconds: Tempo de vida em segundos (usa o padrão se None)
            marketplace_type: Tipo de marketplace (ex: "mercadolivre", "shopee")
            marketplace_shop_id: ID da loja no marketplace

        Returns:
            Número de entidades cujo TTL foi estendido
        """
        # Sempre usa a timeline do usuário
        timeline_pin = master_pin if master_pin else pin
        timeline_key = self._format_user_timeline_key(timeline_pin)

        # Obtém todas as chaves na timeline
        keys = self.redis.smembers(timeline_key)

        if not keys:
            return 0

        # Converte bytes para string
        keys_str = [key.decode("utf-8") if isinstance(key, bytes) else key for key in keys]

        # Estende o TTL de todas as chaves
        return self.extend_many_ttl(keys_str, ttl_seconds)

    def cleanup_legacy_timeline_keys(self) -> int:
        """
        Remove chaves de timeline legadas que começam com 'timeline:'.

        Este método deve ser executado uma vez para limpar a estrutura antiga
        onde timelines eram criadas na raiz do Redis.

        Returns:
            Número de chaves removidas
        """
        try:
            # Busca todas as chaves que começam com 'timeline:'
            legacy_keys = self.redis.keys("timeline:*")

            if not legacy_keys:
                return 0

            # Remove todas as chaves legadas
            count = 0
            for key in legacy_keys:
                key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                if self.redis.delete(key_str):
                    count += 1

            logger.info(f"Limpeza de chaves timeline legadas concluída: {count} chaves removidas")
            return count

        except Exception as e:
            logger.error(f"Erro ao limpar chaves timeline legadas: {e}")
            return 0
