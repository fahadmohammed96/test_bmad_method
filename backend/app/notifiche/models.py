"""Entità di `notifiche` (AD-2, AD-10, AD-13).

Due tabelle, entrambe tenant-owned:

- `notifica` — **il fatto**: a questo Host, per questo riferimento, è dovuta
  una notifica di questo tipo. La sua identità `(host_id, tipo,
  riferimento_id)` è imposta da un UNIQUE del database, ed è il punto in cui
  «è già stata notificata?» smette di essere una domanda applicativa: alla
  prima rilevazione di un Conflitto la riga si crea, alle successive
  l'`INSERT` non tocca nulla. Sotto concorrenza il codice perde (gara A3-5).
- `notifica_consegna` — **il tentativo su un canale**. Una riga per canale
  scelto, con lo stato che il job fa avanzare. È qui che vive l'idempotenza
  del ritentativo: la transizione a `inviata` è condizionata allo stato
  DENTRO la `UPDATE`, quindi otto esecuzioni concorrenti dello stesso job
  producono un solo invio.

**Il testo si scrive alla consegna, non alla richiesta** (AC 6): `oggetto` e
`corpo` sono `NULL` finché il canale non è stato servito, e si compongono
leggendo lo stato corrente. Il payload dell'evento e del job porta soli
identificatori: `outbox` e `job` sono append-only e sopravvivono alla
retention di AD-21, quindi un testo congelato lì — «Possibile doppia
prenotazione — Mario Rossi, 15-17 agosto» — sopravviverebbe all'azzeramento
dell'anagrafica che quella retention impone (AD-16, AD-17, NFR-11).

Il testo che finisce QUI non porta dati dell'Ospite per costruzione: contiene
Struttura e intervallo di date (AC 9), che non sono anagrafica.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.date_range import utcnow
from app.core.db import Base, new_uuid7


class CanaleConsegna(enum.Enum):
    """I canali dell'MVP (AD-13): in-app ed email.

    Vocabolario PROPRIO di questo modulo, non l'enum di `identity`. La
    preferenza dell'Host è una colonna di `host` e vive in `identity` (FR-20,
    Story 1.3); riusarne il tipo qui legherebbe lo schema di due moduli — e
    `notifiche` è il modulo che l'Epic 3 e l'Epic 5 devono poter riusare senza
    trascinarsi dietro il resto. Che i due vocabolari restino allineati è una
    proprietà sorvegliata (`tests/test_notifiche_preferenze.py`): se `identity`
    ne aggiunge uno, questo modulo deve saperlo — un canale preferito che qui
    non esiste sarebbe una preferenza ignorata in silenzio.
    """

    IN_APP = "in_app"
    EMAIL = "email"


class StatoConsegna(enum.Enum):
    """`in_attesa` finché un esito reale non c'è stato (stessa famiglia di AD-8).

    Non esiste uno stato «tentata»: un tentativo che non è arrivato a
    destinazione lascia la riga esattamente dov'era, e a raccontare il
    fallimento è il job — che resta ritentabile e, esauriti i tentativi,
    `failed` con il suo `last_error`. Uno stato di successo si scrive solo
    quando il canale ha risposto.
    """

    IN_ATTESA = "in_attesa"
    INVIATA = "inviata"


class Notifica(Base):
    """Una notifica dovuta all'Host, identificata dal fatto che l'ha generata."""

    __tablename__ = "notifica"
    __table_args__ = (
        # L'identità della notifica, imposta dal DATABASE. «Alla PRIMA
        # rilevazione, non a ogni sync» (AC 2) è un check-then-write: due
        # consegne concorrenti di `conflitto.rilevato`, o un secondo sync che
        # rileva lo stesso Conflitto, passerebbero entrambe un controllo
        # applicativo. Qui la seconda `INSERT` non tocca niente.
        #
        # UNIQUE PIENO e non parziale, al contrario di `conflitto`: lì la
        # stessa coppia può tornare a sovrapporsi e un secondo Conflitto è
        # legittimo; qui il riferimento È il Conflitto, che è già unico.
        UniqueConstraint(
            "host_id", "tipo", "riferimento_id", name="uq_notifica_per_riferimento"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("host.id"), nullable=False, index=True
    )
    # Stringa a catalogo, come `job.job_type` e `outbox.event_name`: un enum
    # elencherebbe qui i domini chiamanti, che è precisamente ciò che questo
    # modulo non deve sapere per essere riusabile (AC 11). A validarla è il
    # registro dei compositori, che rifiuta un tipo senza testo (AD-17).
    tipo: Mapped[str] = mapped_column(String(200), nullable=False)
    # L'entità di dominio a cui la notifica si riferisce — qui il Conflitto.
    # SENZA FK: una FK verso `conflitto` legherebbe lo schema di `notifiche`
    # a quello di `calendario` (AD-1), e il riferimento dell'Epic 3 sarà un
    # Adempimento. L'integrità la dà il compositore, che rilegge lo stato
    # corrente e alla consegna sa dire se il fatto esiste ancora.
    riferimento_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    creata_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class NotificaConsegna(Base):
    """Il tentativo di consegna su UN canale: una riga, un job, un esito."""

    __tablename__ = "notifica_consegna"
    __table_args__ = (
        # Un canale servito una volta sola per notifica. È il vincolo che
        # rende impossibile la seconda email allo stesso Host per lo stesso
        # fatto anche se la richiesta viene rieseguita.
        UniqueConstraint(
            "notifica_id", "canale", name="uq_notifica_consegna_per_canale"
        ),
        # Nessuno stato di successo senza il suo istante, e nessun istante
        # senza lo stato: l'implicazione vale nei due sensi, come per
        # `conflitto.decaduto_il`. Una consegna «inviata» senza quando è un
        # invio dichiarato e non databile.
        CheckConstraint(
            "(stato = 'inviata') = (inviata_il IS NOT NULL)",
            name="ck_notifica_consegna_inviata_ha_istante",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("host.id"), nullable=False, index=True
    )
    notifica_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notifica.id"), nullable=False, index=True
    )
    canale: Mapped[CanaleConsegna] = mapped_column(
        Enum(
            CanaleConsegna,
            name="canale_consegna",
            values_callable=lambda e: [c.value for c in e],
        ),
        nullable=False,
    )
    stato: Mapped[StatoConsegna] = mapped_column(
        Enum(
            StatoConsegna,
            name="stato_consegna",
            values_callable=lambda e: [s.value for s in e],
        ),
        nullable=False,
        default=StatoConsegna.IN_ATTESA,
    )
    # Il testo REALMENTE consegnato, scritto nello stesso istante dell'invio.
    # È l'evidenza di cosa ha letto l'Host e, per il canale in-app, è la
    # notifica stessa.
    oggetto: Mapped[str | None] = mapped_column(String(300), nullable=True)
    corpo: Mapped[str | None] = mapped_column(Text, nullable=True)
    inviata_il: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    creata_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
