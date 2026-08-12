"""Endpoint di `calendario` (FR-3, FR-4): /api/v1/feed-ical e /api/v1/calendario.

Ogni rotta dichiara `CurrentHost`: `host_id` si risolve dalla sessione, mai
da input del client (AD-15), e la guardia `tests/test_auth_convention.py` lo
impone. È anche il solo presidio di NFR-14 che regge per costruzione: il
calendario di un Host non può mostrare le Prenotazioni di un altro perché
non c'è un parametro con cui chiederle.

Un URL non valido è un **422 inline sul campo**: si scopre senza toccare la
rete. La raggiungibilità no — quella si scopre nel job, e arriva qui come
`stato_sync` del Feed (test design §4.2-1).
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.problems import DomainProblem
from app.calendario import service
from app.calendario.models import FeedIcal, Prenotazione
from app.calendario.schemas import (
    AzzeramentoInput,
    AzzeramentoOutput,
    CalendarioOutput,
    ConflittiOutput,
    ConflittoOutput,
    FeedIcalInput,
    FeedIcalOutput,
    PrenotazioneInConflittoOutput,
    PrenotazioneManualeInput,
    PrenotazioneManualeOutput,
    PrenotazioneOutput,
    PrenotazioniDelFeedOutput,
    StrutturaDelCalendarioOutput,
    VoceCalendarioOutput,
)
from app.calendario.uscita_rete import url_redatto

# La dipendenza del token di servizio si importa dal modulo che la possiede,
# come `CurrentHost` da `identity`: sono le due sole protezioni ammesse dalla
# guardia `tests/test_auth_convention.py`, e duplicarne una qui darebbe due
# controlli da tenere allineati.
from app.config_normativa.deps import AdminToken
from app.core.date_range import EmptyDateRangeError
from app.core.db import get_db
from app.identity.deps import CurrentHost
from app.identity.service import HostNonTrovatoError
from app.strutture.service import StrutturaArchiviataError, StrutturaNonTrovataError

router = APIRouter(prefix="/feed-ical", tags=["calendario"])
calendario_router = APIRouter(prefix="/calendario", tags=["calendario"])
# I Conflitti hanno una rotta propria e non un sotto-percorso del calendario:
# sono l'entità su cui la Dashboard (2.8) e la Finestra di riconciliazione
# (2.7) lavoreranno, e annidarli sotto la griglia legherebbe due superfici
# che cambiano per ragioni diverse.
conflitti_router = APIRouter(prefix="/conflitti", tags=["calendario"])
# Endpoint di servizio, non esposti all'Host finale: la cancellazione su
# richiesta GDPR (NFR-15) arriva oggi come istanza al titolare, non come
# bottone nell'app. Vivono sotto `/interno` come quelli di `config_normativa`,
# quindi dietro il token di servizio e con audit chi/cosa/quando (AD-9).
interno_router = APIRouter(prefix="/interno", tags=["calendario"])

DbSession = Annotated[Session, Depends(get_db)]

# Tetto sull'ampiezza del periodo richiedibile in una volta. Non è una
# preferenza di prodotto: è il bound su una query il cui costo cresce con
# l'intervallo, e senza di esso `da=0001-01-01&a=9999-12-31` è una lettura
# dell'intera tabella scritta da un client qualsiasi.
GIORNI_MASSIMI_PERIODO = 366


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
        fallimenti_consecutivi=stato.fallimenti_consecutivi,
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
) -> PrenotazioniDelFeedOutput:
    """Prenotazioni importate dal Feed, comprese quelle non più attive.

    Una Prenotazione uscita da `attiva` resta visibile: farla sparire senza
    traccia contraddirebbe «archiviare, mai distruggere» agli occhi dell'Host
    (AD-20).

    La risposta porta con sé lo stato di sincronizzazione e l'orario
    dell'ultimo sync riuscito: questa è una superficie che mostra dati da
    Feed, e UX-DR6 vuole «dati aggiornati alle HH:MM» su ognuna. La guardia
    `tests/test_superfici_feed_convention.py` (GS-7) impone che resti vero
    anche per le superfici che non esistono ancora.
    """
    try:
        feed = service.leggi_feed(db, host.id, feed_id)
    except service.FeedNonTrovatoError:
        raise _feed_non_trovato() from None
    stato = service.stato_del_feed(db, host.id, feed)
    return PrenotazioniDelFeedOutput(
        stato_sync=stato.stato,
        ultimo_sync_riuscito_il=stato.ultimo_sync_riuscito_il,
        prenotazioni=[
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
        ],
    )


@interno_router.post("/host/{host_id}/ospiti/{ospite_id}/azzeramento")
def azzera_ospite(
    host_id: uuid.UUID,
    ospite_id: uuid.UUID,
    dati: AzzeramentoInput,
    db: DbSession,
    _: AdminToken,
) -> AzzeramentoOutput:
    """Azzera i campi personali di UN Ospite su richiesta (NFR-15, AD-21).

    Riusa la procedura del job di retention: cambia la selezione, non
    l'azzeramento. Mai una `DELETE` — sarebbe una quarta forma distruttiva
    fuori dalla lista esaustiva di AD-20, e GS-6 la fermerebbe.

    L'Ospite sta sotto il suo Host anche nel percorso: la tenancy di un
    endpoint senza sessione deve essere scritta da qualche parte, e il
    percorso è il posto in cui si vede (AD-2).
    """
    try:
        esito = service.azzera_ospite_su_richiesta(
            db, host_id, ospite_id, attore=dati.attore
        )
    except service.OspiteNonTrovatoError:
        raise DomainProblem(
            status=404,
            title="Ospite non trovato",
            type_slug="ospite-not-found",
        ) from None
    return _azzeramento_in_uscita(esito)


@interno_router.post("/host/{host_id}/azzeramento-ospiti")
def azzera_ospiti_dell_host(
    host_id: uuid.UUID,
    dati: AzzeramentoInput,
    db: DbSession,
    _: AdminToken,
) -> AzzeramentoOutput:
    """Azzera i campi personali di TUTTI gli Ospiti di un Host (NFR-15).

    Resta dentro il perimetro di quell'Host (AD-2): non esiste una forma
    «tutti gli Host», e non è una dimenticanza.
    """
    try:
        esito = service.azzera_ospiti_dell_host_su_richiesta(
            db, host_id, attore=dati.attore
        )
    except HostNonTrovatoError:
        raise DomainProblem(
            status=404,
            title="Host non trovato",
            type_slug="host-not-found",
        ) from None
    return _azzeramento_in_uscita(esito)


def _azzeramento_in_uscita(
    esito: service.EsitoAzzeramentoSuRichiesta,
) -> AzzeramentoOutput:
    return AzzeramentoOutput(
        ambito=esito.ambito,
        riferimento=esito.riferimento,
        anagrafiche_azzerate=esito.anagrafiche_azzerate,
        sommari_azzerati=esito.sommari_azzerati,
        eseguito_il=esito.eseguito_il,
    )


def _struttura_archiviata() -> DomainProblem:
    return DomainProblem(
        status=422,
        title="Struttura archiviata",
        type_slug="struttura-archiviata",
        detail=(
            "Questa Struttura è archiviata e non accetta nuove prenotazioni. "
            "Le prenotazioni già registrate restano visibili."
        ),
    )


def _prenotazione_in_uscita(
    db: Session, host_id: uuid.UUID, prenotazione: Prenotazione
) -> PrenotazioneManualeOutput:
    """La Prenotazione manuale con i suoi valori DERIVATI dal server (AD-14).

    `ospite_principale` si rilegge dal service invece di essere costruito dal
    payload d'ingresso: è l'unico modo per cui la risposta descriva ciò che è
    stato scritto e non ciò che era stato chiesto — e la differenza fra le due
    cose è precisamente dove vive il difetto (un campo normalizzato a `None`,
    un'anagrafica non creata).
    """
    ospiti = service.ospiti_della_prenotazione(db, host_id, prenotazione.id)
    principale = next((ospite for ospite in ospiti if ospite.principale), None)
    return PrenotazioneManualeOutput(
        id=prenotazione.id,
        struttura_id=prenotazione.struttura_id,
        canale=prenotazione.canale,
        check_in=prenotazione.check_in,
        check_out=prenotazione.check_out,
        notti=prenotazione.soggiorno.nights,
        sommario=prenotazione.sommario,
        stato=prenotazione.stato,
        ospite_principale=None if principale is None else principale.nome,
    )


@calendario_router.post("/prenotazioni", status_code=201)
def crea_prenotazione(
    dati: PrenotazioneManualeInput, db: DbSession, host: CurrentHost
) -> PrenotazioneManualeOutput:
    """Inserisce una Prenotazione manuale — diretta o blocco date (FR-7).

    `struttura_id` arriva dal client, `host_id` dalla sessione (AD-15): la
    Struttura si risolve nel perimetro dell'Host, quindi quella di un altro
    Host è un 404 e non una fuga.
    """
    try:
        prenotazione = service.crea_prenotazione_manuale(
            db,
            host.id,
            service.DatiPrenotazioneManuale(
                struttura_id=dati.struttura_id,
                check_in=dati.check_in,
                check_out=dati.check_out,
                sommario=dati.sommario,
                ospite=(
                    None
                    if dati.ospite is None
                    else service.DatiOspite(
                        nome=dati.ospite.nome,
                        email=dati.ospite.email,
                        telefono=dati.ospite.telefono,
                    )
                ),
            ),
        )
    except StrutturaNonTrovataError:
        raise _struttura_non_trovata() from None
    except StrutturaArchiviataError:
        raise _struttura_archiviata() from None
    except EmptyDateRangeError:
        # Il confine dell'intervallo semiaperto `[check_in, check_out)` (AD-3):
        # un soggiorno di zero notti non è una prenotazione. 422 inline sul
        # campo, mai un 500 — l'Host ha sbagliato una data, non il sistema.
        raise DomainProblem(
            status=422,
            title="Periodo non valido",
            type_slug="periodo-prenotazione-non-valido",
            detail=(
                "La data di partenza deve essere successiva a quella di "
                "arrivo: una prenotazione dura almeno una notte."
            ),
        ) from None
    return _prenotazione_in_uscita(db, host.id, prenotazione)


@calendario_router.post("/prenotazioni/{prenotazione_id}/cancellazione")
def cancella_prenotazione(
    prenotazione_id: uuid.UUID, db: DbSession, host: CurrentHost
) -> PrenotazioneManualeOutput:
    """Porta una Prenotazione manuale a `cancellata` (AD-19, AD-20).

    **`POST /cancellazione` e non `DELETE`**, e non è una preferenza di stile:
    il verbo dell'API dichiara cosa succede al dato. Qui non si cancella nulla
    — si registra un fatto, la riga resta con la sua storia e continua a
    comparire in griglia con la sua etichetta. Un `DELETE` inviterebbe il
    prossimo a implementarlo davvero, che è la quarta cancellazione distruttiva
    che AD-20 non ammette.

    Idempotente: cancellare due volte risponde `200` con lo stesso stato e non
    emette un secondo evento.
    """
    try:
        prenotazione = service.cancella_prenotazione(db, host.id, prenotazione_id)
    except service.PrenotazioneNonTrovataError:
        raise DomainProblem(
            status=404,
            title="Prenotazione non trovata",
            type_slug="prenotazione-not-found",
        ) from None
    except service.PrenotazioneNonManualeError:
        raise DomainProblem(
            status=422,
            title="Prenotazione non inserita a mano",
            type_slug="prenotazione-non-manuale",
            detail=(
                "Questa prenotazione arriva da un portale: annullala nel "
                "portale e la aggiorneremo alla prossima sincronizzazione."
            ),
        ) from None
    return _prenotazione_in_uscita(db, host.id, prenotazione)


@conflitti_router.get("")
def conflitti(
    db: DbSession,
    host: CurrentHost,
    struttura_id: uuid.UUID | None = None,
) -> ConflittiOutput:
    """I Conflitti `rilevato` dell'Host (FR-5, FR-6).

    **Nessun parametro può nasconderne uno.** Non c'è un filtro temporale,
    non c'è una paginazione che tagli la coda, non c'è un `limit`: un
    Conflitto `rilevato` resta in evidenza finché non è gestito, e ogni
    meccanismo che lo faccia sparire da sé è il gemello di AD-8 — il
    prodotto smetterebbe di segnalare una doppia prenotazione che è ancora
    lì. `struttura_id` restringe il PERIMETRO, come il selettore trasversale
    del Calendario (UX-DR1), e non lo stato.

    Lo storico — i Conflitti `gestito` e `decaduto` — non passa di qui: è la
    superficie della Story 2.7, e non si cancella nulla per non averla
    ancora (AD-20).
    """
    try:
        vista = service.conflitti_rilevati(db, host.id, struttura_id=struttura_id)
    except StrutturaNonTrovataError:
        raise _struttura_non_trovata() from None
    return ConflittiOutput(
        stato_sync=vista.stato,
        ultimo_sync_riuscito_il=vista.ultimo_sync_riuscito_il,
        conflitti=[
            ConflittoOutput(
                id=riga.conflitto.id,
                struttura_id=riga.conflitto.struttura_id,
                stato=riga.conflitto.stato,
                rilevato_il=riga.conflitto.rilevato_il,
                prenotazioni=[
                    PrenotazioneInConflittoOutput(
                        id=lato.prenotazione.id,
                        canale=lato.prenotazione.canale,
                        check_in=lato.prenotazione.check_in,
                        check_out=lato.prenotazione.check_out,
                        notti=lato.prenotazione.soggiorno.nights,
                        sommario=lato.prenotazione.sommario,
                        sincronizzata=lato.sincronizzata,
                        aggiornata_il=lato.aggiornata_il,
                    )
                    for lato in riga.prenotazioni
                ],
            )
            for riga in vista.conflitti
        ],
    )


@calendario_router.get("")
def griglia(
    da: date,
    a: date,
    db: DbSession,
    host: CurrentHost,
    struttura_id: uuid.UUID | None = None,
) -> CalendarioOutput:
    """Il calendario unificato di un periodo (FR-4, UJ-1).

    `struttura_id` assente = vista aggregata su tutte le Strutture; presente
    = una sola Struttura. È lo stesso endpoint, ed è il motivo per cui il
    selettore di UX-DR1 filtra senza cambiare schermata: cambia un parametro
    di query, non la superficie.
    """
    if a < da:
        raise DomainProblem(
            status=422,
            title="Periodo non valido",
            type_slug="periodo-calendario-non-valido",
            detail="La data di fine non può precedere quella di inizio.",
        )
    if (a - da).days >= GIORNI_MASSIMI_PERIODO:
        raise DomainProblem(
            status=422,
            title="Periodo troppo ampio",
            type_slug="periodo-calendario-troppo-ampio",
            detail=(
                "Il calendario si consulta al massimo "
                f"{GIORNI_MASSIMI_PERIODO} giorni per volta."
            ),
        )
    try:
        vista = service.calendario(db, host.id, da=da, a=a, struttura_id=struttura_id)
    except StrutturaNonTrovataError:
        raise _struttura_non_trovata() from None
    return CalendarioOutput(
        da=vista.da,
        a=vista.a,
        stato_sync=vista.stato,
        ultimo_sync_riuscito_il=vista.ultimo_sync_riuscito_il,
        feed_collegati=vista.feed_collegati,
        feed_mai_sincronizzati=vista.feed_mai_sincronizzati,
        feed_in_errore=vista.feed_in_errore,
        strutture=[
            StrutturaDelCalendarioOutput(id=riga.id, nome=riga.nome)
            for riga in vista.strutture
        ],
        voci=[
            VoceCalendarioOutput(
                id=voce.prenotazione.id,
                struttura_id=voce.prenotazione.struttura_id,
                canale=voce.prenotazione.canale,
                check_in=voce.prenotazione.check_in,
                check_out=voce.prenotazione.check_out,
                notti=voce.prenotazione.soggiorno.nights,
                sommario=voce.prenotazione.sommario,
                stato=voce.prenotazione.stato,
                ospite_principale=voce.ospite_principale,
                altri_ospiti=voce.altri_ospiti,
            )
            for voce in vista.voci
        ],
    )
