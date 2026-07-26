"""Confine di rete verso i Feed iCal: l'unico punto che esce dal processo.

Il client è **iniettato per costruzione** nel service (parametro, non import
globale): è la condizione perché i test possano sostituire il confine senza
mockare il service, e perché `ETag`, redirect, timeout e cap di dimensione
restino comportamento osservabile invece di sparire dentro un mock.

Le proprietà che vivono qui e da nessun'altra parte (NFR-17):

1. **I redirect non li segue il client HTTP.** Li seguiamo noi, un hop alla
   volta, rivalidando la politica di uscita di rete su ogni destinazione: un
   `Location:` verso `169.254.169.254` è esattamente l'attacco che una
   validazione fatta solo sull'URL iniziale non vede. E un redirect non può
   **declassare** da `https` a `http`: l'URL di un Feed porta il segreto in
   query, e sul filo in chiaro sarebbe regalato.
2. **Si connette all'indirizzo GIÀ validato**, non al risultato di una
   seconda risoluzione DNS. Senza il pinning ci sarebbero due lookup
   indipendenti per hop e niente legherebbe il secondo al primo: un DNS che
   cambia risposta fra validazione e connessione (rebinding) porterebbe il
   fetch dove vuole.
3. **Il corpo si legge in streaming con un tetto**, e solo se il portale non
   l'ha compresso: `iter_bytes()` sceglie il decoder dal `Content-Encoding`
   della RISPOSTA, non da quello che abbiamo chiesto, quindi il cap sui byte
   decodificati da solo non limita la memoria.
4. **Un bound sul TEMPO, non un insieme di checkpoint.** I timeout di httpx
   sono per-operazione e si azzerano a ogni byte; la fase di testa della
   risposta non passa da `iter_bytes`, quindi nessun controllo applicativo la
   vede. Un insieme di controlli non limita il tempo che passa FRA due
   controlli: qui ogni attesa (DNS compreso) si esegue con una scadenza, e
   alla scadenza il worker torna disponibile qualunque cosa stia facendo la
   socket. `core/worker.py` è un ciclo sequenziale in-process: una
   connessione appesa ferma i job di tutti gli Host, non solo di quello del
   Feed lento.
5. **Solo GET.** La superficie pubblica non espone altro verbo: «il sistema
   non scrive mai verso le OTA» resta vero per costruzione.
6. **Nessuna fiducia nell'ambiente.** Un `HTTPS_PROXY` farebbe risolvere il
   nome al proxy, azzerando l'intera denylist.
"""

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as ScadenzaFuturo
from dataclasses import dataclass
from functools import partial
from typing import Protocol, TypeVar
from urllib.parse import urljoin, urlsplit

import httpx

from app.calendario.uscita_rete import (
    DestinazioneNonAmmessaError,
    PoliticaUscitaRete,
    Risolutore,
    UrlFeedNonValidoError,
    risolutore_di_sistema,
    url_redatto,
    valida_destinazione,
    valida_formato,
)

logger = logging.getLogger(__name__)

STATI_DI_REDIRECT = frozenset({301, 302, 303, 307, 308})

# Le sole codifiche del contenuto accettate: nessuna. Il cap conta i byte
# DECODIFICATI, quindi una risposta compressa può gonfiare di ordini di
# grandezza prima che il cap se ne accorga — e un chunk che decodifica a
# stringa vuota non emette nemmeno un evento su cui controllare la scadenza.
CODIFICHE_AMMESSE = frozenset({"", "identity"})

T = TypeVar("T")


class ErroreDiTrasporto(Exception):
    """Il feed non si è potuto scaricare. Nessuno stato di dominio cambia."""


class UrlNonRaggiungibileError(ErroreDiTrasporto):
    """Connessione fallita, host che non risolve, o destinazione vietata.

    Le cause condividono un solo errore di proposito: distinguerle
    trasformerebbe il messaggio in un canale per mappare la rete interna
    (NFR-17).
    """


class TimeoutFeedError(ErroreDiTrasporto):
    """Superato un timeout di operazione o la scadenza complessiva."""


class RispostaTroppoGrandeError(ErroreDiTrasporto):
    """Superato il cap di dimensione della risposta."""


class EsitoHttpInattesoError(ErroreDiTrasporto):
    """Il portale ha risposto, ma non con un feed utilizzabile."""

    def __init__(self, stato: int) -> None:
        super().__init__(f"esito HTTP {stato}")
        self.stato = stato


@dataclass(frozen=True, slots=True)
class RispostaFeed:
    stato: int
    corpo: bytes
    content_type: str | None
    etag: str | None
    last_modified: str | None


class ClientFeed(Protocol):
    """Confine iniettabile: il service dipende da questo, non da httpx."""

    def scarica(self, url: str) -> RispostaFeed: ...


class ClientFeedHttp:
    """Implementazione reale del confine. Non segue i redirect da sé."""

    def __init__(
        self,
        politica: PoliticaUscitaRete,
        *,
        risolutore: Risolutore = risolutore_di_sistema,
    ) -> None:
        self._politica = politica
        self._risolutore = risolutore

    def scarica(self, url: str) -> RispostaFeed:
        corrente = url
        # Scadenza monotona calcolata UNA volta: il budget è dell'intero
        # fetch, quindi una catena di redirect non lo moltiplica.
        scadenza = time.monotonic() + self._politica.deadline_totale_secondi
        for _ in range(self._politica.max_redirect + 1):
            vetted = self._valida(corrente, scadenza)
            esito = self._entro_la_scadenza(
                # `partial` e non una lambda: la lambda catturerebbe le
                # variabili del ciclo per riferimento (B023).
                partial(self._un_hop, corrente, vetted, scadenza),
                scadenza,
            )
            if isinstance(esito, RispostaFeed):
                return esito
            corrente = esito
        raise UrlNonRaggiungibileError(
            f"troppi redirect (>{self._politica.max_redirect})"
        )

    # ------------------------------------------------------------------ tempo

    def _residuo(self, scadenza: float) -> float:
        residuo = scadenza - time.monotonic()
        if residuo <= 0:
            raise TimeoutFeedError("superata la scadenza complessiva del fetch")
        return residuo

    def _entro_la_scadenza(self, azione: Callable[[], T], scadenza: float) -> T:
        """Esegue `azione` e la ABBANDONA alla scadenza.

        È qui che il bound diventa reale. Nessun timeout di httpx limita il
        tempo *aggregato*: si applicano a ogni singola operazione e si
        azzerano a ogni byte ricevuto, quindi né la fase di testa né il
        framing chunked (né le estensioni di chunk, che possono portare
        kilobyte senza emettere un solo evento di dato) hanno un tetto.

        L'attesa la si limita dove si può limitare davvero: su ciò che
        attende. Alla scadenza questo metodo solleva e il worker riparte; il
        lavoro abbandonato muore da sé, perché il timeout di lettura passato
        all'hop è a sua volta limitato al residuo.
        """
        residuo = self._residuo(scadenza)
        esecutore = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fetch-feed")
        try:
            futuro = esecutore.submit(azione)
            try:
                return futuro.result(timeout=residuo)
            except ScadenzaFuturo as exc:
                raise TimeoutFeedError(
                    "superata la scadenza complessiva del fetch"
                ) from exc
        finally:
            # `wait=False`: attendere il lavoro abbandonato riporterebbe
            # esattamente il blocco che questo metodo esiste per evitare.
            esecutore.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------- validazione

    def _valida(self, url: str, scadenza: float) -> tuple[str, ...]:
        """Politica di uscita di rete su OGNI hop; ritorna gli indirizzi ok.

        La risoluzione DNS è l'unica altra attesa del fetch e non ha un
        timeout proprio (`getaddrinfo` non lo accetta): passa anche lei dalla
        scadenza, altrimenti sarebbero fino a `max_redirect + 1` attese fuori
        dal budget.
        """
        try:
            parti = valida_formato(url)
            return self._entro_la_scadenza(
                partial(valida_destinazione, parti, self._politica, self._risolutore),
                scadenza,
            )
        except (UrlFeedNonValidoError, DestinazioneNonAmmessaError) as exc:
            logger.warning(
                "fetch del feed rifiutato dalla politica di uscita di rete",
                extra={"url": url_redatto(url)},
            )
            raise UrlNonRaggiungibileError("URL non raggiungibile") from exc

    # ------------------------------------------------------------------- fetch

    def _timeout(self, scadenza: float) -> httpx.Timeout:
        """Timeout per-operazione, mai più lunghi del budget che resta.

        Non sono il bound (vedi `_entro_la_scadenza`): servono a far morire in
        fretta il lavoro abbandonato invece di lasciarlo su una socket viva.
        """
        residuo = self._residuo(scadenza)
        return httpx.Timeout(
            connect=min(self._politica.timeout_connessione_secondi, residuo),
            read=min(self._politica.timeout_lettura_secondi, residuo),
            write=min(self._politica.timeout_connessione_secondi, residuo),
            pool=min(self._politica.timeout_connessione_secondi, residuo),
        )

    def _un_hop(
        self, url: str, vetted: tuple[str, ...], scadenza: float
    ) -> RispostaFeed | str:
        pinnato, intestazioni, estensioni = self._richiesta_pinnata(url, vetted)
        try:
            with (
                httpx.Client(
                    follow_redirects=False,
                    timeout=self._timeout(scadenza),
                    # Un `HTTPS_PROXY` nell'ambiente del worker farebbe risolvere
                    # il nome AL PROXY, azzerando l'intera denylist —
                    # `169.254.169.254` incluso. Su self-hosted un proxy
                    # nell'ambiente è lo scenario normale, non l'eccezione.
                    trust_env=False,
                    headers={
                        "Accept": "text/calendar, text/plain;q=0.5",
                        "Accept-Encoding": "identity",
                    },
                ) as client,
                client.stream(
                    "GET", pinnato, headers=intestazioni, extensions=estensioni
                ) as risposta,
            ):
                if risposta.status_code in STATI_DI_REDIRECT:
                    # `urljoin` sull'URL LOGICO, non su quello pinnato: un
                    # `Location` relativo si risolverebbe sull'indirizzo IP e
                    # perderebbe l'host originale.
                    return self._prossimo_hop(url, risposta)
                if risposta.status_code != 200:
                    raise EsitoHttpInattesoError(risposta.status_code)
                self._rifiuta_codifica_inattesa(risposta)
                return RispostaFeed(
                    stato=risposta.status_code,
                    corpo=self._corpo_con_tetto(risposta, scadenza),
                    content_type=risposta.headers.get("content-type"),
                    etag=risposta.headers.get("etag"),
                    last_modified=risposta.headers.get("last-modified"),
                )
        except httpx.TimeoutException as exc:
            raise TimeoutFeedError("timeout nel fetch del feed") from exc
        except httpx.HTTPError as exc:
            # Include la chiusura anticipata della connessione: il corpo è
            # incompleto, quindi non è un feed — è un errore di trasporto.
            raise UrlNonRaggiungibileError("URL non raggiungibile") from exc

    @staticmethod
    def _rifiuta_codifica_inattesa(risposta: httpx.Response) -> None:
        """`Accept-Encoding: identity` è una richiesta, non una garanzia.

        `iter_bytes()` decodifica in base al `Content-Encoding` che il portale
        ha **risposto**: una risposta gzip con `Content-Length` piccolo passa
        il pre-check sul dichiarato e poi si espande di ordini di grandezza
        prima che il cap sui byte decodificati se ne accorga.
        """
        codifica = risposta.headers.get("content-encoding", "").strip().lower()
        if codifica not in CODIFICHE_AMMESSE:
            raise RispostaTroppoGrandeError(
                f"codifica del contenuto non ammessa: '{codifica}'"
            )

    @staticmethod
    def _richiesta_pinnata(
        url: str, vetted: tuple[str, ...]
    ) -> tuple[str, dict[str, str], dict[str, object]]:
        """URL con l'indirizzo GIÀ validato al posto del nome (NFR-17).

        L'identità del server resta quella vera: `Host` esplicito e
        `sni_hostname` per la stretta di mano TLS, così la verifica del
        certificato continua a valere sul nome e non sull'indirizzo. Lo
        userinfo si conserva: sostituire l'intero netloc lo cancellerebbe, e
        un Feed con credenziali nell'URL — forma che questo codice supporta —
        prenderebbe 401.
        """
        parti = urlsplit(url)
        hostname = parti.hostname or ""
        if not vetted:
            return url, {}, {}
        letterale = _fra_parentesi(vetted[0])
        porta = f":{parti.port}" if parti.port is not None else ""
        netloc = f"{_userinfo(parti)}{letterale}{porta}"
        pinnato = parti._replace(netloc=netloc).geturl()
        # `Host` senza userinfo e con le quadre se è un IPv6 (RFC 9110).
        host = f"{_fra_parentesi(hostname)}{porta}"
        return pinnato, {"Host": host}, {"sni_hostname": hostname}

    @staticmethod
    def _prossimo_hop(url: str, risposta: httpx.Response) -> str:
        """Destinazione del redirect, se è lecito seguirla.

        Risoluzione e divieto di declassamento stanno nella stessa funzione di
        proposito: erano due righe adiacenti nel ciclo, e la seconda si poteva
        cancellare senza che nulla si rompesse. Qui il calcolo del prossimo hop
        non esiste senza il controllo.

        Rivalidare lo schema non basterebbe: `http` è ammesso in assoluto, ma
        non **dopo** `https` — l'URL di un Feed porta il segreto nella query, e
        seguire un declassamento lo metterebbe in chiaro sul filo.
        """
        posizione = risposta.headers.get("location")
        if not posizione:
            raise EsitoHttpInattesoError(risposta.status_code)
        destinazione = urljoin(url, posizione)
        if urlsplit(url).scheme == "https" and urlsplit(destinazione).scheme != "https":
            raise UrlNonRaggiungibileError("redirect che declassa da https a http")
        return destinazione

    def _corpo_con_tetto(self, risposta: httpx.Response, scadenza: float) -> bytes:
        tetto = self._politica.dimensione_massima_byte
        dichiarata = risposta.headers.get("content-length")
        if dichiarata is not None and dichiarata.isdigit() and int(dichiarata) > tetto:
            # Cap rispettato PRIMA di scaricare: se il portale dichiara 2 GB
            # non c'è motivo di leggerne il primo byte.
            raise RispostaTroppoGrandeError(f"dimensione dichiarata > {tetto} byte")
        pezzi: list[bytes] = []
        letti = 0
        for pezzo in risposta.iter_bytes():
            # NON è il bound — lo è `_entro_la_scadenza`. Chiamare «bound
            # wall-clock» un insieme di checkpoint è precisamente l'errore che
            # aveva lasciato aperta la fase di testa: un insieme di controlli
            # non limita il tempo che passa fra due controlli. Questo serve
            # solo a non accumulare lavoro inutile dopo la scadenza.
            self._residuo(scadenza)
            letti += len(pezzo)
            if letti > tetto:
                raise RispostaTroppoGrandeError(f"risposta oltre {tetto} byte")
            pezzi.append(pezzo)
        return b"".join(pezzi)


def _fra_parentesi(indirizzo: str) -> str:
    """IPv6 fra quadre, IPv4 e nomi così come sono."""
    return f"[{indirizzo}]" if ":" in indirizzo else indirizzo


def _userinfo(parti: object) -> str:
    utente = getattr(parti, "username", None)
    if not utente:
        return ""
    password = getattr(parti, "password", None)
    return f"{utente}:{password}@" if password else f"{utente}@"
