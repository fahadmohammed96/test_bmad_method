"""Entità di `identity` (AD-18): host e sessione."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.date_range import utcnow
from app.core.db import Base, new_uuid7


class Host(Base):
    """L'Host è la radice della tenancy (AD-2): ogni dato applicativo
    tenant-owned porterà `host_id` riferito a questa tabella."""

    __tablename__ = "host"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Sessione(Base):
    """Sessione server-side (AD-15): in DB vive solo l'hash del token."""

    __tablename__ = "sessione"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("host.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
