"""
Repositório para cache de anúncios do Mercado Livre.

Este módulo implementa o repositório para cache de anúncios do Mercado Livre,
utilizando o padrão Cache-Aside com Redis como backend de cache.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from app.cache.base import Repository
from app.cache.config import CacheConfig
from app.cache.redis_timeline import RedisTimelineCache
from app.services.ads.models import generalAds, meliAds, meliAdsVariations
from app.services.ads.schema import create_general_ads_schema, create_meli_ads_schema
from app.services.user.models import users
from app.utils.context_manager import get_db_session

logger = logging.getLogger(__name__)


class MeliAdsCache(Repository[Dict[str, Any]]):
    """
    Repositório para cache de anúncios do Mercado Livre.

    Implementa o padrão Cache-Aside para dados de anúncios,
    utilizando Redis como backend de cache.
    """

    def __init__(self):
        """
        Inicializa o repositório com a estratégia de cache para anúncios.
        """
        ttl = CacheConfig.get_ttl("ads")

        # Define padrões de chaves personalizados para ads
        self.key_patterns = {
            "external": "ads:{marketplace_type}:{marketplace_shop_id}:{ad_id}",
            "user_timeline": "user:{pin}:ads:timeline",
        }

        cache_strategy = RedisTimelineCache[Dict[str, Any]](entity_type="ads", ttl_seconds=ttl, key_patterns=self.key_patterns)
        super().__init__(cache_strategy, schema_factory=create_meli_ads_schema)

    def _format_ad_key(self, marketplace_type: str, marketplace_shop_id: str, ad_id: str) -> str:
        """Formata a chave externa do anúncio."""
        return self.key_patterns["external"].format(marketplace_type=marketplace_type, marketplace_shop_id=marketplace_shop_id, ad_id=ad_id)

    def _format_user_timeline_key(self, pin: str) -> str:
        """Formata a chave da timeline do usuário."""
        return self.key_patterns["user_timeline"].format(pin=pin)

    # Permite que o base interprete chaves externas em get/get_many
    def parse_id_from_key(self, key: str) -> Optional[str]:
        try:
            parts = key.split(":")
            # Esperado: ads:{marketplace_type}:{marketplace_shop_id}:{ad_id}
            if len(parts) >= 4 and parts[0] == "ads":
                return parts[3]
            return None
        except Exception:
            return None

    def get_from_database(self, ad_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca dados do anúncio do banco de dados.

        Args:
            ad_id: ID do anúncio (MLB)

        Returns:
            Dados do anúncio ou None se não encontrado
        """
        try:
            with get_db_session() as db:

                # Verifica se é um MLB (anúncio do Mercado Livre)
                if ad_id.startswith("MLB"):
                    ad = db.query(meliAds).filter(meliAds.mlb == ad_id).first()

                    if not ad:
                        return None

                    # Serializa dentro da sessão
                    return self.apply_schema(ad, many=False)
                else:
                    # Busca anúncio geral por ID
                    general_ad = db.query(generalAds).filter(generalAds.id == int(ad_id)).first()

                    if not general_ad:
                        return None

                    # Serializa dentro da sessão
                    return create_general_ads_schema()(many=False).dump(general_ad)
        except Exception as e:
            logger.error(f"Erro ao buscar anúncio do banco: {e}")
            return None
        finally:
            db.close()

    def save_to_database(self, ad_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Atualiza dados do anúncio no banco de dados.

        Args:
            ad_data: Dados do anúncio a serem atualizados

        Returns:
            Dados do anúncio atualizados
        """
        try:
            with get_db_session() as db:

                # Verifica se é um MLB (anúncio do Mercado Livre)
                if "mlb" in ad_data and ad_data["mlb"].startswith("MLB"):
                    ad = db.query(meliAds).filter(meliAds.mlb == ad_data["mlb"]).first()

                    if not ad:
                        raise ValueError(f"Anúncio com MLB {ad_data['mlb']} não encontrado")

                    # Atualiza os campos permitidos
                    for field in ["name", "price", "stock", "status"]:
                        if field in ad_data:
                            setattr(ad, field, ad_data[field])

                    # Atualiza variações se fornecidas
                    if "variations" in ad_data and ad_data["variations"]:
                        for var_data in ad_data["variations"]:
                            if "variation_id" in var_data:
                                var = db.query(meliAdsVariations).filter(meliAdsVariations.mlb == ad_data["mlb"], meliAdsVariations.variation_id == var_data["variation_id"]).first()

                                if var:
                                    # Atualiza campos da variação
                                    for field in ["price", "stock", "sku"]:
                                        if field in var_data:
                                            setattr(var, field, var_data[field])

                    db.commit()
                    db.refresh(ad)

                    # Converte para dicionário novamente
                    return self.get_from_database(ad.mlb)
                else:
                    # Atualiza anúncio geral
                    general_ad = db.query(generalAds).filter(generalAds.id == int(ad_data["id"])).first()

                    if not general_ad:
                        raise ValueError(f"Anúncio geral com ID {ad_data['id']} não encontrado")

                    # Atualiza os campos permitidos
                    for field in ["sku", "is_variation"]:
                        if field in ad_data:
                            setattr(general_ad, field, ad_data[field])

                    db.commit()
                    db.refresh(general_ad)

                    # Converte para dicionário novamente
                    return self.get_from_database(str(general_ad.id))
        except Exception as e:
            logger.error(f"Erro ao salvar anúncio no banco: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def get_ad(self, ad_id: str, marketplace_type: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Busca dados do anúncio utilizando o padrão Cache-Aside.

        Args:
            ad_id: ID do anúncio (MLB)
            marketplace_type: Tipo de marketplace
            account_id: ID da conta (marketplace_shop_id), opcional

        Returns:
            Dados do anúncio ou None se não encontrado
        """
        # Se temos o account_id, usamos a nova estrutura de chaves
        if account_id:
            # Formato: ads:{marketplace_type}:{marketplace_shop_id}:{ad_id}
            key = self._format_ad_key(marketplace_type, account_id, ad_id)
            return self.cache.get(key) or self._load_ad_from_db(ad_id, marketplace_type, account_id)

        # Caso contrário, tentamos o formato antigo
        return self.get(ad_id)

    def _load_ad_from_db(self, ad_id: str, marketplace_type: str, account_id: str) -> Optional[Dict[str, Any]]:
        """
        Carrega o anúncio do banco de dados e armazena no cache.

        Args:
            ad_id: ID do anúncio (MLB)
            marketplace_type: Tipo de marketplace
            account_id: ID da conta (marketplace_shop_id)

        Returns:
            Dados do anúncio ou None se não encontrado
        """
        ad_data = self.get_from_database(ad_id)
        if ad_data:
            # Armazena no cache com a nova estrutura de chaves
            key = self._format_ad_key(marketplace_type, account_id, ad_id)
            self.cache.set(key, ad_data)
        return ad_data

    def get_account_ads(self, account_id: str, pin: str, marketplace_type: str) -> List[Dict[str, Any]]:
        """
        Busca todos os anúncios de uma conta.

        Args:
            account_id: ID da conta (marketplace_shop_id)
            pin: PIN do usuário
            marketplace_type: Tipo de marketplace

        Returns:
            Lista de anúncios da conta
        """
        try:
            # Verifica se é um colaborador
            with get_db_session() as db:
                user = db.query(users).filter(users.pin == pin).first()

                if not user:
                    return []

                # Se for colaborador, usa o PIN do master para a timeline
                master_pin = user.master_pin if user.is_colab else None
                timeline_pin = master_pin if master_pin else pin

                # Busca anúncios pela timeline do usuário com hidratação embutida no base
                timeline_key = self._format_user_timeline_key(timeline_pin)
                ad_keys = self.cache.redis.smembers(timeline_key)
                keys_str = [key.decode("utf-8") if isinstance(key, bytes) else key for key in ad_keys]
                # Filtra apenas as chaves da conta
                matching_keys = [k for k in keys_str if isinstance(k, str) and k.startswith(f"ads:{marketplace_type}:{account_id}:")]
                values_map = self.get_many(matching_keys)
                # Limpa referências inválidas e renova TTL
                for ref_key, payload in values_map.items():
                    if payload is None:
                        self.cache.redis.srem(timeline_key, ref_key)
                self.cache.redis.expire(timeline_key, timedelta(seconds=self.cache.default_ttl * 2))
                ads_dict = {k: v for k, v in values_map.items() if v is not None}

                # Se encontramos anúncios no cache, retornamos
                if ads_dict and len(ads_dict) > 0:
                    logger.info(f"Anúncios da conta {account_id} encontrados no cache: {len(ads_dict)} anúncios")
                    # Converte o dicionário de chaves/valores para uma lista de anúncios
                    return list(ads_dict.values())

                # Busca do banco (popula quando ausente do cache)
                # Busca anúncios gerais da conta
                general_ads_query = db.query(generalAds).filter(
                    generalAds.marketplace_shop_id == account_id,
                )

                general_ads_list = general_ads_query.all()

                # Converte para lista de dicionários
                ads_list = []
                for general_ad in general_ads_list:
                    # Busca anúncio específico do Mercado Livre (se existir)
                    meli_ad = db.query(meliAds).filter(meliAds.general_ad_id == general_ad.id).first()

                    if meli_ad:
                        # Busca variações
                        variations = db.query(meliAdsVariations).filter(meliAdsVariations.mlb == meli_ad.mlb).all()
                        variations_list = []

                        for var in variations:
                            var_dict = {
                                "variation_id": var.variation_id,
                                "sku": var.sku,
                                "price": float(var.price),
                                "stock": var.stock,
                                "sold_quantity": var.sold_quantity,
                            }
                            variations_list.append(var_dict)

                        # Serializa dentro da sessão
                        ad_dict = self.apply_schema(meli_ad, many=False)

                        # Armazena o anúncio na nova estrutura de chaves (chave externa)
                        ad_key = self._format_ad_key(marketplace_type, account_id, meli_ad.mlb)
                        self.cache.set(ad_key, ad_dict)

                        # Adiciona referência à timeline do usuário
                        timeline_key = self._format_user_timeline_key(timeline_pin)
                        self.cache.redis.sadd(timeline_key, ad_key)
                        self.cache.redis.expire(timeline_key, timedelta(seconds=self.cache.default_ttl * 2))

                    ads_list.append(ad_dict)

                return ads_list
        except Exception as e:
            logger.error(f"Erro ao buscar anúncios da conta: {e}")
            return []
        finally:
            db.close()

    def after_save_update_cache(self, id: str, saved_entity: Dict[str, Any]) -> None:
        """
        Após salvar um anúncio, garante referência na timeline do usuário correto.

        Requer que a aplicação passe sempre o id formatado como
        ads:{marketplace_type}:{marketplace_shop_id}:{ad_id}
        """
        try:
            # saved_entity deve conter o user_pin (direto ou resolvível) e marketplace_shop_id
            # Caso não tenha user_pin, não atualizamos timeline aqui (depende do contexto de chamada)
            user_pin = saved_entity.get("user_pin")
            if not user_pin:
                return
            timeline_key = self._format_user_timeline_key(user_pin)
            self.add_reference_to_sets(id, [timeline_key])
        except Exception as e:
            logger.error(f"after_save_update_cache(MeliAdsCache) falhou: {e}")
