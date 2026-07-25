"""Entità di `identity` (AD-18): host e sessione."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.date_range import utcnow
from app.core.db import Base, new_uuid7


class CanaleNotifica(enum.Enum):
    """Canali di notifica Host dell'MVP (envelope operativo: in-app + email)."""

    IN_APP = "in_app"
    EMAIL = "email"


class Host(Base):
    """L'Host è la radice della tenancy (AD-2): ogni dato applicativo
    tenant-owned porterà `host_id` riferito a questa tabella."""

    __tablename__ = "host"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    canale_notifica_preferito: Mapped[CanaleNotifica] = mapped_column(
        Enum(
            CanaleNotifica,
            name="canale_notifica",
            values_callable=lambda e: [c.value for c in e],
        ),
        nullable=False,
        default=CanaleNotifica.EMAIL,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class TentativoLogin(Base):
    """Traccia effimera dei tentativi di accesso, per frenare gli abusi.

    NON è un dato tenant-owned: si registra PRIMA di sapere se l'account
    esiste — legarlo a un `host_id` rivelerebbe quali email sono
    registrate. Contiene solo email tentata, origine ed esito: mai la
    password. Le righe vecchie le elimina il purge periodico.
    """

    __tablename__ = "tentativo_login"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    origine: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    avvenuto_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
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
