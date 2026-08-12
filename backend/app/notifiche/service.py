"""Service di `notifiche` (FR-5, FR-20, AD-10, AD-13).

Due sole operazioni, e la separazione fra loro è il cuore della Story:

- **`richiedi`** decide *se* è dovuta una notifica e su quali canali. Gira
  nella transazione del fatto che l'ha generata — la consegna dell'evento
  `conflitto.rilevato` — e non manda niente a nessuno: accoda job durevoli
  (AD-10). Se il processo muore un istante dopo il commit, la notifica non è
  persa, perché è una riga in tabella e non un'intenzione in memoria.
- **`consegna`** esegue *un* canale, ed è l'handler del job. È l'unico punto
  in cui si compone il testo, leggendo lo stato corrente (AC 6).

Nessuna delle due fa `commit`: la transazione è del chiamante, e il worker
esegue ogni handler dentro un SAVEPOINT (G-1) che un `commit` interno
scavalcherebbe.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.date_range import utcnow
from app.identity import service as identity_service
from app.identity.service import CanaleNotifica
from app.notifiche import jobs
from app.notifiche.canali import canali
from app.notifiche.models import CanaleConsegna, Notifica, StatoConsegna
from app.notifiche.registro import compositori
from app.notifiche.repository import ConsegnaRepository, NotificaRepository

logger = logging.getLogger(__name__)


class ConsegnaNonTrovataError(Exception):
    """Il job punta a una consegna che non esiste: non si tace, si solleva."""


class NotificaNonTrovataError(Exception):
    """La consegna punta a una notifica che non esiste (irraggiungibile)."""


def canali_da_servire(preferito: CanaleNotifica) -> tuple[CanaleConsegna, ...]:
    """I canali su cui consegnare, data la preferenza dell'Host (FR-20, AC 5).

    **L'in-app si scrive sempre, i canali in USCITA seguono la preferenza.**
    La distinzione non è una scappatoia per ignorare a metà il pannello della
    Story 1.3: l'in-app non è un modo di raggiungere l'Host, è la traccia del
    fatto dentro il prodotto — quella su cui la Dashboard (2.8) costruirà il
    badge, e quella che rende «mai silenziosa» una proprietà verificabile
    invece di una promessa. Toglierla renderebbe l'app cieca su un Conflitto
    che ha appena notificato per email.

    Quello che la preferenza governa davvero è ciò che esce dal prodotto e
    arriva addosso all'Host: con `in_app` scelto, nessuna email parte.

    **Questa funzione è il punto di innesto della decisione D1** (MYL-90,
    aperta a Fahad): `host.canale_notifica_preferito` è UN canale solo, mentre
    l'AC promette «in-app + email». Il comportamento qui sopra è il
    DEFAULT PROVVISORIO scelto per non lasciare la Story incompleta, non la
    decisione — che è di prodotto. La lettura alternativa (preferenza
    esclusiva: `return (CanaleConsegna[preferito.name],)`) si applica
    cambiando queste due righe, e fa cadere
    `test_notifiche_preferenze.py::TestCanaliDaServire::test_l_in_app_c_e_sempre`
    più `test_notifiche_consegna.py::TestPreferenzeIgnorate`. Nessun'altra
    parte del modulo la conosce.
    """
    if preferito is CanaleNotifica.EMAIL:
        return (CanaleConsegna.IN_APP, CanaleConsegna.EMAIL)
    return (CanaleConsegna.IN_APP,)


def richiedi(
    db: Session, host_id: uuid.UUID, *, tipo: str, riferimento_id: uuid.UUID
) -> Notifica | None:
    """Apre la notifica e accoda un job per canale; `None` se già notificata.

    Il tipo si valida contro il registro dei compositori PRIMA di scrivere
    (AD-17): una notifica senza testo è una riga che nessun job potrà mai
    consegnare, e il momento in cui accorgersene è questo, non tre tentativi
    dopo.

    Un job **per canale** e non uno per notifica: ogni job possiede un solo
    effetto esterno. Con un job solo, l'email che fallisce farebbe annullare
    dal SAVEPOINT anche la consegna in-app già marcata, e il ritentativo
    rifarebbe entrambe — cioè un canale rotto trascinerebbe con sé quello che
    funziona.
    """
    compositori.compositore_per(tipo)
    destinatario = identity_service.destinatario_notifiche(db, host_id)
    notifica_id = NotificaRepository(db).apri(
        host_id, tipo=tipo, riferimento_id=riferimento_id, adesso=utcnow()
    )
    if notifica_id is None:
        # Notifica già aperta per questo riferimento: la seconda rilevazione
        # dello stesso Conflitto non rinotifica (AC 2).
        return None
    consegne = ConsegnaRepository(db)
    for canale in canali_da_servire(destinatario.canale_preferito):
        consegna = consegne.aggiungi(host_id, notifica_id=notifica_id, canale=canale)
        jobs.accoda_consegna(db, consegna)
    logger.info(
        "notifica richiesta",
        extra={
            "host_id": str(host_id),
            "tipo": tipo,
            "riferimento_id": str(riferimento_id),
        },
    )
    return NotificaRepository(db).by_id(host_id, notifica_id)


def consegna(db: Session, host_id: uuid.UUID, consegna_id: uuid.UUID) -> bool:
    """Consegna UN canale. `True` se questo giro ha davvero consegnato.

    **Idempotente** (AC 3): la consegna dei job è at-least-once, e lo stesso
    job rieseguito trova la riga già `inviata` e non tocca il canale. Non è
    l'`if` in testa a garantirlo — quello risparmia solo il lavoro inutile —
    ma la condizione sullo stato dentro la `UPDATE` di `marca_inviata`: sotto
    concorrenza l'`if` passerebbe otto volte.

    L'ordine è **marca, poi invia**, e il fallimento del canale risale: il
    SAVEPOINT del kernel annulla la marcatura, la consegna torna `in_attesa` e
    il job si ritenta col backoff. Esauriti i tentativi il job è `failed` con
    il motivo scritto — visibile, non silenzioso (AC 7, AC 8).
    """
    consegne = ConsegnaRepository(db)
    riga = consegne.by_id(host_id, consegna_id)
    if riga is None:
        raise ConsegnaNonTrovataError(str(consegna_id))
    if riga.stato is StatoConsegna.INVIATA:
        return False
    notifica = NotificaRepository(db).by_id(host_id, riga.notifica_id)
    if notifica is None:
        raise NotificaNonTrovataError(str(riga.notifica_id))

    destinatario = identity_service.destinatario_notifiche(db, host_id)
    messaggio = compositori.compositore_per(notifica.tipo)(
        db, host_id, notifica.riferimento_id
    )
    if not consegne.marca_inviata(
        host_id, consegna_id=consegna_id, messaggio=messaggio, adesso=utcnow()
    ):
        # Un altro contendente ha preso in carico questa consegna.
        return False
    canali.per(riga.canale).invia(destinatario.email, messaggio)
    logger.info(
        "notifica consegnata",
        extra={
            "host_id": str(host_id),
            "consegna_id": str(consegna_id),
            "canale": riga.canale.value,
        },
    )
    return True
