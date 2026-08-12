"""Radice di composizione: l'unico posto che può conoscere due moduli insieme.

Lo spine disegna `calendario -. job .-> notifiche` **tratteggiata**: nessun
modulo dipende sincronicamente da `notifiche`, e `notifiche` a sua volta
dipende solo da `identity`. Ne segue che il collegamento fra i due — «quando
un Conflitto viene rilevato, notifica l'Host» — non può stare in nessuno dei
due: in `calendario` sarebbe un import di `notifiche` (vietato), in
`notifiche` sarebbe la conoscenza del dominio chiamante, cioè esattamente ciò
che impedirebbe all'Epic 3 e all'Epic 5 di riusarlo (AC 4, AC 11).

Sta qui, un livello sopra i moduli, dove sta già `registro_modelli` per la
stessa ragione. Questo file non è un modulo di dominio: non ha tabelle, non ha
repository, e la guardia GS-3 lo tratta come radice di composizione insieme a
`app/worker.py`.

Due cose, entrambe con effetto di registrazione all'import:

1. il **sottoscrittore** di `conflitto.rilevato`, che traduce un fatto di
   `calendario` in una richiesta di `notifiche`;
2. il **compositore** del testo, che alla consegna rilegge lo stato corrente e
   scrive il messaggio in italiano.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.calendario import service as calendario_service
from app.core.outbox import subscribers
from app.notifiche import service as notifiche_service
from app.notifiche.registro import FattoScomparsoError, Messaggio, compositori
from app.notifiche.testo import intervallo_it

logger = logging.getLogger(__name__)

# Il tipo di notifica è una stringa a catalogo, come i tipi di evento e di job
# (AD-17): è il nome con cui `notifiche` ritrova il compositore, e l'unica
# parola di dominio che quel modulo vede passare.
TIPO_NOTIFICA_CONFLITTO_RILEVATO = "conflitto_rilevato"

# Copy it-IT (NFR-9, UX-DR11). Vive qui e non in `notifiche` perché è testo di
# DOMINIO — parla di doppie prenotazioni — e non in `calendario` perché è un
# messaggio, non una regola del calendario. La radice di composizione è il
# posto in cui le due cose si incontrano una volta sola.
OGGETTO_CONFLITTO = "Possibile doppia prenotazione"


@compositori.registra(TIPO_NOTIFICA_CONFLITTO_RILEVATO)
def componi_conflitto(
    db: Session, host_id: uuid.UUID, riferimento_id: uuid.UUID
) -> Messaggio:
    """«Possibile doppia prenotazione — Bologna Centro, 15-17 agosto».

    Legge lo stato CORRENTE alla consegna (AC 6): niente di questo testo
    viaggia nel payload dell'evento o del job, che restano fatti di soli
    identificatori. Nessun dato dell'Ospite compare qui, e non per omissione —
    `RiepilogoConflitto` non ne trasporta (AD-16, NFR-11).
    """
    riepilogo = calendario_service.riepilogo_conflitto(db, host_id, riferimento_id)
    if riepilogo is None:
        raise FattoScomparsoError(f"conflitto {riferimento_id} non trovato")
    dettaglio = (
        f"{riepilogo.struttura}, "
        f"{intervallo_it(riepilogo.check_in, riepilogo.check_out)}"
    )
    return Messaggio(
        oggetto=f"{OGGETTO_CONFLITTO} — {dettaglio}",
        corpo=(
            f"{OGGETTO_CONFLITTO} — {dettaglio}.\n\n"
            "Due Prenotazioni attive si sovrappongono sulle stesse notti. "
            "Apri HostPilot per confrontarle e decidere quale tenere: il "
            "sistema non scrive mai sui portali al posto tuo."
        ),
    )


def al_conflitto_rilevato(session: Session, event_name: str, payload: dict) -> None:
    """`conflitto.rilevato` → una notifica dovuta all'Host (FR-5).

    **Idempotente**, perché la consegna è at-least-once (AD-10): la seconda
    consegna dello stesso evento trova la notifica già aperta e non ne apre
    una seconda. Non è un `if` a garantirlo — è il UNIQUE su
    `(host_id, tipo, riferimento_id)`, perché due consegne concorrenti
    passerebbero entrambe un controllo applicativo (gara A3-5).

    Non fa `commit`: la transazione è di `deliver_pending`, che esegue ogni
    handler dentro un SAVEPOINT (G-1).
    """
    host_id = uuid.UUID(str(payload["host_id"]))
    conflitto_id = uuid.UUID(str(payload["conflitto_id"]))
    notifiche_service.richiedi(
        session,
        host_id,
        tipo=TIPO_NOTIFICA_CONFLITTO_RILEVATO,
        riferimento_id=conflitto_id,
    )


subscribers.subscribe(
    calendario_service.EVENTO_CONFLITTO_RILEVATO, al_conflitto_rilevato
)
