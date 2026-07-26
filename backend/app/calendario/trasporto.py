"""Confine di rete verso i Feed iCal: l'unico punto che esce dal processo.

Il client è **iniettato per costruzione** nel service (parametro, non import
globale): è la condizione perché i test possano sostituire il confine senza
mockare il service, e perché `ETag`, redirect, timeout e cap di dimensione
restino comportamento osservabile invece di sparire dentro un mock.

Tre proprietà che vivono qui e da nessun'altra parte (NFR-17):

1. **I redirect non li segue il client HTTP.** Li seguiamo noi, un hop alla
   volta, rivalidando la politica di uscita di rete su ogni destinazione: un
   `Location:` verso `169.254.169.254` è esattamente l'attacco che una
   validazione fatta solo sull'URL iniziale non vede.
2. **Il corpo si legge in streaming con un tetto.** Un feed da 2 GB non deve
   esaurire la memoria del worker: al superamento del cap la connessione si
   chiude e il run è fallito.
3. **Solo GET.** La superficie pubblica non espone altro verbo: «il sistema
   non scrive mai verso le OTA» resta vero per costruzione.
"""

import logging
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin

import httpx

from app.calendario.uscita_rete import (
    DestinazioneNonAmmessaError,
    PoliticaUscitaRete,
    Risolutore,
    UrlFeedNonValidoError,
    risolutore_di_sistema,
    url_redatto,
    valida_url_feed,
)

logger = logging.getLogger(__name__)

STATI_DI_REDIRECT = frozenset({301, 302, 303, 307, 308})


class ErroreDiTrasporto(Exception):
    """Il feed non si è potuto scaricare. Nessuno stato di dominio cambia."""


class UrlNonRaggiungibileError(ErroreDiTrasporto):
    """Connessione fallita, host che non risolve, o destinazione vietata.

    Le tre cause condividono un solo errore di proposito: distinguerle
    trasformerebbe il messaggio in un canale per mappare la rete interna
    (NFR-17).
    """


class TimeoutFeedError(ErroreDiTrasporto):
    """Superato il timeout di connessione o di lettura."""


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
        with httpx.Client(
            follow_redirects=False,
            timeout=self._timeout,
            headers={"Accept": "text/calendar, text/plain;q=0.5"},
        ) as client:
            for _ in range(self._politica.max_redirect + 1):
                self._valida(corrente)
                esito = self._un_hop(client, corrente)
                if isinstance(esito, RispostaFeed):
                    return esito
                corrente = esito
        raise UrlNonRaggiungibileError(
            f"troppi redirect (>{self._politica.max_redirect})"
        )

    def _valida(self, url: str) -> None:
        """Politica di uscita di rete su OGNI hop, non solo sul primo."""
        try:
            valida_url_feed(url, self._politica, self._risolutore)
        except (UrlFeedNonValidoError, DestinazioneNonAmmessaError) as exc:
            logger.warning(
                "fetch del feed rifiutato dalla politica di uscita di rete",
                extra={"url": url_redatto(url)},
            )
            raise UrlNonRaggiungibileError("URL non raggiungibile") from exc

    def _un_hop(self, client: httpx.Client, url: str) -> RispostaFeed | str:
        try:
            with client.stream("GET", url) as risposta:
                if risposta.status_code in STATI_DI_REDIRECT:
                    return self._destinazione_del_redirect(url, risposta)
                if risposta.status_code != 200:
                    raise EsitoHttpInattesoError(risposta.status_code)
                return RispostaFeed(
                    stato=risposta.status_code,
                    corpo=self._corpo_con_tetto(risposta),
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
    def _destinazione_del_redirect(url: str, risposta: httpx.Response) -> str:
        posizione = risposta.headers.get("location")
        if not posizione:
            raise EsitoHttpInattesoError(risposta.status_code)
        return urljoin(url, posizione)

    def _corpo_con_tetto(self, risposta: httpx.Response) -> bytes:
        tetto = self._politica.dimensione_massima_byte
        dichiarata = risposta.headers.get("content-length")
        if dichiarata is not None and dichiarata.isdigit() and int(dichiarata) > tetto:
            # Cap rispettato PRIMA di scaricare: se il portale dichiara 2 GB
            # non c'è motivo di leggerne il primo byte.
            raise RispostaTroppoGrandeError(f"dimensione dichiarata > {tetto} byte")
        pezzi: list[bytes] = []
        letti = 0
        for pezzo in risposta.iter_bytes():
            letti += len(pezzo)
            if letti > tetto:
                raise RispostaTroppoGrandeError(f"risposta oltre {tetto} byte")
            pezzi.append(pezzo)
        return b"".join(pezzi)
