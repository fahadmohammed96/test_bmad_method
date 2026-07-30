"""Entità del modulo `strutture` (AD-18, AD-20)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.date_range import utcnow
from app.core.db import Base, new_uuid7


class StatoStruttura(enum.Enum):
    """Una Struttura si archivia, mai si distrugge (AD-20)."""

    ATTIVA = "attiva"
    ARCHIVIATA = "archiviata"


class RegimeLettura(Base):
    """Registro delle conferme di lettura del pannello Regime fiscale (UX-DR14).

    Traccia PER QUALE conteggio di Strutture l'Host ha già visto il
    pannello a schermo intero: non è il Regime (che resta derivato,
    AD-12), è lo stato di lettura dell'informativa — e insieme l'evidenza
    datata che l'Host è stato informato della soglia fiscale (UJ-4).

    Il rientro sotto soglia REVOCA la conferma (`revocata_il`) invece di
    cancellare la riga: una `DELETE` perderebbe la prova che l'Host sia mai
    stato informato, su una materia in cui la prova è il punto — e sarebbe una
    cancellazione distruttiva fuori dalla lista esaustiva di AD-20. È la forma
    di AD-19: transizioni tracciate, mai `delete`.

    Le righe si accumulano un giro di soglia alla volta e la più recente vince.
    L'invariante «una sola conferma VALIDA per Host» resta, imposto dall'indice
    unico parziale: è quello che tiene, non l'unicità di `host_id`, che con la
    storia in tabella non è più vera.
    """

    __tablename__ = "regime_lettura"
    __table_args__ = (
        # Indice unico PARZIALE sulle sole conferme valide. Sostituisce
        # `uq_regime_lettura_host_id`, che con più giri di soglia in tabella
        # vieterebbe la storia; l'invariante che serve al codice — al più una
        # conferma valida per Host, quindi `one_or_none()` legittimo — è questo.
        #
        # Dichiarato nel modello e non solo in migrazione: un indice che vive
        # nel database e non nei modelli è deriva, e `alembic check` in CI
        # (MYL-44) propone di cancellarlo.
        Index(
            "uq_regime_lettura_conferma_attiva",
            "host_id",
            unique=True,
            postgresql_where=text("revocata_il IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    # `index=True` semplice: l'indice del vincolo unico non copre più tutte le
    # righe (è parziale), e le letture della storia di un Host lo vogliono
    # pieno. È l'indice che la migrazione 0009 aveva tolto perché allora
    # duplicava quello di `uq_regime_lettura_host_id`.
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("host.id"), nullable=False, index=True
    )
    conteggio_confermato: Mapped[int] = mapped_column(Integer, nullable=False)
    confermato_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    # NULL = la conferma vale ORA. Non è un flag booleano: la data è l'evidenza
    # di QUANDO la conferma ha smesso di valere, ed è metà di ciò che rende la
    # storia leggibile («informato il giorno X, revocata il giorno Y»).
    revocata_il: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
