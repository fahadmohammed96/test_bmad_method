"""Service di `calendario` (AD-4, AD-18, AD-19).

Due percorsi, deliberatamente separati nel tempo (test design §4.2-1):

- **`collega_feed` è sincrono e non tocca la rete.** Valida il formato
  dell'URL e accoda un job di sync scaduto subito. L'errore inline immediato
  sul campo può parlare solo di ciò che si sa senza uscire: uno schema
  inammissibile, un URL senza host.
- **`esegui_sync` è il job.** Qui si scopre la raggiungibilità, e l'esito
  arriva all'Host come stato del Feed entro il primo run.

L'invariante che governa tutto il resto (E2-G3): la transizione a
`rimossa_dal_feed` si applica **solo** dopo un parse completo e validato.
Un corpo troncato, vuoto o con esito HTTP inatteso produce un `sync_run`
fallito e **nessuna** transizione di stato. Senza questa regola un errore di
trasporto svuoterebbe logicamente il calendario, facendo `decadere` i
Conflitti aperti: probabilità alta, impatto critico, nessun errore visibile.

Nessuna funzione di questo modulo fa `commit` sul percorso del job: la
transazione è del chiamante. Il worker esegue ogni handler dentro un
SAVEPOINT (G-1) e un `commit` interno lo scavalcherebbe.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.calendario import ical, jobs
from app.calendario.models import (
    CanaleFeed,
    CategoriaErroreSync,
    EsitoSyncRun,
    FeedIcal,
    Prenotazione,
    StatoPrenotazione,
    SyncRun,
)
from app.calendario.normalizzazione import (
    EventoFeed,
    EventoNonNormalizzabileError,
    normalizza,
)
from app.calendario.repository import (
    FeedIcalRepository,
    PrenotazioneRepository,
    SyncRunRepository,
)
from app.calendario.schemas import StatoSincronizzazione
from app.calendario.trasporto import (
    ClientFeed,
    ClientFeedHttp,
    ErroreDiTrasporto,
    EsitoHttpInattesoError,
    RispostaTroppoGrandeError,
    TimeoutFeedError,
)
from app.calendario.uscita_rete import (
    PoliticaUscitaRete,
    UrlFeedNonValidoError,
    url_redatto,
    valida_formato,
)
from app.core.config import get_settings
from app.core.date_range import EmptyDateRangeError, utcnow
from app.strutture import service as strutture_service

logger = logging.getLogger(__name__)


class FeedNonTrovatoError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DatiFeed:
    struttura_id: uuid.UUID
    url: str
    canale: CanaleFeed


@dataclass(frozen=True, slots=True)
class StatoFeed:
    """Feed più il suo stato di sincronizzazione, derivato alla lettura."""

    feed: FeedIcal
    stato: StatoSincronizzazione
    ultimo_sync_riuscito_il: datetime | None
    ultimo_tentativo_il: datetime | None
    categoria_errore: CategoriaErroreSync | None
    prenotazioni_attive: int
    prenotazioni_rimosse_dal_feed: int
    eventi_malformati: int
    eventi_ricorrenti_non_espansi: int


@dataclass(frozen=True, slots=True)
class EsitoImport:
    """Contatori di un run, come finiscono nel `sync_run`."""

    importate: int = 0
    aggiornate: int = 0
    rimosse_dal_feed: int = 0
    ricomparse: int = 0
    malformati: int = 0
    ricorrenti_non_espansi: int = 0


def client_di_produzione() -> ClientFeed:
    """Confine di rete configurato dall'ambiente (NFR-4, NFR-17)."""
    return ClientFeedHttp(PoliticaUscitaRete.da_configurazione(get_settings()))


def collega_feed(db: Session, host_id: uuid.UUID, dati: DatiFeed) -> FeedIcal:
    """Collega il Feed e accoda subito il sync. Solleva `UrlFeedNonValidoError`.

    La Struttura si legge dal service di `strutture`, mai dal suo repository:
    `calendario` non conosce le tabelle di un altro modulo (AD-1, AD-18).
    """
    strutture_service.leggi_struttura(db, host_id, dati.struttura_id)
    url = dati.url.strip()
    # Validazione SINCRONA di solo formato: nessun DNS, nessuna connessione.
    # L'errore inline immediato non può dipendere dalla rete.
    valida_formato(url)

    feed = FeedIcalRepository(db).add(
        host_id,
        FeedIcal(struttura_id=dati.struttura_id, url=url, canale=dati.canale),
    )
    db.flush()
    jobs.accoda_sync_immediato(db, feed)
    db.commit()
    return feed


def lista_feed(
    db: Session, host_id: uuid.UUID, struttura_id: uuid.UUID
) -> list[FeedIcal]:
    strutture_service.leggi_struttura(db, host_id, struttura_id)
    return FeedIcalRepository(db).della_struttura(host_id, struttura_id)


def leggi_feed(db: Session, host_id: uuid.UUID, feed_id: uuid.UUID) -> FeedIcal:
    feed = FeedIcalRepository(db).by_id(host_id, feed_id)
    if feed is None:
        raise FeedNonTrovatoError()
    return feed


def ultimo_run(db: Session, host_id: uuid.UUID, feed_id: uuid.UUID) -> SyncRun | None:
    return SyncRunRepository(db).ultimo(host_id, feed_id)


def ultimo_run_riuscito(
    db: Session, host_id: uuid.UUID, feed_id: uuid.UUID
) -> SyncRun | None:
    """Sorgente unica di «dati aggiornati alle HH:MM» (NFR-2).

    Deriva dal `sync_run`, non da un campo mantenuto a parte: un timestamp
    duplicato è un timestamp che prima o poi avanza su un run fallito.
    """
    return SyncRunRepository(db).ultimo_riuscito(host_id, feed_id)


def prenotazioni_del_feed(
    db: Session, host_id: uuid.UUID, feed_id: uuid.UUID
) -> list[Prenotazione]:
    return PrenotazioneRepository(db).del_feed(host_id, feed_id)


def stato_del_feed(db: Session, host_id: uuid.UUID, feed: FeedIcal) -> StatoFeed:
    """Stato di sincronizzazione DERIVATO alla lettura (NFR-2, AD-14).

    Non esiste una colonna «ultimo sync riuscito» da tenere allineata: la
    verità è la traccia append-only dei `sync_run`, e qui si legge.
    """
    run = SyncRunRepository(db)
    ultimo = run.ultimo(host_id, feed.id)
    riuscito = run.ultimo_riuscito(host_id, feed.id)
    conteggi = PrenotazioneRepository(db).conta_per_stato(host_id, feed.id)

    if ultimo is None:
        in_coda = FeedIcalRepository(db).sync_in_coda(
            host_id, feed.id, tipo_job=jobs.TIPO_JOB_SYNC_FEED
        )
        stato = (
            StatoSincronizzazione.IN_CORSO
            if in_coda
            else StatoSincronizzazione.MAI_SINCRONIZZATO
        )
    elif ultimo.esito is EsitoSyncRun.RIUSCITO:
        stato = StatoSincronizzazione.RIUSCITO
    else:
        stato = StatoSincronizzazione.FALLITO

    return StatoFeed(
        feed=feed,
        stato=stato,
        ultimo_sync_riuscito_il=None if riuscito is None else riuscito.concluso_il,
        ultimo_tentativo_il=None if ultimo is None else ultimo.concluso_il,
        categoria_errore=None if ultimo is None else ultimo.categoria_errore,
        prenotazioni_attive=conteggi.get(StatoPrenotazione.ATTIVA, 0),
        prenotazioni_rimosse_dal_feed=conteggi.get(
            StatoPrenotazione.RIMOSSA_DAL_FEED, 0
        ),
        eventi_malformati=0 if riuscito is None else riuscito.eventi_malformati,
        eventi_ricorrenti_non_espansi=(
            0 if riuscito is None else riuscito.eventi_ricorrenti_non_espansi
        ),
    )


def _categoria(errore: ErroreDiTrasporto) -> CategoriaErroreSync:
    if isinstance(errore, TimeoutFeedError):
        return CategoriaErroreSync.TIMEOUT
    if isinstance(errore, RispostaTroppoGrandeError):
        return CategoriaErroreSync.RISPOSTA_TROPPO_GRANDE
    if isinstance(errore, EsitoHttpInattesoError):
        return CategoriaErroreSync.ESITO_HTTP_INATTESO
    return CategoriaErroreSync.URL_NON_RAGGIUNGIBILE


def _scrivi_run(
    db: Session,
    feed: FeedIcal,
    *,
    iniziato_il: datetime,
    esito: EsitoSyncRun,
    categoria: CategoriaErroreSync | None = None,
    conteggi: EsitoImport | None = None,
) -> SyncRun:
    contatori = conteggi or EsitoImport()
    run = SyncRunRepository(db).add(
        feed.host_id,
        SyncRun(
            feed_id=feed.id,
            esito=esito,
            categoria_errore=categoria,
            prenotazioni_importate=contatori.importate,
            prenotazioni_aggiornate=contatori.aggiornate,
            prenotazioni_rimosse_dal_feed=contatori.rimosse_dal_feed,
            prenotazioni_ricomparse=contatori.ricomparse,
            eventi_malformati=contatori.malformati,
            eventi_ricorrenti_non_espansi=contatori.ricorrenti_non_espansi,
            iniziato_il=iniziato_il,
            concluso_il=utcnow(),
        ),
    )
    db.flush()
    return run


def esegui_sync(
    db: Session,
    host_id: uuid.UUID,
    feed_id: uuid.UUID,
    *,
    client: ClientFeed | None = None,
) -> SyncRun:
    """Un run di sincronizzazione. Scrive SEMPRE un `sync_run`.

    Non solleva sugli errori di feed o di rete: li registra. Un run fallito
    che non lascia traccia renderebbe «non sincronizzo da tre giorni»
    indistinguibile da «non ci sono novità» (NFR-2), e il SAVEPOINT per item
    del worker (G-1) annullerebbe la scrittura insieme all'eccezione.
    """
    trasporto = client if client is not None else client_di_produzione()
    feed = leggi_feed(db, host_id, feed_id)
    iniziato_il = utcnow()

    try:
        risposta = trasporto.scarica(feed.url)
    except ErroreDiTrasporto as exc:
        logger.warning(
            "sync del feed fallito nel trasporto",
            extra={"feed_id": str(feed.id), "url": url_redatto(feed.url)},
        )
        return _scrivi_run(
            db,
            feed,
            iniziato_il=iniziato_il,
            esito=EsitoSyncRun.FALLITO,
            categoria=_categoria(exc),
        )

    try:
        analizzato = ical.analizza_feed(risposta.corpo)
    except ical.FeedNonValidoError:
        # E2-G3: il corpo non è un calendario completo. NESSUNA transizione.
        logger.warning(
            "sync del feed fallito: corpo non valido", extra={"feed_id": str(feed.id)}
        )
        return _scrivi_run(
            db,
            feed,
            iniziato_il=iniziato_il,
            esito=EsitoSyncRun.FALLITO,
            categoria=CategoriaErroreSync.FEED_NON_VALIDO,
        )

    if not analizzato.eventi:
        # Un calendario chiuso ma senza eventi è indistinguibile da un export
        # andato male, e il costo dei due errori non è simmetrico: trattarlo
        # come «tutto scomparso» svuoterebbe il calendario, mentre trattarlo
        # come run fallito costa un errore visibile su un Feed che davvero
        # non ha prenotazioni. Si sceglie il secondo.
        return _scrivi_run(
            db,
            feed,
            iniziato_il=iniziato_il,
            esito=EsitoSyncRun.FALLITO,
            categoria=CategoriaErroreSync.FEED_SENZA_EVENTI,
        )

    return _scrivi_run(
        db,
        feed,
        iniziato_il=iniziato_il,
        esito=EsitoSyncRun.RIUSCITO,
        conteggi=_riconcilia(db, feed, analizzato),
    )


def _riconcilia(
    db: Session, feed: FeedIcal, analizzato: ical.FeedAnalizzato
) -> EsitoImport:
    """Upsert degli eventi e transizione degli scomparsi. Mai una DELETE."""
    prenotazioni = PrenotazioneRepository(db)
    importate = aggiornate = ricomparse = malformati = ricorrenti = 0
    # TUTTI gli uid letti dal feed, compresi quelli di eventi che non si
    # normalizzano: un evento malformato è comunque presente nel feed, e
    # trattarlo come scomparso marcherebbe `rimossa_dal_feed` una
    # Prenotazione viva.
    uid_presenti: list[str] = []

    for vevent in analizzato.eventi:
        if vevent.uid is not None:
            uid_presenti.append(vevent.uid)
        try:
            evento = normalizza(vevent)
        except (EventoNonNormalizzabileError, EmptyDateRangeError) as exc:
            malformati += 1
            logger.info(
                "VEVENT non normalizzabile: registrato come malformato",
                extra={"feed_id": str(feed.id), "motivo": type(exc).__name__},
            )
            continue
        if evento.ricorrente:
            ricorrenti += 1
        esito = _upsert(prenotazioni, feed, evento)
        if esito == "importata":
            importate += 1
        elif esito == "ricomparsa":
            ricomparse += 1
        else:
            aggiornate += 1

    rimosse = prenotazioni.marca_rimosse_dal_feed(
        feed.host_id, feed_id=feed.id, uid_presenti=uid_presenti
    )
    logger.info(
        "sync del feed concluso",
        extra={
            "feed_id": str(feed.id),
            "importate": importate,
            "aggiornate": aggiornate,
            "rimosse_dal_feed": rimosse,
        },
    )
    return EsitoImport(
        importate=importate,
        aggiornate=aggiornate,
        rimosse_dal_feed=rimosse,
        ricomparse=ricomparse,
        malformati=malformati,
        ricorrenti_non_espansi=ricorrenti,
    )


def _upsert(
    prenotazioni: PrenotazioneRepository, feed: FeedIcal, evento: EventoFeed
) -> str:
    return prenotazioni.upsert_dal_feed(
        feed.host_id,
        feed_id=feed.id,
        struttura_id=feed.struttura_id,
        canale=feed.canale,
        ical_uid=evento.ical_uid,
        check_in=evento.soggiorno.check_in,
        check_out=evento.soggiorno.check_out,
        sommario=evento.sommario,
        cancellata=evento.cancellato,
    )


__all__ = [
    "DatiFeed",
    "EsitoImport",
    "FeedNonTrovatoError",
    "StatoFeed",
    "UrlFeedNonValidoError",
    "client_di_produzione",
    "collega_feed",
    "esegui_sync",
    "leggi_feed",
    "lista_feed",
    "prenotazioni_del_feed",
    "stato_del_feed",
    "ultimo_run",
    "ultimo_run_riuscito",
]
