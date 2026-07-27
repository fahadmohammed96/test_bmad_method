"""Entità del modulo `calendario` (AD-4, AD-18, AD-19, AD-20).

Tre tabelle, tutte tenant-owned (AD-2):

- `feed_ical` — il collegamento fra una Struttura e l'URL di export di un
  Canale. L'URL è input non fidato (NFR-17): qui si conserva, non si fida.
- `sync_run` — traccia APPEND-ONLY di ogni esecuzione di sync, riuscita o
  fallita. È la sorgente unica di «ultimo aggiornamento HH:MM» (NFR-2):
  un run fallito senza traccia rende «non sincronizzo da tre giorni»
  indistinguibile da «non ci sono novità».
- `prenotazione` — chiave naturale `(feed_id, ical_uid)` imposta da un
  UNIQUE del database, non da un controllo applicativo: sotto concorrenza
  a decidere deve essere il vincolo (A3-1).

Nessuna di queste righe si cancella mai: la guardia
`tests/test_append_preserving_convention.py` (GS-6) lo impone.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.date_range import DateRange, utcnow
from app.core.db import Base, new_uuid7


class CanaleFeed(enum.Enum):
    """Origine delle Prenotazioni importate (FR-4)."""

    AIRBNB = "airbnb"
    BOOKING = "booking"
    ALTRO = "altro"


class StatoPrenotazione(enum.Enum):
    """Stati di AD-19: solo `attiva` concorre ai Conflitti.

    `rimossa_dal_feed` è la transizione che sostituisce la cancellazione
    quando un evento scompare dall'export dell'OTA (AD-4).
    """

    ATTIVA = "attiva"
    CANCELLATA = "cancellata"
    RIMOSSA_DAL_FEED = "rimossa_dal_feed"


class EsitoSyncRun(enum.Enum):
    RIUSCITO = "riuscito"
    FALLITO = "fallito"


class CategoriaErroreSync(enum.Enum):
    """Categoria dell'errore, mai il dettaglio tecnico (AD-16, NFR-17).

    `URL_NON_RAGGIUNGIBILE` copre insieme il fallimento di connessione E il
    rifiuto della politica di uscita di rete: l'Host vede lo stesso esito,
    così il messaggio d'errore non diventa un canale per scoprire la rete
    interna (NFR-17).
    """

    URL_NON_RAGGIUNGIBILE = "url_non_raggiungibile"
    TIMEOUT = "timeout"
    RISPOSTA_TROPPO_GRANDE = "risposta_troppo_grande"
    ESITO_HTTP_INATTESO = "esito_http_inatteso"
    FEED_NON_VALIDO = "feed_non_valido"
    FEED_SENZA_EVENTI = "feed_senza_eventi"


# Il tipo Postgres `canale_feed` è condiviso da `feed_ical` e
# `prenotazione`: una sola istanza riusata, così non si generano due
# CREATE TYPE per lo stesso nome.
TIPO_CANALE_FEED = Enum(
    CanaleFeed,
    name="canale_feed",
    values_callable=lambda e: [c.value for c in e],
)


class FeedIcal(Base):
    __tablename__ = "feed_ical"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("host.id"), nullable=False, index=True
    )
    struttura_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("struttura.id"), nullable=False, index=True
    )
    # Text e non String(n): la lunghezza degli URL di export delle OTA non è
    # sotto il nostro controllo, e un troncamento silenzioso romperebbe il
    # fetch senza dire perché.
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canale: Mapped[CanaleFeed] = mapped_column(TIPO_CANALE_FEED, nullable=False)
    collegato_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    # Validatori di cache HTTP dell'ultimo import RIUSCITO (RFC 9110 §8.8):
    # si rimandano come `If-None-Match` / `If-Modified-Since` e permettono al
    # portale di rispondere 304 invece di ritrasmettere il calendario (AD-4).
    #
    # Si scrivono SOLO dopo una riconciliazione completa, mai dopo un run
    # fallito: un validatore scritto su un corpo che non abbiamo importato
    # farebbe rispondere 304 a un feed che nel database non è mai arrivato,
    # e il Feed resterebbe fermo dichiarandosi aggiornato — la falsa
    # sincronia di NFR-2 nella sua forma peggiore, perché silenziosa.
    #
    # Opachi per contratto: `Text` e non una forma strutturata. L'`ETag` è
    # una stringa arbitraria del portale e `Last-Modified` va rimandato
    # VERBATIM, non riformattato da noi.
    etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_modified: Mapped[str | None] = mapped_column(Text, nullable=True)


class SyncRun(Base):
    """Esito di un'esecuzione di sync: append-only, una riga per run."""

    __tablename__ = "sync_run"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("host.id"), nullable=False, index=True
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feed_ical.id"), nullable=False, index=True
    )
    esito: Mapped[EsitoSyncRun] = mapped_column(
        Enum(
            EsitoSyncRun,
            name="esito_sync_run",
            values_callable=lambda e: [c.value for c in e],
        ),
        nullable=False,
    )
    categoria_errore: Mapped[CategoriaErroreSync | None] = mapped_column(
        Enum(
            CategoriaErroreSync,
            name="categoria_errore_sync",
            values_callable=lambda e: [c.value for c in e],
        ),
        nullable=True,
    )
    prenotazioni_importate: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    prenotazioni_aggiornate: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    prenotazioni_rimosse_dal_feed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # Un evento ricomparso nel feed dopo essere stato marcato
    # `rimossa_dal_feed` NON torna `attiva` da solo: la transizione di
    # ritorno è una decisione di prodotto aperta (test design §4.2-2).
    # Il contatore esiste perché il fatto sia VISIBILE invece che ingoiato.
    prenotazioni_ricomparse: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # VEVENT presenti nel feed ma non normalizzabili (UID assente, date
    # incoerenti): non diventano Prenotazioni e non si perdono in silenzio
    # (NFR-1).
    eventi_malformati: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # L'MVP non espande le ricorrenze: un VEVENT con RRULE entra come
    # singola occorrenza ed è contato qui, perché «ignorato in silenzio»
    # sarebbe una Prenotazione persa (NFR-1).
    eventi_ricorrenti_non_espansi: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # Il portale ha risposto `304 Not Modified`: run RIUSCITO in cui non si è
    # scaricato né riconciliato nulla, perché non c'era nulla di nuovo (AD-4).
    #
    # Senza questa colonna un run da 304 sarebbe indistinguibile da un run che
    # ha riconciliato un feed vuoto di novità: entrambi hanno tutti i
    # contatori a zero. La differenza conta — il primo dice «il portale
    # conferma che è tutto uguale», il secondo «abbiamo riletto tutto».
    non_modificato: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    iniziato_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    concluso_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Prenotazione(Base):
    __tablename__ = "prenotazione"
    __table_args__ = (
        # Chiave naturale = LA COPPIA, non l'uid: lo stesso `ical_uid` su due
        # Feed diversi resta due Prenotazioni distinte. `feed_id` e
        # `ical_uid` sono nullable per le Prenotazioni manuali (Story 2.4) e
        # in Postgres i NULL sono distinti fra loro: il vincolo morde solo
        # sulle righe che vengono da un Feed, che è esattamente il perimetro
        # dell'idempotenza.
        UniqueConstraint("feed_id", "ical_uid", name="uq_prenotazione_feed_ical_uid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("host.id"), nullable=False, index=True
    )
    struttura_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("struttura.id"), nullable=False, index=True
    )
    feed_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feed_ical.id"), nullable=True, index=True
    )
    ical_uid: Mapped[str | None] = mapped_column(String(500), nullable=True)
    canale: Mapped[CanaleFeed] = mapped_column(TIPO_CANALE_FEED, nullable=False)
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    # Testo opaco del feed (`SUMMARY`), utile all'Host per riconoscere la
    # Prenotazione. NON è un'anagrafica Ospite: l'entità `ospite` arriva con
    # la decisione di prodotto MYL-40, e il VEVENT non porta un'identità
    # affidabile su cui costruirla.
    sommario: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stato: Mapped[StatoPrenotazione] = mapped_column(
        Enum(
            StatoPrenotazione,
            name="stato_prenotazione",
            values_callable=lambda e: [s.value for s in e],
        ),
        nullable=False,
        default=StatoPrenotazione.ATTIVA,
    )
    creata_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    aggiornata_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    @property
    def soggiorno(self) -> DateRange:
        """Intervallo semiaperto [check_in, check_out) (AD-3)."""
        return DateRange(check_in=self.check_in, check_out=self.check_out)
