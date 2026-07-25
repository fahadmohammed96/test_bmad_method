"""Service di `strutture` (AD-12, AD-18, AD-20).

Il cap "max N attive" è imposto QUI, unico punto; è il cap di prodotto del
pilota, distinto dalla soglia fiscale (config_normativa, Story 1.6).
Le mutazioni emettono eventi outbox nella stessa transazione (AD-1).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config_normativa import service as config_service
from app.config_normativa.repository import AnagraficaRepository
from app.core.config import get_settings
from app.core.date_range import today_rome
from app.core.outbox import emit
from app.strutture.models import StatoStruttura, Struttura
from app.strutture.regime_fiscale import RegimeFiscale, calcola_regime, oltre_soglia
from app.strutture.repository import RegimeLetturaRepository, StrutturaRepository


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


def _emetti_transizione_regime(
    db: Session, host_id: uuid.UUID, conteggio_prima: int, conteggio_dopo: int
) -> None:
    """Evento alla transizione di soglia fiscale (FR-17, AD-12).

    Solo l'attraversamento produce un evento: restare sopra o sotto la
    soglia non ne genera. Senza parametri configurati non si inventa una
    soglia, quindi non si emette nulla.
    """
    parametri = config_service.parametri_fiscali_vigenti(db, today_rome())
    if parametri is None:
        return
    prima = oltre_soglia(conteggio_prima, parametri)
    dopo = oltre_soglia(conteggio_dopo, parametri)
    if prima == dopo:
        return
    payload = {"host_id": str(host_id), "conteggio": conteggio_dopo}
    if dopo:
        emit(db, "regime_fiscale.soglia_superata", payload)
    else:
        emit(db, "regime_fiscale.rientrato", payload)
        RegimeLetturaRepository(db).azzera(host_id)


def crea_struttura(db: Session, host_id: uuid.UUID, dati: DatiStruttura) -> Struttura:
    repo = StrutturaRepository(db)
    conteggio_prima = repo.conta_attive(host_id)
    if conteggio_prima >= get_settings().max_strutture_attive:
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
    _emetti_transizione_regime(db, host_id, conteggio_prima, conteggio_prima + 1)
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
    conteggio_prima = StrutturaRepository(db).conta_attive(host_id)
    struttura.stato = StatoStruttura.ARCHIVIATA
    emit(db, "struttura.archiviata", _payload(struttura))
    _emetti_transizione_regime(db, host_id, conteggio_prima, conteggio_prima - 1)
    db.commit()
    return struttura


def regime_fiscale(db: Session, host_id: uuid.UUID) -> RegimeFiscale:
    """Regime derivato alla lettura (AD-12): unico punto di verità."""
    return calcola_regime(
        db,
        host_id,
        alla_data=today_rome(),
        lettura_confermata=RegimeLetturaRepository(db).confermata(host_id),
    )


def conferma_lettura_regime(db: Session, host_id: uuid.UUID) -> None:
    conteggio = StrutturaRepository(db).conta_attive(host_id)
    RegimeLetturaRepository(db).conferma(host_id, conteggio)
    db.commit()
