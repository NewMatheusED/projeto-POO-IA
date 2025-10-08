"""
Repositório para cache de usuários.

Este módulo implementa o repositório para cache de usuários,
utilizando o padrão Cache-Aside com Redis como backend de cache.
"""

import logging
from typing import Any, Dict, Optional

from app.cache.base import Repository
from app.cache.config import CacheConfig
from app.cache.redis_timeline import RedisTimelineCache
from app.services.user.models import UserRole, users
from app.services.user.schema import create_user_response_schema
from app.utils.context_manager import get_db_session

logger = logging.getLogger(__name__)


class UserCache(Repository[Dict[str, Any]]):
    """
    Repositório para cache de usuários.

    Implementa o padrão Cache-Aside para dados de usuários,
    utilizando Redis como backend de cache e schema para serialização.
    """

    def __init__(self):
        """
        Inicializa o repositório com a estratégia de cache para usuários.
        """
        ttl = CacheConfig.get_ttl("user")

        # Define padrões de chaves personalizados para user
        key_patterns = {"external": "user:{pin}", "colabs_timeline": "user:{pin}:colabs", "colabs": "user:{master_pin}:users:{pin}", "user_timeline": "user:{pin}:user:timeline"}

        cache_strategy = RedisTimelineCache[Dict[str, Any]](entity_type="user", ttl_seconds=ttl, key_patterns=key_patterns)
        super().__init__(cache_strategy, schema_factory=create_user_response_schema)

        # Mantém referência aos padrões para uso nos métodos
        self.key_patterns = key_patterns

    def _format_user_key(self, pin: str) -> str:
        """Formata a chave do usuário."""
        return self.key_patterns["external"].format(pin=pin)

    def _format_colabs_timeline_key(self, pin: str) -> str:
        """Formata a chave do SET de colaboradores do master."""
        return self.key_patterns["colabs_timeline"].format(pin=pin)

    def _format_colabs_key(self, master_pin: str, pin: str) -> str:
        """Formata a chave do usuário do colaborador."""
        return self.key_patterns["colabs"].format(master_pin=master_pin, pin=pin)

    def parse_id_from_key(self, key: str) -> Optional[str]:
        """
        Extrai o PIN do usuário a partir de uma chave formatada.

        Args:
            key: Chave formatada (ex: "user:BG_123")

        Returns:
            PIN do usuário ou None se não conseguir extrair
        """
        try:
            parts = key.split(":")
            if len(parts) == 2 and parts[0] == "user":
                return parts[1]
            return None
        except Exception:
            return None

    def get_from_database(self, pin: str) -> Optional[Dict[str, Any]]:
        """
        Busca dados do usuário do banco de dados.

        Args:
            pin: PIN do usuário

        Returns:
            Dados do usuário ou None se não encontrado
        """
        try:
            with get_db_session() as db:
                user = db.query(users).filter(users.pin == pin).first()

                if not user:
                    return None

                # Usar schema para serializar corretamente
                return self.apply_schema(user, many=False)
        except Exception as e:
            logger.error(f"Erro ao buscar usuário do banco: {e}")
            return None
        finally:
            db.close()

    def save_to_database(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upsert de dados do usuário no banco de dados.

        Args:
            user_data: Dados do usuário a serem atualizados

        Returns:
            Dados do usuário atualizados
        """
        try:
            with get_db_session() as db:
                # Upsert por pin
                if not user_data.get("pin"):
                    raise ValueError("Campo 'pin' é obrigatório para salvar usuário")

                user = db.query(users).filter(users.pin == user_data["pin"]).first()

                if not user:
                    # Inserção requer payload mínimo
                    required_fields = ["pin", "name", "role"]
                    missing = [f for f in required_fields if not user_data.get(f)]
                    if missing:
                        raise ValueError(f"Campos obrigatórios ausentes para inserir usuário: {missing}")

                    user = users(pin=user_data["pin"])  # cria base e completa abaixo
                    db.add(user)

                # Atualiza apenas campos presentes
                updatable_fields = ["name", "email", "phone", "status", "master_pin", "level", "role"]
                for field in updatable_fields:
                    if field in user_data and user_data[field] is not None:
                        setattr(user, field, user_data[field])

                db.commit()
                db.refresh(user)

                return user
        except Exception as e:
            logger.error(f"Erro ao salvar usuário no banco: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def get_user(self, pin: str) -> Optional[Dict[str, Any]]:
        """
        Busca dados do usuário utilizando o padrão Cache-Aside.

        Args:
            pin: PIN do usuário

        Returns:
            Dados do usuário ou None se não encontrado
        """
        # Usar chave externa formatada para evitar duplicação
        key = self._format_user_key(pin)
        return self.get(key)

    def get_user_with_colabs(self, master_pin: str) -> Dict[str, Any]:
        """
        Busca dados do usuário master e seus colaboradores.

        Args:
            master_pin: PIN do usuário master

        Returns:
            Dados do usuário master com lista de colaboradores
        """
        # Busca dados do usuário master usando chave externa
        master_key = self._format_user_key(master_pin)
        master = self.get(master_key)

        if not master:
            return {}

        try:
            # Chave SET de referências de colaboradores (timeline)
            colabs_set_key = self._format_colabs_timeline_key(master_pin)

            # Lê referências existentes
            try:
                ref_members = self.cache.redis.smembers(colabs_set_key)
                colab_ref_keys = [m.decode("utf-8") if isinstance(m, bytes) else m for m in ref_members]
            except Exception as e:
                logger.error(f"Erro ao ler SET de colabs: {e}")
                colab_ref_keys = []

            # Se vazio, popular a partir do banco
            if not colab_ref_keys:
                with get_db_session() as db:
                    colabs = db.query(users).filter(users.master_pin == master_pin).all()
                    colabs_list = self.apply_schema(colabs, many=True)

                    # Garantir que colabs_list é uma lista
                    if not isinstance(colabs_list, list):
                        colabs_list = [colabs_list] if colabs_list is not None else []

                    for colab in colabs_list:
                        # Se colab já é um dict (serializado pelo schema), usar diretamente
                        if isinstance(colab, dict):
                            pin = colab.get("pin")
                            payload = colab
                        else:
                            # Se colab é um objeto SQLAlchemy, serializar com schema
                            try:
                                payload = self.apply_schema(colab, many=False)
                                pin = payload.get("pin") if isinstance(payload, dict) else getattr(colab, "pin", None)
                            except Exception as e:
                                logger.error(f"Erro ao serializar colaborador: {e}")
                                pin = getattr(colab, "pin", None)
                                payload = None

                        if not pin or not isinstance(payload, dict):
                            continue

                        # Salva colaborador usando chave simples na raiz
                        colab_key = self._format_user_key(pin)
                        self.cache.set(colab_key, payload)

                        # Registra referência no SET de colabs do master
                        try:
                            self.cache.redis.sadd(colabs_set_key, colab_key)
                        except Exception as e:
                            logger.error(f"Erro ao adicionar membro no SET de colabs: {e}")

                    # TTL do SET (duas vezes o default para segurança)
                    try:
                        self.cache.redis.expire(colabs_set_key, int(self.cache.default_ttl) * 2)
                    except Exception as e:
                        logger.error(f"Erro ao definir TTL do SET de colabs: {e}")

                    db.close()

                # Recarrega referências
                try:
                    ref_members = self.cache.redis.smembers(colabs_set_key)
                    colab_ref_keys = [m.decode("utf-8") if isinstance(m, bytes) else m for m in ref_members]
                except Exception:
                    colab_ref_keys = []

            # Resolve referências para payloads dos colabs
            colabs_payloads: list[dict] = []
            if colab_ref_keys:

                def _fallback_loader(ref_key: str) -> Optional[Dict[str, Any]]:
                    try:
                        # ref_key agora é uma chave simples: user:BG_123
                        pin = self.parse_id_from_key(ref_key)
                        if not pin:
                            return None
                        recovered = self.get_user(pin)
                        if isinstance(recovered, dict):
                            # Recria a entidade na chave simples
                            colab_key = self._format_user_key(pin)
                            self.cache.set(colab_key, recovered)
                            return recovered
                        return None
                    except Exception as e:
                        logger.error(f"Fallback falhou ao reidratar colab para chave {ref_key}: {e}")
                        return None

                values_map = self.cache.get_values_by_set(colabs_set_key, fallback_loader=_fallback_loader, readd_on_success=True)
                for key in colab_ref_keys:
                    value = values_map.get(key)
                    if isinstance(value, dict):
                        colabs_payloads.append(value)

            # Garantir que master é um dict antes de adicionar colabs
            if not isinstance(master, dict):
                master = {}

            master["colabs"] = colabs_payloads
            return master
        except Exception as e:
            logger.error(f"Erro ao buscar colaboradores: {e}")
            return master

    def after_save_update_cache(self, id: str, saved_entity: Dict[str, Any]) -> None:
        """
        Atualizações derivadas após salvar usuário:
        - Se for COLAB, atualiza chave derivada sob o master e SET de colabs.
        """
        try:
            role_value = saved_entity.get("role")
            # Normaliza role possívelmente como enum/str
            role_str = role_value.name if hasattr(role_value, "name") else role_value

            if role_str and str(role_str) == UserRole.COLAB.value:
                colab_pin = saved_entity.get("pin")
                master_pin = saved_entity.get("master_pin")
                if not colab_pin or not master_pin:
                    return

                # Usar chave simples para colaborador
                colab_key = self._format_user_key(colab_pin)

                # Salvar colaborador na raiz
                self.cache.set(colab_key, saved_entity)

                # Adicionar referência no SET de colabs do master
                colabs_set_key = self._format_colabs_timeline_key(master_pin)
                try:
                    self.cache.redis.sadd(colabs_set_key, colab_key)
                    self.cache.redis.expire(colabs_set_key, int(self.cache.default_ttl) * 2)
                except Exception as e:
                    logger.error(f"Erro ao adicionar colaborador no SET: {e}")
        except Exception as e:
            logger.error(f"after_save_update_cache(UserCache) falhou: {e}")
