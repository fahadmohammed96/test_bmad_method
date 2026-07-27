"""Sync dei Feed iCal come job durevole (AD-10, AD-17).

Due tipi di job, deliberatamente distinti:

- **`feed_ical.sync_richiesto`** — l'import on-demand del collegamento. Nasce
  **scaduto** (`due_at` = adesso): il worker lo prende al primo giro, prima di
  qualunque ciclo periodico, che per costruzione ha `due_at` nel futuro. È
  così che l'on-demand è «prioritario» senza introdurre una nozione di
  priorità nel kernel — che sarebbe un cambio di `core` per il bisogno di un
  solo dominio.
- **`feed_ical.sync_periodico`** — il poller di regime (Story 2.2). Nasce
  sempre nel futuro, si riprogramma alla fine di ogni esecuzione, e un
  bootstrap idempotente lo rimette in coda se manca.

**La periodicità vive nella tabella `job`, mai in un timer di processo**
(AD-10): un restart del worker non perde il ciclo, e non ne crea un secondo.
Le due metà sono entrambe necessarie e falliscono in modi opposti — senza la
riprogrammazione il poller gira una volta sola, senza il bootstrap un ciclo
perso non torna mai.

Perché un job **per Feed** e non un unico tick globale: l'intervallo è
adattivo per Feed (G3-5), un tick globale dovrebbe ricalcolare tutto ogni
volta al ritmo del più stretto, e un Feed rotto porterebbe con sé nella
morte per `max_attempts` il ciclo di tutti gli altri.
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendario import azzeramento
from app.calendario.azzeramento import EsitoAzzeramento
from app.calendario.models import FeedIcal
from app.calendario.retention import (
    LimiteRetention,
    filtro_scadute,
    limite_retention,
)
from app.core.config import get_settings
from app.core.date_range import utcnow
from app.core.events import catalog
from app.core.jobs import Job, JobStatus, handlers, schedule
from app.core.lock import NAMESPACE_SYNC_PERIODICO, blocca_per_id

logger = logging.getLogger(__name__)

TIPO_JOB_SYNC_FEED = "feed_ical.sync_richiesto"
TIPO_JOB_SYNC_PERIODICO = "feed_ical.sync_periodico"
TIPO_JOB_RETENTION_OSPITE = "ospite.azzera_scaduti"

# AD-17: i tipi si dichiarano nel catalogo unico, con payload di SOLI
# identificatori scalari — mai nomi di Ospiti, mai snapshot di stato.
catalog.register_job(TIPO_JOB_SYNC_FEED, payload_keys=("feed_id", "host_id"))
catalog.register_job(TIPO_JOB_SYNC_PERIODICO, payload_keys=("feed_id", "host_id"))
# Payload VUOTO: il job di retention non porta con sé né identificatori né,
# tanto meno, i campi che sta per azzerare. La coda `job` è leggibile da chi
# amministra il sistema, e un nome Ospite scritto lì sopravviverebbe
# all'azzeramento che il job stesso ha eseguito (AD-17, NFR-11).
catalog.register_job(TIPO_JOB_RETENTION_OSPITE, payload_keys=())


def _payload(feed: FeedIcal) -> dict[str, str]:
    return {"feed_id": str(feed.id), "host_id": str(feed.host_id)}


def accoda_sync_immediato(db: Session, feed: FeedIcal) -> Job:
    """Job di sync scaduto subito, nella transazione del chiamante."""
    return schedule(db, TIPO_JOB_SYNC_FEED, _payload(feed), due_at=utcnow())


@handlers.register(TIPO_JOB_SYNC_FEED)
def esegui_sync_del_feed(db: Session, payload: dict) -> None:
    """Handler idempotente: rieseguirlo non duplica né perde Prenotazioni.

    L'import è idempotente per costruzione (upsert su `(feed_id, ical_uid)`),
    che è la proprietà richiesta dalla consegna at-least-once di AD-10.
    """
    # Import locale: `service` importa questo modulo per accodare, quindi al
    # livello di modulo il ciclo si chiuderebbe.
    from app.calendario import service

    feed_id = uuid.UUID(str(payload["feed_id"]))
    host_id = uuid.UUID(str(payload["host_id"]))
    run = service.esegui_sync(db, host_id, feed_id)
    logger.info(
        "job di sync eseguito",
        extra={"feed_id": str(feed_id), "esito": run.esito.value},
    )


# --------------------------------------------------------------- poller (2.2)


def _riprogramma(db: Session, feed: FeedIcal) -> Job:
    """Accoda il prossimo giro. `due_at` è SEMPRE nel futuro.

    Non è un dettaglio: un ciclo periodico già scaduto alla nascita
    verrebbe preso nello stesso giro di worker che l'ha creato, e il poller
    girerebbe in ciclo stretto. È anche la proprietà su cui poggia la
    priorità dell'import on-demand, ed è pinnata da un test.
    """
    from app.calendario import service

    intervallo = service.intervallo_prossimo_sync(db, feed.host_id, feed)
    return schedule(
        db, TIPO_JOB_SYNC_PERIODICO, _payload(feed), due_at=utcnow() + intervallo
    )


def assicura_sync_periodico(db: Session, feed: FeedIcal) -> None:
    """Bootstrap idempotente del ciclo di UN Feed: mai due job in coda.

    È un `SELECT`-poi-`schedule`, cioè un **check-then-write**: fra la lettura
    e la scrittura un altro chiamante può inserire, e la regola dell'Epic 2
    (§2.4) dice che ogni percorso di questa forma nasce con un test di gara.
    Qui il test è `test_calendario_gara_poller.py::A3-3`.

    Serializzato con un lock consultivo e non con un UNIQUE, perché il
    vincolo non è esprimibile come unicità di una riga: `job` è una coda
    generica del kernel e la condizione è «nessuna riga di QUESTO tipo per
    QUESTO feed in stato pending o running» — un predicato su un
    sottoinsieme, non su una chiave. Un UNIQUE parziale su `(job_type,
    payload->>'feed_id')` legherebbe `core` alla forma del payload di un
    dominio (AD-1).

    Il lock è per Feed, quindi due Feed diversi non si aspettano mai:
    l'unico costo è fra chiamanti che stanno facendo esattamente la stessa
    cosa, e uno dei due sta per scoprire di non doverla fare.
    """
    blocca_per_id(db, NAMESPACE_SYNC_PERIODICO, feed.id)
    if _gia_in_coda(db, feed):
        return
    _riprogramma(db, feed)


def _gia_in_coda(db: Session, feed: FeedIcal) -> bool:
    return (
        db.scalars(
            select(Job.id)
            .where(
                Job.job_type == TIPO_JOB_SYNC_PERIODICO,
                Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
                Job.payload["feed_id"].astext == str(feed.id),
            )
            .limit(1)
        ).first()
        is not None
    )


def bootstrap_sync_periodico(db: Session) -> int:
    """Rimette in coda il ciclo di OGNI Feed che ne è rimasto senza.

    Chiamata all'avvio del worker: è la rete di sicurezza per i cicli che si
    sono persi — un job andato a `failed` per esaurimento dei tentativi, un
    Feed collegato mentre il worker era giù, una riga cancellata a mano.
    Senza, un ciclo perso resterebbe perso per sempre e il Feed smetterebbe
    di aggiornarsi in silenzio.

    Query **non scopata per Host**, e deliberatamente: questo è il worker
    all'avvio, non un percorso di richiesta. Non c'è un Host «corrente» a cui
    scoparla, nessun input di client la raggiunge, e scoparla per Host
    significherebbe non sincronizzare i Feed di tutti gli altri. Per lo stesso
    motivo vive qui e non nel repository, dove la guardia di tenancy (G-3)
    impone `host_id` su ogni metodo: l'eccezione è dichiarata dove si vede,
    invece di indebolire la regola per tutti. È la forma già usata da
    `identity/jobs.py::purge_sessioni_scadute`.
    """
    accodati = 0
    for feed in db.scalars(select(FeedIcal).order_by(FeedIcal.collegato_il)):
        if _gia_in_coda(db, feed):
            continue
        assicura_sync_periodico(db, feed)
        accodati += 1
    if accodati:
        logger.info("cicli di sync periodico rimessi in coda", extra={"feed": accodati})
    return accodati


@handlers.register(TIPO_JOB_SYNC_PERIODICO)
def esegui_sync_periodico(db: Session, payload: dict) -> None:
    """Un giro del poller, poi si riprogramma. Idempotente (AD-10).

    **Si riprogramma anche quando il sync fallisce**, ed è il punto di NFR-1:
    un portale irraggiungibile per un'ora non deve spegnere il poller di quel
    Feed, altrimenti il primo guasto temporaneo diventerebbe permanente e non
    lo scoprirebbe nessuno. `esegui_sync` non solleva sugli errori di rete —
    li registra come `sync_run` fallito — quindi questo handler arriva alla
    riprogrammazione in entrambi i casi.

    L'unica uscita senza riprogrammazione è il Feed che non esiste più: lì il
    ciclo deve fermarsi, e continuare a riaccodarlo sarebbe una coda che
    cresce per sempre su una risorsa scomparsa.
    """
    from app.calendario import service

    feed_id = uuid.UUID(str(payload["feed_id"]))
    host_id = uuid.UUID(str(payload["host_id"]))
    try:
        feed = service.leggi_feed(db, host_id, feed_id)
    except service.FeedNonTrovatoError:
        logger.info(
            "ciclo di sync periodico fermato: il Feed non esiste più",
            extra={"feed_id": str(feed_id)},
        )
        return

    run = service.esegui_sync(db, host_id, feed_id)
    prossimo = _riprogramma(db, feed)
    logger.info(
        "giro di sync periodico eseguito",
        extra={
            "feed_id": str(feed_id),
            "esito": run.esito.value,
            "non_modificato": run.non_modificato,
            "prossimo_il": prossimo.due_at.isoformat(),
        },
    )


# ------------------------------------------- retention anagrafica Ospite (2.3)


def _riprogramma_retention(db: Session) -> Job:
    return schedule(
        db,
        TIPO_JOB_RETENTION_OSPITE,
        {},
        due_at=utcnow()
        + timedelta(minutes=get_settings().ospite_retention_intervallo_minuti),
    )


def assicura_retention_periodica(db: Session) -> None:
    """Bootstrap idempotente del ciclo di retention: un solo job in coda.

    Stessa forma di `assicura_purge_periodico` (Epic 1), deliberatamente
    non fattorizzata: la duplicazione è nota ed è una proposta parcheggiata
    per Fahad, non una decisione da prendere dentro questa Story.
    """
    gia_in_coda = db.scalars(
        select(Job.id)
        .where(
            Job.job_type == TIPO_JOB_RETENTION_OSPITE,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
        .limit(1)
    ).first()
    if gia_in_coda is None:
        _riprogramma_retention(db)


@handlers.register(TIPO_JOB_RETENTION_OSPITE)
def azzera_anagrafiche_scadute(db: Session, payload: dict) -> None:
    """Retention dell'anagrafica Ospite (AD-21, NFR-12): AZZERA, non cancella.

    Alla scadenza si scrivono a `NULL` i tre campi personali dell'anagrafica
    **e il `sommario` della Prenotazione**, e si marca `anonimizzato_il` sulla
    riga il cui campo è stato azzerato. La riga `ospite`, la Prenotazione e la
    sua storia restano intatte: l'azzeramento è una delle **tre** sole
    cancellazioni distruttive che AD-20 ammette — il `sommario` è un campo in
    più della STESSA, non una quarta — ed è distruttivo sui CAMPI: una
    `DELETE` di riga sarebbe l'invariante rotto (GS-6).

    Il `sommario` è testo opaco del portale per tutto il resto del suo ciclo
    di vita, ma il `SUMMARY` dei feed OTA contiene spesso il nome dell'Ospite:
    azzerare l'anagrafica lasciandolo vivo vanificherebbe la retention. E la
    sua `UPDATE` non è guidata dall'Ospite (`azzeramento.per_prenotazioni`):
    l'Ospite non nasce mai dal sync, quindi il caso primario è la Prenotazione
    scaduta **senza alcuna riga `ospite`**.

    **Idempotente per costruzione, non per promessa.** La selezione prende
    solo le righe che hanno davvero qualcosa da azzerare: al secondo giro
    sullo stesso stato le `UPDATE` toccano zero righe, perché i campi sono già
    `NULL`. Non si marca `anonimizzato_il` su un'anagrafica che non ha mai
    avuto contatti né su una Prenotazione senza `sommario` — sarebbe
    l'evidenza di un adempimento che non è avvenuto, su dati che non sono mai
    esistiti.

    Il filtro è sui CAMPI e non su `anonimizzato_il IS NULL`, che sembrerebbe
    la condizione naturale e sarebbe un difetto: dalla Story 2.4 l'Host può
    reinserire un contatto su un'anagrafica già azzerata, e con quel filtro
    quel dato non scadrebbe mai più. La domanda giusta è «c'è qualcosa da
    azzerare?», non «l'ho già fatto una volta?». La guardia di
    NON-RIPOPOLAMENTO di AD-21 è un'altra cosa e vive nell'upsert, che è
    l'unico punto in cui un `sommario` può tornare da solo.

    Query **non scopata per Host**, e deliberatamente: è manutenzione del
    worker, non un percorso di richiesta, e scoparla per Host significherebbe
    non adempiere per tutti gli altri. Per lo stesso motivo vive qui e non
    nel repository, dove la guardia G-3 impone `host_id` su ogni metodo —
    stessa forma dichiarata di `bootstrap_sync_periodico` e di
    `identity/jobs.py::purge_sessioni_scadute`.

    **Il ciclo si riprogramma anche quando l'azzeramento fallisce** (E2-F1).
    Un errore che sfuggisse da qui porterebbe il job a `failed` al quinto
    tentativo, e a quel punto in coda non resterebbe **nessun** job di
    retention: la conservazione dei dati personali si fermerebbe oltre il
    termine, a tempo indefinito, fino al prossimo riavvio del worker. È lo
    stesso modo di guasto che il poller dichiara venti righe sopra, e la
    forma del rimedio è la sua: l'errore si REGISTRA, non si solleva.

    Il `try/except` non basta da solo, e la ragione è nel kernel: l'handler
    gira dentro il SAVEPOINT per item di `run_due_jobs` (G-1), quindi una
    riprogrammazione scritta in un `finally` verrebbe annullata insieme
    all'eccezione. Serve un savepoint **interno** attorno alla sola `UPDATE`:
    così il fallimento si richiude su sé stesso, la transazione esterna resta
    utilizzabile, e l'`INSERT` del prossimo giro va a buon fine.
    """
    adesso = utcnow()
    limite = limite_retention(
        adesso=adesso,
        periodo=timedelta(days=get_settings().ospite_retention_giorni),
    )
    azzerate = _azzera(db, limite, adesso)
    # SEMPRE, anche dopo un fallimento: un ciclo di adempimento che si spegne
    # da solo è peggio di un ciclo che sbaglia un giro.
    _riprogramma_retention(db)
    if azzerate is None:
        # Il silenzio è il difetto: un adempimento che non è avvenuto deve
        # lasciare traccia, e il giro dopo riproverà.
        logger.error(
            "retention dell'anagrafica Ospite non eseguita: ciclo riprogrammato",
            extra={"decorrenza_entro_il": limite.giorno.isoformat()},
        )
        return
    # Soli conteggi e confini: i dati appena azzerati non possono
    # sopravvivere nei log all'azzeramento stesso (AD-16, NFR-11).
    logger.info(
        "retention dell'anagrafica Ospite eseguita",
        extra={
            "anagrafiche_azzerate": azzerate.anagrafiche,
            "sommari_azzerati": azzerate.sommari,
            "decorrenza_entro_il": limite.giorno.isoformat(),
        },
    )


def _azzera(
    db: Session, limite: LimiteRetention, adesso: datetime
) -> EsitoAzzeramento | None:
    """Azzera i campi personali scaduti; `None` se l'azzeramento è fallito.

    Il savepoint interno è ciò che rende recuperabile il fallimento: senza,
    una `UPDATE` andata male lascerebbe la transazione abortita e l'`INSERT`
    della riprogrammazione fallirebbe a sua volta — cioè il rimedio
    morirebbe dello stesso errore da cui deve proteggere.

    **Entrambe le UPDATE stanno dentro QUESTO savepoint.** Metterne una fuori
    riaprirebbe E2-F1 dalla porta accanto: un suo fallimento spegnerebbe la
    riprogrammazione del ciclo, cioè il difetto appena chiuso.
    """
    try:
        # La costruzione della selezione sta DENTRO il try, non fuori: la
        # protezione è su «qualunque cosa prima della riprogrammazione», e un
        # pezzo lasciato fuori è esattamente la riga da cui il ciclo si
        # spegnerebbe di nuovo.
        selezione = azzeramento.per_prenotazioni(filtro_scadute(limite))
        with db.begin_nested():
            return azzeramento.esegui(db, selezione, adesso=adesso)
    except Exception:
        # Cattura larga e deliberata: l'insieme dei modi in cui una UPDATE
        # può fallire non è enumerabile a priori (deadlock, timeout, un
        # vincolo aggiunto domani), e qualunque di essi non deve poter
        # spegnere il ciclo. `exception` porta il traceback nei log.
        logger.exception(
            "azzeramento dell'anagrafica Ospite fallito",
            extra={"decorrenza_entro_il": limite.giorno.isoformat()},
        )
        return None
