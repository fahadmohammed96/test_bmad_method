"""Service di `strutture` (AD-12, AD-18, AD-20).

Il cap "max N attive" è imposto QUI, unico punto; è il cap di prodotto del
pilota, distinto dalla soglia fiscale (config_normativa, Story 1.6).
Le mutazioni emettono eventi outbox nella stessa transazione (AD-1).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.outbox import emit
from app.strutture.models import StatoStruttura, Struttura
from app.strutture.repository import StrutturaRepository


class CapStruttureAttiveError(Exception):
    """Il pilota copre da 1 a 3 Strutture attive per Host (FR-1)."""


class StrutturaNonTrovataError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DatiStruttura:
    nome: str
    comune: str
    regione: str
    cin: str | None = None


def _payload(struttura: Struttura) -> dict[str, str]:
    return {"struttura_id": str(struttura.id), "host_id": str(struttura.host_id)}


def crea_struttura(db: Session, host_id: uuid.UUID, dati: DatiStruttura) -> Struttura:
    repo = StrutturaRepository(db)
    if repo.conta_attive(host_id) >= get_settings().max_strutture_attive:
        raise CapStruttureAttiveError()
    struttura = repo.add(
        host_id,
        Struttura(
            nome=dati.nome, comune=dati.comune, regione=dati.regione, cin=dati.cin
        ),
    )
    db.flush()
    emit(db, "struttura.creata", _payload(struttura))
    db.commit()
    return struttura


def lista_strutture(db: Session, host_id: uuid.UUID) -> list[Struttura]:
    return StrutturaRepository(db).lista(host_id)


def _carica(db: Session, host_id: uuid.UUID, struttura_id: uuid.UUID) -> Struttura:
    struttura = StrutturaRepository(db).by_id(host_id, struttura_id)
    if struttura is None:
        raise StrutturaNonTrovataError()
    return struttura


def aggiorna_struttura(
    db: Session,
    host_id: uuid.UUID,
    struttura_id: uuid.UUID,
    modifiche: dict[str, str | None],
) -> Struttura:
    struttura = _carica(db, host_id, struttura_id)
    for campo in ("nome", "comune", "regione", "cin"):
        if campo in modifiche:
            setattr(struttura, campo, modifiche[campo])
    db.commit()
    return struttura


def archivia_struttura(
    db: Session, host_id: uuid.UUID, struttura_id: uuid.UUID
) -> Struttura:
    struttura = _carica(db, host_id, struttura_id)
    if struttura.stato is StatoStruttura.ARCHIVIATA:
        return struttura  # idempotente: archiviata resta archiviata (AD-20)
    struttura.stato = StatoStruttura.ARCHIVIATA
    emit(db, "struttura.archiviata", _payload(struttura))
    db.commit()
    return struttura
