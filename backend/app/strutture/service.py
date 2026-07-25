"""Service di `strutture` (AD-12, AD-18, AD-20).

Il cap "max N attive" è imposto QUI, unico punto; è il cap di prodotto del
pilota, distinto dalla soglia fiscale (config_normativa, Story 1.6).
Le mutazioni emettono eventi outbox nella stessa transazione (AD-1).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config_normativa.repository import AnagraficaRepository
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
    comune_codice_istat: str | None = None


def _risolvi_anagrafica(
    db: Session, comune_codice_istat: str | None, regione_nome: str
) -> tuple[str | None, str | None]:
    """Codici ISTAT di Comune e Regione, quando riconoscibili (AD-9).

    Il Comune arriva dall'anagrafica (l'Host lo sceglie dai suggerimenti);
    la Regione si deriva dal Comune, o dal nome scelto nell'elenco. Un
    luogo non riconosciuto lascia i codici a None: la configurazione
    degraderà in sicurezza, senza bloccare la registrazione.
    """
    anagrafica = AnagraficaRepository(db)
    if comune_codice_istat:
        comune = anagrafica.comune_by_codice(comune_codice_istat)
        if comune is not None:
            return comune.codice_istat, comune.regione_codice_istat
    regione = anagrafica.regione_by_nome(regione_nome)
    return None, regione.codice_istat if regione else None


def _payload(struttura: Struttura) -> dict[str, str]:
    return {"struttura_id": str(struttura.id), "host_id": str(struttura.host_id)}


def crea_struttura(db: Session, host_id: uuid.UUID, dati: DatiStruttura) -> Struttura:
    repo = StrutturaRepository(db)
    if repo.conta_attive(host_id) >= get_settings().max_strutture_attive:
        raise CapStruttureAttiveError()
    comune_codice, regione_codice = _risolvi_anagrafica(
        db, dati.comune_codice_istat, dati.regione
    )
    struttura = repo.add(
        host_id,
        Struttura(
            nome=dati.nome,
            comune=dati.comune,
            comune_codice_istat=comune_codice,
            regione=dati.regione,
            regione_codice_istat=regione_codice,
            cin=dati.cin,
        ),
    )
    db.flush()
    emit(db, "struttura.creata", _payload(struttura))
    db.commit()
    return struttura


def lista_strutture(db: Session, host_id: uuid.UUID) -> list[Struttura]:
    return StrutturaRepository(db).lista(host_id)


def leggi_struttura(
    db: Session, host_id: uuid.UUID, struttura_id: uuid.UUID
) -> Struttura:
    return _carica(db, host_id, struttura_id)


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
    if {"comune", "comune_codice_istat", "regione"} & modifiche.keys():
        # Cambiare Comune/Regione ricarica la configurazione applicabile
        # (FR-2): si aggiorna il legame all'anagrafica, mai una copia dei
        # parametri — così lo storico dei versamenti resta leggibile.
        struttura.comune_codice_istat, struttura.regione_codice_istat = (
            _risolvi_anagrafica(
                db,
                modifiche.get("comune_codice_istat"),
                struttura.regione,
            )
        )
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
