"""Consumatori di eventi di dominio del modulo `calendario` (AD-1, AD-5).

**Questo è il primo sottoscrittore di `outbox` del progetto.** L'infrastruttura
di consegna esiste dalla Story 1.1 — `deliver_pending`, `EventSubscribers`, il
tick del worker — e finora nessun modulo si era registrato: gli eventi si
scrivevano, si consegnavano a zero handler e si marcavano consegnati.

Due conseguenze, e nessuna delle due è opzionale:

1. **La consegna è at-least-once** (AD-10). Un handler che fallisce lascia
   l'evento non consegnato, e il tick successivo riprova — insieme a tutti
   quelli del suo batch. L'handler nasce quindi **idempotente**: lo stesso
   evento consegnato due volte non deve far `decadere` due volte lo stesso
   Conflitto né riscriverne la data. Qui l'idempotenza non è una promessa
   nel commento: la transizione è condizionata allo stato dentro la `UPDATE`,
   quindi la seconda consegna tocca zero righe.
2. **La registrazione è un'assenza che tace.** Se `app/worker.py` smettesse
   di importare questo modulo, nessun test funzionale fallirebbe: gli eventi
   continuerebbero a essere scritti e «consegnati», e i Conflitti resterebbero
   accesi per sempre su Prenotazioni che non esistono più. Per questo la
   registrazione è pinnata da `tests/test_conflitti_decadimento.py`, che
   verifica il registro di PRODUZIONE dopo l'import dell'entrypoint.

L'import di questo modulo ha un effetto di registrazione, come per gli handler
di job: si importa una volta sola, dall'entrypoint del worker.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.outbox import subscribers

logger = logging.getLogger(__name__)


def alla_prenotazione_cessata(session: Session, event_name: str, payload: dict) -> None:
    """Una Prenotazione è uscita da `attiva`: i suoi Conflitti decadono.

    L'handler ascolta UN evento e non conosce le tre strade che lo producono
    — cancellazione manuale dell'Host, scomparsa dal feed, `STATUS:CANCELLED`
    dal portale. È il senso della decisione MYL-69: le tre diventano un solo
    fatto dal punto di vista di chi consuma.

    Non fa `commit`: la transazione è di `deliver_pending`, che esegue ogni
    handler dentro un SAVEPOINT (G-1) — un `commit` interno lo scavalcherebbe.
    """
    from app.calendario import service

    host_id = uuid.UUID(str(payload["host_id"]))
    prenotazione_id = uuid.UUID(str(payload["prenotazione_id"]))
    service.decadi_conflitti_della_prenotazione(session, host_id, prenotazione_id)


# Import locale nel corpo dell'handler e registrazione qui: `service` importa
# `jobs`, che importa `core`, e una registrazione a livello di modulo che
# passasse da `service` chiuderebbe il ciclo.
subscribers.subscribe("prenotazione.cessata", alla_prenotazione_cessata)
