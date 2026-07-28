"""Retention della coda `job` — manutenzione del kernel (MYL-51, AD-10).

Dalla Story 2.2 `job` è una tabella a **crescita illimitata e ritmo noto**: il
poller accoda un giro per Feed ogni quindici minuti, i cicli periodici di
manutenzione si riprogrammano ognuno alla fine di sé stesso, e nessuna riga
veniva mai eliminata. A regime la coda è fatta quasi interamente di righe
`completed` che nessuno rilegge, e ogni query che non può usare un indice le
attraversa tutte.

**Perché vive in `core` e non in un modulo di dominio.** `job` è la tabella del
kernel: un modulo di dominio che la ripulisse scriverebbe su una tabella non
sua, e la scelta di quali righe tenere non appartiene a nessun dominio in
particolare. `core` non importa domini (AD-1) e questo modulo non fa eccezione
— registra un handler nel registro del kernel e legge solo la propria tabella.

**Si elimina solo `completed`, mai `failed`.** Sono due popolazioni diverse:
le completate crescono col ritmo del sistema e non affermano nulla che non sia
già scritto altrove — la traccia dei sync è `sync_run`, quella degli
azzeramenti è `azzeramento_audit`, entrambe append-only e fuori dalla portata
di questo job; le fallite sono poche, il loro numero è un sintomo, e il loro
`last_error` è spesso l'unica cosa che resta di un guasto. Cancellarle sarebbe
buttare l'evidenza di un problema aperto per recuperare spazio che non
occupano. Le `pending` e le `running` sono lavoro futuro o in corso: fuori
questione.

**Perché `created_at` e non `due_at`.** `due_at` viene RISCRITTO dal backoff a
ogni tentativo fallito, quindi non è la data di nulla; `created_at` è
l'unico istante immutabile della riga. La finestra si legge come «da quanto
tempo questa riga esiste», che è esattamente la domanda della retention.
"""

import logging
from datetime import datetime, timedelta
from typing import cast

from sqlalchemy import ColumnElement, and_, delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.date_range import utcnow
from app.core.events import catalog
from app.core.jobs import Job, JobStatus, handlers, schedule
from app.core.lock import NAMESPACE_PURGE_JOB, blocca_singoletto

logger = logging.getLogger(__name__)

TIPO_JOB_PURGE_JOB = "job.purge_completati"

# Payload vuoto: il purge non ha parametri per riga, e la finestra è
# configurazione — leggerla dal payload significherebbe congelarla nel momento
# in cui il ciclo è stato accodato, cioè renderla non più configurabile senza
# svuotare la coda.
catalog.register_job(TIPO_JOB_PURGE_JOB, payload_keys=())


def filtro_scaduti(limite: datetime) -> ColumnElement[bool]:
    """Le righe che il purge può eliminare: completate e più vecchie del limite.

    Predicato isolato e non in linea nella `DELETE` perché è **la** decisione
    di questo modulo — quali righe si possono buttare — e perché è la sola
    parte che un test può sostituire per dimostrare che un guasto della query
    non spegne il ciclo.
    """
    return and_(Job.status == JobStatus.COMPLETED, Job.created_at < limite)


def _riprogramma(db: Session) -> Job:
    """Accoda il prossimo giro. `due_at` è SEMPRE nel futuro.

    Un ciclo periodico già scaduto alla nascita verrebbe preso nello stesso
    giro di worker che l'ha creato, e il poller girerebbe in ciclo stretto.
    """
    return schedule(
        db,
        TIPO_JOB_PURGE_JOB,
        {},
        due_at=utcnow()
        + timedelta(minutes=get_settings().job_retention_intervallo_minuti),
    )


@handlers.register(TIPO_JOB_PURGE_JOB)
def purga_job_completati(db: Session, payload: dict) -> None:
    """Elimina i job completati oltre la finestra, poi si riprogramma.

    **Idempotente per costruzione**: al secondo giro sullo stesso stato la
    `DELETE` tocca zero righe, perché quelle che c'erano non ci sono più. La
    consegna dei job è at-least-once (AD-10) e questo handler la regge senza
    condizioni aggiuntive.

    **Il ciclo si riprogramma anche quando la `DELETE` fallisce** — è la stessa
    forma di `calendario/jobs.py::azzera_anagrafiche_scadute` e per la stessa
    ragione (E2-F1): un errore che sfuggisse da qui porterebbe il job a
    `failed` al quinto tentativo, e a quel punto in coda non resterebbe
    **nessun** purge — la tabella tornerebbe a crescere senza limite, in
    silenzio, fino al prossimo riavvio del worker. Cioè esattamente il difetto
    che questo modulo esiste per chiudere, reintrodotto dal suo stesso rimedio.

    Il `try/except` da solo non basterebbe: l'handler gira dentro il SAVEPOINT
    per item di `run_due_jobs` (G-1), quindi una riprogrammazione scritta in un
    `finally` verrebbe annullata insieme all'eccezione, e se a fallire è la
    query la transazione resta abortita e anche l'`INSERT` fallirebbe. Serve un
    savepoint **interno** attorno alla sola `DELETE`.
    """
    limite = utcnow() - timedelta(days=get_settings().job_retention_giorni)
    eliminati = _elimina_completati(db, limite)
    # SEMPRE, anche dopo un fallimento.
    _riprogramma(db)
    if eliminati is None:
        logger.error(
            "purge della coda job non eseguito: ciclo riprogrammato",
            extra={"creati_prima_del": limite.isoformat()},
        )
        return
    logger.info(
        "purge della coda job eseguito",
        extra={"job_eliminati": eliminati, "creati_prima_del": limite.isoformat()},
    )


def _elimina_completati(db: Session, limite: datetime) -> int | None:
    """Righe eliminate, oppure `None` se la `DELETE` è fallita."""
    try:
        # La costruzione del predicato sta DENTRO il try, non fuori: la
        # protezione è su «qualunque cosa prima della riprogrammazione», e un
        # pezzo lasciato fuori è la riga da cui il ciclo si spegnerebbe.
        filtro = filtro_scaduti(limite)
        with db.begin_nested():
            # `synchronize_session=False`: è una DELETE di manutenzione su
            # righe che nessuno ha in sessione, e la sincronizzazione dello
            # stato ORM valuterebbe il predicato sugli oggetti presenti — fra
            # cui il job in corso, la cui `created_at` non è ancora scritta se
            # la riga non è stata flushata.
            risultato = cast(
                CursorResult,
                db.execute(
                    delete(Job).where(filtro),
                    execution_options={"synchronize_session": False},
                ),
            )
            return risultato.rowcount
    except Exception:
        # Cattura larga e deliberata: l'insieme dei modi in cui una DELETE può
        # fallire non è enumerabile a priori (deadlock, timeout, un vincolo
        # aggiunto domani), e nessuno di essi deve poter spegnere il ciclo.
        logger.exception(
            "purge della coda job fallito",
            extra={"creati_prima_del": limite.isoformat()},
        )
        return None


def assicura_purge_job_periodico(db: Session) -> None:
    """Bootstrap idempotente del ciclo di purge: un solo job in coda.

    `SELECT`-poi-`schedule`, serializzato con un lock consultivo sul namespace
    del singoletto: senza, due chiamanti concorrenti — due worker avviati
    insieme, un restart che si sovrappone al precedente — lascerebbero due
    cicli in coda, cioè il doppio dei giri per sempre e nessun errore che lo
    dica.

    Stessa forma di `identity/jobs.py::assicura_purge_periodico` e di
    `calendario/jobs.py::assicura_retention_periodica`, deliberatamente non
    fattorizzata: la duplicazione è nota — questa è la sua quarta occorrenza —
    ed è una proposta aperta per Fahad, non una decisione da prendere qui.

    Il test di gara è `tests/test_gara_bootstrap_singoletti.py`.
    """
    blocca_singoletto(db, NAMESPACE_PURGE_JOB)
    gia_in_coda = db.scalars(
        select(Job.id)
        .where(
            Job.job_type == TIPO_JOB_PURGE_JOB,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
        .limit(1)
    ).first()
    if gia_in_coda is None:
        _riprogramma(db)
