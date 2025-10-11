from enum import Enum

from sqlalchemy import Column, String
from sqlalchemy import Enum as SQLEnum
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.base.models_base import BaseModel


class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    status = Column(SQLEnum(UserStatus), nullable=False, default=UserStatus.ACTIVE)

    def set_password(self, password):
        """Define a senha do usuário com hash"""
        self.password = generate_password_hash(password)

    def check_password(self, password):
        """Verifica se a senha está correta"""
        return check_password_hash(self.password, password)

    def to_dict(self):
        """Converte o usuário para dicionário"""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
