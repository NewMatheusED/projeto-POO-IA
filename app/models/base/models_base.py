from enum import Enum

from sqlalchemy import Column, DateTime, Integer, String, func, ForeignKey

from app.database import db


class MarketplaceType(Enum):
    meli = "meli"
    shopee = "shopee"


class ShippingModeMeli(Enum):
    xd_drop_off = "Agência"
    fulfillment = "FULL"
    cross_docking = "Coleta"
    drop_off = "Correios"
    me2 = "Mercado Envios"
    self_service = "Flex"
    not_specified = "Não especificado"


class AdTypeMeli(Enum):
    gold_pro = "Premium"
    gold_premium = "Diamante"
    gold_special = "Clássico"
    gold = "Ouro"
    silver = "Prata"
    bronze = "Bronze"
    free = "Grátis"


class BaseModel(db.Model):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


