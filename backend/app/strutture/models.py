"""Entità del modulo `strutture` (AD-18, AD-20)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.date_range import utcnow
from app.core.db import Base, new_uuid7


class StatoStruttura(enum.Enum):
    """Una Struttura si archivia, mai si distrugge (AD-20)."""

    ATTIVA = "attiva"
    ARCHIVIATA = "archiviata"


class Struttura(Base):
    __tablename__ = "struttura"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("host.id"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    comune: Mapped[str] = mapped_column(String(120), nullable=False)
    regione: Mapped[str] = mapped_column(String(80), nullable=False)
    cin: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stato: Mapped[StatoStruttura] = mapped_column(
        Enum(
            StatoStruttura,
            name="stato_struttura",
            values_callable=lambda e: [s.value for s in e],
        ),
        nullable=False,
        default=StatoStruttura.ATTIVA,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
