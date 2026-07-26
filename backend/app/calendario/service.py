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
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.calendario import ical, jobs
from app.calendario.intervallo import ParametriIntervallo, intervallo_di_sync
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
    RispostaFeed,
    RispostaTroppoGrandeError,
    TimeoutFeedError,
    Validatori,
)
from app.calendario.uscita_rete import (
    PoliticaUscitaRete,
    UrlFeedNonValidoError,
    url_redatto,
    valida_formato,
)
from app.core.config import get_settings
from app.core.date_range import today_rome, utcnow
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
    # Quante volte di fila il sync è fallito dall'ultimo riuscito (AR-10).
    # È il segnale che distingue «un tentativo andato male» da «questo Feed
    # ha smesso di funzionare», e senza di esso l'Host li vede uguali.
    fallimenti_consecutivi: int
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
    # Il ciclo periodico parte SUBITO col collegamento, non al prossimo
    # riavvio del worker: il bootstrap all'avvio è una rete di sicurezza, e
    # affidargli il primo giro significherebbe che un Feed collegato oggi
    # comincia a risincronizzarsi al prossimo rilascio (AD-10, NFR-1).
    jobs.assicura_sync_periodico(db, feed)
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


def intervallo_prossimo_sync(
    db: Session, host_id: uuid.UUID, feed: FeedIcal
) -> timedelta:
    """Quanto attendere prima del prossimo sync di questo Feed (G3-5).

    Lo stato (il prossimo check-in) si legge qui; la REGOLA sta in
    `intervallo.py` ed è pura. La separazione non è estetica: è ciò che
    permette di provare la regola su tutti i suoi confini senza un database e
    senza attendere quindici minuti.
    """
    impostazioni = get_settings()
    prossimo = PrenotazioneRepository(db).prossimo_check_in(
        host_id, struttura_id=feed.struttura_id, da=today_rome()
    )
    return intervallo_di_sync(
        adesso=utcnow(),
        prossimo_check_in=prossimo,
        parametri=ParametriIntervallo(
            intervallo_minuti=impostazioni.feed_sync_intervallo_minuti,
            intervallo_minimo_minuti=impostazioni.feed_sync_intervallo_minimo_minuti,
            finestra_prossimita_ore=impostazioni.feed_sync_finestra_prossimita_ore,
        ),
    )


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
        fallimenti_consecutivi=run.fallimenti_consecutivi(host_id, feed.id),
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
    non_modificato: bool = False,
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
            non_modificato=non_modificato,
            iniziato_il=iniziato_il,
            concluso_il=utcnow(),
        ),
    )
    # `flush` prima di contare: il run appena scritto DEVE essere fra quelli
    # che l'alert conta, altrimenti la soglia scatterebbe con un giro di
    # ritardo — cioè al fallimento N+1, non all'N.
    db.flush()
    if esito is EsitoSyncRun.FALLITO:
        _valuta_alert_fallimenti(db, feed, categoria)
    return run


def _valuta_alert_fallimenti(
    db: Session, feed: FeedIcal, categoria: CategoriaErroreSync | None
) -> None:
    """Alert interno all'ATTRAVERSAMENTO della soglia (AR-10, NFR-1).

    Solo all'attraversamento, non a ogni fallimento oltre la soglia: un
    portale giù per un giorno produrrebbe novantasei righe identiche, e un
    alert che si ripete è un alert che si impara a ignorare. Il fatto nuovo è
    «questo Feed ha smesso di funzionare», e succede una volta sola per
    guasto — al successivo successo il contatore torna a zero da sé
    (`fallimenti_consecutivi` è derivato) e un nuovo guasto tornerà a
    segnalare.

    L'artefatto è un log strutturato: NFR-7 mappa metriche e canali di alert
    sull'Epic 3, quindi qui non esiste ancora un canale verso cui uscire. Il
    log è il minimo verificabile proposto dal test design (§4.2-9) e non
    pregiudica quella scelta — è un `logger.error` con i campi già pronti per
    essere raccolti.
    """
    soglia = get_settings().feed_sync_fallimenti_per_alert
    consecutivi = SyncRunRepository(db).fallimenti_consecutivi(feed.host_id, feed.id)
    if consecutivi != soglia:
        return
    logger.error(
        "alert: feed non sincronizza da %s tentativi consecutivi",
        consecutivi,
        extra={
            "feed_id": str(feed.id),
            "host_id": str(feed.host_id),
            "struttura_id": str(feed.struttura_id),
            "fallimenti_consecutivi": consecutivi,
            "soglia": soglia,
            "categoria_errore": None if categoria is None else categoria.value,
        },
    )


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
        # Richiesta CONDIZIONALE: se il portale non ha novità risponde 304 e
        # non ritrasmette il calendario (AD-4). I validatori vengono da
        # `feed`, cioè dall'ultimo import davvero riconciliato — mai da un run
        # fallito, altrimenti chiederemmo «è cambiato rispetto a una cosa che
        # non abbiamo?» e ci sentiremmo rispondere «no».
        risposta = trasporto.scarica(
            feed.url, validatori=Validatori(feed.etag, feed.last_modified)
        )
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

    if risposta.non_modificato:
        # Il portale conferma che i validatori che gli abbiamo mandato sono
        # ancora buoni: non c'è corpo, quindi non c'è NULLA da riconciliare.
        #
        # È l'interazione che il test design marca come il rischio peggiore
        # dell'Epic (R2-C): un 304 letto come «il feed è arrivato ed è vuoto»
        # marcherebbe `rimossa_dal_feed` l'intero calendario, con esito
        # riuscito e quindi in silenzio. Il ritorno anticipato qui è la
        # ragione per cui non può succedere — non c'è nessun percorso da
        # questa riga a `_riconcilia`.
        #
        # Il run è comunque RIUSCITO e il suo timestamp fa avanzare «dati
        # aggiornati alle HH:MM»: abbiamo davvero verificato con il portale
        # che i dati che mostriamo sono correnti, ed è esattamente ciò che
        # NFR-2 chiede di dire all'Host.
        _memorizza_validatori(db, feed, risposta)
        return _scrivi_run(
            db,
            feed,
            iniziato_il=iniziato_il,
            esito=EsitoSyncRun.RIUSCITO,
            non_modificato=True,
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

    # TUTTI gli uid letti dal feed, compresi quelli di eventi che non si
    # normalizzano: un evento malformato è comunque presente nel feed, e
    # trattarlo come scomparso marcherebbe `rimossa_dal_feed` una
    # Prenotazione viva.
    uid_presenti = [
        vevent.uid for vevent in analizzato.eventi if vevent.uid is not None
    ]
    if not uid_presenti:
        # Due casi, una sola conclusione. Un calendario chiuso ma senza eventi
        # e un calendario i cui eventi non portano un `UID` utilizzabile sono
        # entrambi indistinguibili da un export andato male, e in entrambi
        # l'insieme degli uid presenti è vuoto — cioè l'insieme rispetto al
        # quale si decide chi è «scomparso».
        #
        # Il costo dei due errori non è simmetrico: trattarli come «tutto
        # scomparso» svuoterebbe il calendario e farebbe `decadere` i
        # Conflitti aperti, con esito RIUSCITO e quindi in silenzio; trattarli
        # come run fallito costa un errore visibile su un Feed che davvero non
        # ha prenotazioni identificabili. Si sceglie il secondo.
        return _scrivi_run(
            db,
            feed,
            iniziato_il=iniziato_il,
            esito=EsitoSyncRun.FALLITO,
            categoria=CategoriaErroreSync.FEED_SENZA_EVENTI,
        )

    conteggi = _riconcilia(db, feed, analizzato, uid_presenti)
    # DOPO la riconciliazione, mai prima: il validatore certifica che questo
    # corpo è entrato nel database. Scriverlo prima significherebbe che un
    # errore a metà riconciliazione lascerebbe un validatore che promette
    # dati che non abbiamo, e il prossimo 304 congelerebbe il Feed su di essi.
    _memorizza_validatori(db, feed, risposta)
    return _scrivi_run(
        db,
        feed,
        iniziato_il=iniziato_il,
        esito=EsitoSyncRun.RIUSCITO,
        conteggi=conteggi,
    )


def _memorizza_validatori(db: Session, feed: FeedIcal, risposta: RispostaFeed) -> None:
    FeedIcalRepository(db).aggiorna_validatori(
        feed.host_id,
        feed_id=feed.id,
        etag=risposta.etag,
        last_modified=risposta.last_modified,
    )


def _riconcilia(
    db: Session,
    feed: FeedIcal,
    analizzato: ical.FeedAnalizzato,
    uid_presenti: list[str],
) -> EsitoImport:
    """Upsert degli eventi e transizione degli scomparsi. Mai una DELETE."""
    prenotazioni = PrenotazioneRepository(db)
    importate = aggiornate = ricomparse = malformati = ricorrenti = 0

    for vevent in analizzato.eventi:
        try:
            evento = normalizza(vevent)
        except Exception as exc:
            # `normalizza` è PURA: nessun I/O, nessuna sessione. Qui si può
            # catturare largo senza rischiare di proseguire su una transazione
            # abortita, e va fatto: il contenuto è di terze parti, quindi
            # l'insieme dei modi in cui può essere illeggibile non è
            # enumerabile a priori. Un'eccezione che sfugge risalirebbe fino
            # al SAVEPOINT per item del worker, annullando la riga `sync_run`
            # insieme all'errore — e il Feed tornerebbe a
            # «mai sincronizzato» senza categoria d'errore, cioè il
            # fallimento silenzioso che AC 7 e AC 5 vietano.
            #
            # L'uid resta in `uid_presenti` (calcolato a monte): un evento
            # illeggibile è comunque NEL feed, non scomparso.
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
