"""Endpoint di `calendario` (FR-3): /api/v1/feed-ical.

Ogni rotta dichiara `CurrentHost`: `host_id` si risolve dalla sessione, mai
da input del client (AD-15), e la guardia `tests/test_auth_convention.py` lo
impone.

Un URL non valido è un **422 inline sul campo**: si scopre senza toccare la
rete. La raggiungibilità no — quella si scopre nel job, e arriva qui come
`stato_sync` del Feed (test design §4.2-1).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.problems import DomainProblem
from app.calendario import service
from app.calendario.models import FeedIcal
from app.calendario.schemas import (
    FeedIcalInput,
    FeedIcalOutput,
    PrenotazioneOutput,
)
from app.calendario.uscita_rete import url_redatto
from app.core.db import get_db
from app.identity.deps import CurrentHost
from app.strutture.service import StrutturaNonTrovataError

router = APIRouter(prefix="/feed-ical", tags=["calendario"])

DbSession = Annotated[Session, Depends(get_db)]


def _struttura_non_trovata() -> DomainProblem:
    return DomainProblem(
        status=404,
        title="Struttura non trovata",
        type_slug="struttura-not-found",
    )


def _feed_non_trovato() -> DomainProblem:
    return DomainProblem(
        status=404,
        title="Feed non trovato",
        type_slug="feed-ical-not-found",
    )


def _in_uscita(db: Session, host_id: uuid.UUID, feed: FeedIcal) -> FeedIcalOutput:
    stato = service.stato_del_feed(db, host_id, feed)
    return FeedIcalOutput(
        id=feed.id,
        struttura_id=feed.struttura_id,
        # Redatto: se l'Host ha incollato credenziali nell'URL non tornano
        # indietro in nessuna risposta (NFR-17).
        url=url_redatto(feed.url),
        canale=feed.canale,
        collegato_il=feed.collegato_il,
        stato_sync=stato.stato,
        ultimo_sync_riuscito_il=stato.ultimo_sync_riuscito_il,
        ultimo_tentativo_il=stato.ultimo_tentativo_il,
        categoria_errore=stato.categoria_errore,
        prenotazioni_attive=stato.prenotazioni_attive,
        prenotazioni_rimosse_dal_feed=stato.prenotazioni_rimosse_dal_feed,
        eventi_malformati=stato.eventi_malformati,
        eventi_ricorrenti_non_espansi=stato.eventi_ricorrenti_non_espansi,
    )


@router.post("", status_code=201)
def collega(dati: FeedIcalInput, db: DbSession, host: CurrentHost) -> FeedIcalOutput:
    """Collega un Feed e accoda subito l'import (AD-4, AD-10)."""
    try:
        feed = service.collega_feed(
            db,
            host.id,
            service.DatiFeed(
                struttura_id=dati.struttura_id, url=dati.url, canale=dati.canale
            ),
        )
    except StrutturaNonTrovataError:
        raise _struttura_non_trovata() from None
    except service.UrlFeedNonValidoError:
        raise DomainProblem(
            status=422,
            title="URL del Feed non valido",
            type_slug="url-feed-non-valido",
            detail=(
                "Incolla l'indirizzo del calendario esportato dal portale: "
                "deve iniziare con http:// o https://."
            ),
        ) from None
    return _in_uscita(db, host.id, feed)


@router.get("")
def lista(
    struttura_id: uuid.UUID, db: DbSession, host: CurrentHost
) -> list[FeedIcalOutput]:
    try:
        feed = service.lista_feed(db, host.id, struttura_id)
    except StrutturaNonTrovataError:
        raise _struttura_non_trovata() from None
    return [_in_uscita(db, host.id, riga) for riga in feed]


@router.get("/{feed_id}")
def dettaglio(feed_id: uuid.UUID, db: DbSession, host: CurrentHost) -> FeedIcalOutput:
    try:
        feed = service.leggi_feed(db, host.id, feed_id)
    except service.FeedNonTrovatoError:
        raise _feed_non_trovato() from None
    return _in_uscita(db, host.id, feed)


@router.get("/{feed_id}/prenotazioni")
def prenotazioni(
    feed_id: uuid.UUID, db: DbSession, host: CurrentHost
) -> list[PrenotazioneOutput]:
    """Prenotazioni importate dal Feed, comprese quelle non più attive.

    Una Prenotazione uscita da `attiva` resta visibile: farla sparire senza
    traccia contraddirebbe «archiviare, mai distruggere» agli occhi dell'Host
    (AD-20).
    """
    try:
        service.leggi_feed(db, host.id, feed_id)
    except service.FeedNonTrovatoError:
        raise _feed_non_trovato() from None
    return [
        PrenotazioneOutput(
            id=riga.id,
            struttura_id=riga.struttura_id,
            canale=riga.canale,
            ical_uid=riga.ical_uid,
            check_in=riga.check_in,
            check_out=riga.check_out,
            notti=riga.soggiorno.nights,
            sommario=riga.sommario,
            stato=riga.stato,
        )
        for riga in service.prenotazioni_del_feed(db, host.id, feed_id)
    ]
