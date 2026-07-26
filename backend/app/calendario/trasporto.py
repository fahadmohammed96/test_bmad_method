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
3. **Il corpo si legge in streaming con un tetto**, e senza compressione: il
   cap conta i byte decodificati, quindi da solo non limiterebbe la memoria
   contro una bomba zlib.
4. **Una deadline sull'INTERO fetch.** I timeout di httpx sono
   per-operazione: un portale che sgocciola un byte appena dentro il timeout
   di lettura non ne fa scattare nessuno, e il worker è un ciclo sequenziale
   in-process — la connessione appesa fermerebbe i job di tutti gli Host.
5. **Solo GET.** La superficie pubblica non espone altro verbo: «il sistema
   non scrive mai verso le OTA» resta vero per costruzione.
6. **Nessuna fiducia nell'ambiente.** Un `HTTPS_PROXY` farebbe risolvere il
   nome al proxy, azzerando l'intera denylist.
"""

import logging
import time
from dataclasses import dataclass
from typing import Protocol
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


class ErroreDiTrasporto(Exception):
    """Il feed non si è potuto scaricare. Nessuno stato di dominio cambia."""


class UrlNonRaggiungibileError(ErroreDiTrasporto):
    """Connessione fallita, host che non risolve, o destinazione vietata.

    Le cause condividono un solo errore di proposito: distinguerle
    trasformerebbe il messaggio in un canale per mappare la rete interna
    (NFR-17).
    """


class TimeoutFeedError(ErroreDiTrasporto):
    """Superato un timeout di operazione o la deadline complessiva."""


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

    @property
    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self._politica.timeout_connessione_secondi,
            read=self._politica.timeout_lettura_secondi,
            write=self._politica.timeout_connessione_secondi,
            pool=self._politica.timeout_connessione_secondi,
        )

    def scarica(self, url: str) -> RispostaFeed:
        corrente = url
        # Deadline monotona calcolata UNA volta: il budget è dell'intero
        # fetch, quindi una catena di redirect lenti non lo moltiplica.
        scadenza = time.monotonic() + self._politica.deadline_totale_secondi
        with httpx.Client(
            follow_redirects=False,
            timeout=self._timeout,
            # Un `HTTPS_PROXY` nell'ambiente del worker farebbe risolvere il
            # nome AL PROXY, azzerando l'intera denylist — `169.254.169.254`
            # incluso. Su self-hosted un proxy nell'ambiente è lo scenario
            # normale, non l'eccezione.
            trust_env=False,
            headers={
                "Accept": "text/calendar, text/plain;q=0.5",
                # Senza `identity` httpx chiede gzip e `iter_bytes()`
                # decomprime senza limite. Il cap conta i byte DECODIFICATI,
                # quindi è corretto, ma non limiterebbe la memoria: poche
                # centinaia di KB di bomba zlib gonfiano a centinaia di MiB
                # prima che il cap se ne accorga.
                "Accept-Encoding": "identity",
            },
        ) as client:
            for _ in range(self._politica.max_redirect + 1):
                self._controlla_scadenza(scadenza)
                vetted = self._valida(corrente)
                esito = self._un_hop(client, corrente, vetted, scadenza)
                if isinstance(esito, RispostaFeed):
                    return esito
                self._vieta_declassamento(corrente, esito)
                corrente = esito
        raise UrlNonRaggiungibileError(
            f"troppi redirect (>{self._politica.max_redirect})"
        )

    @staticmethod
    def _controlla_scadenza(scadenza: float) -> None:
        if time.monotonic() >= scadenza:
            raise TimeoutFeedError("superata la deadline complessiva del fetch")

    def _valida(self, url: str) -> tuple[str, ...]:
        """Politica di uscita di rete su OGNI hop; ritorna gli indirizzi ok."""
        try:
            parti = valida_formato(url)
            return valida_destinazione(parti, self._politica, self._risolutore)
        except (UrlFeedNonValidoError, DestinazioneNonAmmessaError) as exc:
            logger.warning(
                "fetch del feed rifiutato dalla politica di uscita di rete",
                extra={"url": url_redatto(url)},
            )
            raise UrlNonRaggiungibileError("URL non raggiungibile") from exc

    @staticmethod
    def _vieta_declassamento(origine: str, destinazione: str) -> None:
        """Un redirect non può togliere il TLS.

        Rivalidare lo schema non basta: `http` è ammesso in assoluto, ma non
        **dopo** `https`. L'URL di un Feed porta il segreto nella query.
        """
        if (
            urlsplit(origine).scheme == "https"
            and urlsplit(destinazione).scheme != "https"
        ):
            raise UrlNonRaggiungibileError("redirect che declassa da https a http")

    def _un_hop(
        self,
        client: httpx.Client,
        url: str,
        vetted: tuple[str, ...],
        scadenza: float,
    ) -> RispostaFeed | str:
        pinnato, intestazioni, estensioni = self._richiesta_pinnata(url, vetted)
        try:
            with client.stream(
                "GET", pinnato, headers=intestazioni, extensions=estensioni
            ) as risposta:
                if risposta.status_code in STATI_DI_REDIRECT:
                    # `urljoin` sull'URL LOGICO, non su quello pinnato: un
                    # `Location` relativo si risolverebbe sull'indirizzo IP e
                    # perderebbe l'host originale.
                    return self._destinazione_del_redirect(url, risposta)
                if risposta.status_code != 200:
                    raise EsitoHttpInattesoError(risposta.status_code)
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
    def _richiesta_pinnata(
        url: str, vetted: tuple[str, ...]
    ) -> tuple[str, dict[str, str], dict[str, object]]:
        """URL con l'indirizzo GIÀ validato al posto del nome (NFR-17).

        L'identità del server resta quella vera: `Host` esplicito e
        `sni_hostname` per la stretta di mano TLS, così la verifica del
        certificato continua a valere sul nome e non sull'indirizzo.
        """
        parti = urlsplit(url)
        hostname = parti.hostname or ""
        if not vetted:
            return url, {}, {}
        indirizzo = vetted[0]
        letterale = f"[{indirizzo}]" if ":" in indirizzo else indirizzo
        netloc = letterale if parti.port is None else f"{letterale}:{parti.port}"
        pinnato = parti._replace(netloc=netloc).geturl()
        host = hostname if parti.port is None else f"{hostname}:{parti.port}"
        return pinnato, {"Host": host}, {"sni_hostname": hostname}

    @staticmethod
    def _destinazione_del_redirect(url: str, risposta: httpx.Response) -> str:
        posizione = risposta.headers.get("location")
        if not posizione:
            raise EsitoHttpInattesoError(risposta.status_code)
        return urljoin(url, posizione)

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
            # La deadline si controlla DENTRO il ciclo: è l'unico punto in cui
            # un portale che sgocciola può essere fermato, perché ogni singolo
            # byte arriva dentro il timeout di lettura.
            self._controlla_scadenza(scadenza)
            letti += len(pezzo)
            if letti > tetto:
                raise RispostaTroppoGrandeError(f"risposta oltre {tetto} byte")
            pezzi.append(pezzo)
        return b"".join(pezzi)
