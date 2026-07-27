"""Entità del modulo `strutture` (AD-18, AD-20)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.date_range import utcnow
from app.core.db import Base, new_uuid7


class StatoStruttura(enum.Enum):
    """Una Struttura si archivia, mai si distrugge (AD-20)."""

    ATTIVA = "attiva"
    ARCHIVIATA = "archiviata"


class RegimeLettura(Base):
    """Conferma di lettura del pannello Regime fiscale (UX-DR14).

    Traccia PER QUALE conteggio di Strutture l'Host ha già visto il
    pannello a schermo intero: non è il Regime (che resta derivato,
    AD-12), è solo lo stato di lettura dell'informativa.
    """

    __tablename__ = "regime_lettura"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    # `unique=True` senza `index=True`: insieme SQLAlchemy li rende come un
    # unico indice unico, mentre lo schema porta un UNIQUE constraint (che ha
    # già il suo indice) — la deriva di `alembic check` chiusa dalla
    # migrazione 0009 (MYL-44). Il vincolo resta lo stesso: un solo record di
    # lettura per Host.
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("host.id"), nullable=False, unique=True
    )
    conteggio_confermato: Mapped[int] = mapped_column(Integer, nullable=False)
    confermato_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Struttura(Base):
    __tablename__ = "struttura"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("host.id"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    # `comune`/`regione` restano il testo mostrato all'Host; i codici ISTAT
    # sono il legame con l'anagrafica (AD-9) e possono mancare quando il
    # luogo non è ancora in anagrafica: in quel caso la configurazione
    # degrada in sicurezza, l'onboarding non si blocca (FR-2).
    comune: Mapped[str] = mapped_column(String(120), nullable=False)
    comune_codice_istat: Mapped[str | None] = mapped_column(
        ForeignKey("comune.codice_istat"), nullable=True, index=True
    )
    regione: Mapped[str] = mapped_column(String(80), nullable=False)
    regione_codice_istat: Mapped[str | None] = mapped_column(
        ForeignKey("regione.codice_istat"), nullable=True, index=True
    )
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
