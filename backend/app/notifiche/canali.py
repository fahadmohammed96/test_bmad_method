"""I canali di uscita dell'MVP (AD-13): in-app ed email.

Un canale è una cosa sola: `invia(destinatario, messaggio)`, che ritorna se ha
consegnato e solleva se no. Nessun valore di ritorno da interpretare — un
esito che si può ignorare prima o poi si ignora, e la notifica «inviata» che
non è mai partita è precisamente il difetto che NFR-3 chiama di severità alta.

**Il canale in-app non esce da qui**: la riga `notifica_consegna` con il suo
testo *è* la consegna. Non è una scorciatoia — è il motivo per cui una
notifica in-app non può fallire per un guasto di rete, e per cui l'Host vede
il Conflitto anche quando l'email non parte.

**Il canale email si inietta** (AC 10). Nella suite lo sostituisce una guardia
che solleva: nessun test manda posta a nessuno, e chi ha bisogno di osservare
un invio installa un canale finto. La guardia GS-1 sulla rete resta la seconda
difesa, indipendente da questa: `tests/test_isolamento_notifiche.py` dimostra
che il canale SMTP reale, se qualcuno lo installasse, morirebbe comunque
contro la socket.
"""

import logging
import smtplib
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.core.config import get_settings
from app.notifiche.models import CanaleConsegna
from app.notifiche.registro import Messaggio

logger = logging.getLogger(__name__)


class ConsegnaFallitaError(Exception):
    """Il canale non ha consegnato: il job resta ritentabile (AC 7).

    Il messaggio NON riporta il testo né il destinatario: un errore che viene
    scritto in `job.last_error` e nei log deve portare identificatori e
    categoria, mai il contenuto (AD-16, NFR-11).
    """


class CanaleUscita(Protocol):
    def invia(self, destinatario: str, messaggio: Messaggio) -> None: ...


class CanaleInApp:
    """Consegna in-app: la riga scritta dal service è già il messaggio."""

    def invia(self, destinatario: str, messaggio: Messaggio) -> None:
        return None


# Il tipo di ciò che apre una connessione SMTP: si inietta per poter provare
# la composizione del messaggio senza una socket.
FabbricaSmtp = Callable[[], AbstractContextManager[smtplib.SMTP]]


def _connessione_di_sistema(host: str, porta: int, timeout: float) -> FabbricaSmtp:
    def apri() -> AbstractContextManager[smtplib.SMTP]:
        return smtplib.SMTP(host, porta, timeout=timeout)

    return apri


@dataclass(frozen=True, slots=True)
class CanaleEmailSmtp:
    """Invio SMTP. La connessione è un parametro, non un dettaglio nascosto."""

    mittente: str
    apri_connessione: FabbricaSmtp

    def invia(self, destinatario: str, messaggio: Messaggio) -> None:
        posta = EmailMessage()
        posta["From"] = self.mittente
        posta["To"] = destinatario
        posta["Subject"] = messaggio.oggetto
        posta.set_content(messaggio.corpo)
        try:
            with self.apri_connessione() as connessione:
                connessione.send_message(posta)
        except OSError as errore:
            # Solo la CATEGORIA: l'indirizzo dell'Host non finisce in
            # `job.last_error`, che è una colonna che nessuno ripulisce.
            raise ConsegnaFallitaError(
                f"canale email non raggiungibile: {type(errore).__name__}"
            ) from errore


class CanaleEmailNonConfigurato:
    """Nessun SMTP in configurazione: si fallisce, non si finge di consegnare.

    Un ambiente senza posta configurata non deve produrre notifiche
    silenziosamente perse: il job resta ritentabile e, esauriti i tentativi,
    `failed` con il motivo scritto. È la stessa regola di AD-9 sui parametri
    mancanti — stato esplicito, mai un default inventato.
    """

    def invia(self, destinatario: str, messaggio: Messaggio) -> None:
        raise ConsegnaFallitaError(
            "canale email non configurato: HOSTPILOT_SMTP_HOST è vuoto"
        )


def canale_email_di_produzione() -> CanaleUscita:
    impostazioni = get_settings()
    if not impostazioni.smtp_host or not impostazioni.smtp_mittente:
        return CanaleEmailNonConfigurato()
    return CanaleEmailSmtp(
        mittente=impostazioni.smtp_mittente,
        apri_connessione=_connessione_di_sistema(
            impostazioni.smtp_host,
            impostazioni.smtp_porta,
            impostazioni.smtp_timeout_secondi,
        ),
    )


class RegistroCanali:
    """Quale implementazione serve un canale, con l'innesto per i test.

    Senza installazione esplicita si ricade sul canale di produzione, che per
    l'email si ricostruisce a ogni richiesta: la configurazione si legge
    quando serve, non all'import — altrimenti un ambiente che cambia
    impostazione richiederebbe un riavvio per una ragione che nessuno
    ricorderebbe.
    """

    def __init__(self) -> None:
        self._installati: dict[CanaleConsegna, CanaleUscita] = {}

    def installa(self, canale: CanaleConsegna, uscita: CanaleUscita) -> None:
        self._installati[canale] = uscita

    def rimuovi(self, canale: CanaleConsegna) -> None:
        self._installati.pop(canale, None)

    def per(self, canale: CanaleConsegna) -> CanaleUscita:
        installato = self._installati.get(canale)
        if installato is not None:
            return installato
        if canale is CanaleConsegna.IN_APP:
            return CanaleInApp()
        return canale_email_di_produzione()


canali = RegistroCanali()
