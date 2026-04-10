import uuid
import enum
from sqlalchemy import String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from ..core.database import Base


class UserRole(str, enum.Enum):
    owner      = "owner"
    technicien = "technicien"


class User(Base):
    __tablename__ = "users"

    id         : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       : Mapped[str]       = mapped_column(String(200), nullable=False)
    email      : Mapped[str]       = mapped_column(String(200), unique=True, nullable=False)
    role       : Mapped[UserRole]  = mapped_column(Enum(UserRole, name="user_role", create_type=False), nullable=False, default=UserRole.technicien)
    is_active  : Mapped[bool]      = mapped_column(Boolean, nullable=False, default=True)
    created_at : Mapped[DateTime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at : Mapped[DateTime]  = mapped_column(DateTime(timezone=True), server_default=func.now())

    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")


class APIKey(Base):
    __tablename__ = "api_keys"

    id           : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_hash     : Mapped[str]            = mapped_column(String(64), unique=True, nullable=False)
    name         : Mapped[str]            = mapped_column(String(100), nullable=False)
    last_used_at : Mapped[DateTime | None]= mapped_column(DateTime(timezone=True))
    is_active    : Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at   : Mapped[DateTime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="api_keys")
