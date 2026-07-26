"""Politica di uscita di rete verso i Feed iCal (NFR-17).

L'Host incolla un URL e il **worker** lo scarica: è la definizione di SSRF.
La politica adottata è una **denylist** sull'indirizzo RISOLTO (allowlist di
domini OTA e proxy di egress restano alternative aperte, non implementate):

- soli schemi `http`/`https`;
- l'indirizzo risolto via DNS è rifiutato se ricade su loopback, reti
  private, link-local, endpoint di metadati d'istanza e spazi riservati;
- **tutti** gli indirizzi restituiti dal DNS devono passare: bastasse uno,
  un round-robin con un indirizzo interno sarebbe un bypass gratuito;
- la validazione si ripete dopo ogni redirect (vedi `trasporto.py`);
- il rifiuto NON rivela l'esito della risoluzione: in superficie diventa lo
  stesso «non raggiungibile» di una connessione fallita.

Il precedente in repo è `config_normativa/importa_comuni.py`, che valida il
percorso PRIMA di toccare il filesystem: qui vale lo stesso principio sulla
rete. Timeout e cap di dimensione sono CONFIGURAZIONE (NFR-4), non costanti.

Gli indirizzi validati si RESTITUISCONO al chiamante, e non è un dettaglio:
`trasporto.py` si connette esattamente a quelli invece di risolvere una
seconda volta. Senza quel passaggio ci sarebbero due `getaddrinfo`
indipendenti per hop e nulla legherebbe il secondo al primo — cioè un DNS che
cambia risposta fra validazione e connessione (rebinding) porterebbe il fetch
dove vuole. Il pinning è arrivato con il fix-batch `epic2-batch1`: questo
modulo dice QUALI indirizzi sono ammessi, il trasporto garantisce che siano
quelli usati.
"""

import ipaddress
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from urllib.parse import SplitResult, urlsplit

from app.core.config import Settings

SCHEMI_AMMESSI = frozenset({"http", "https"})

IndirizzoIP = ipaddress.IPv4Address | ipaddress.IPv6Address
ReteIP = ipaddress.IPv4Network | ipaddress.IPv6Network

# Reti vietate IN AGGIUNTA a quelle che `ipaddress` classifica già come
# loopback / private / link-local / multicast / reserved / unspecified.
RETI_VIETATE_AGGIUNTIVE: tuple[ReteIP, ...] = (
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT (RFC 6598)
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("100.100.100.200/32"),  # metadati Alibaba Cloud
    ipaddress.ip_network("64:ff9b::/96"),  # NAT64: incapsula IPv4 in IPv6
    ipaddress.ip_network("fec0::/10"),  # site-local IPv6 deprecato (RFC 3879)
)

# Il risolutore è iniettato: a unit la matrice degli indirizzi si scrive
# senza rete, e la guardia di isolamento della suite resta verde.
Risolutore = Callable[[str], Sequence[str]]


class UrlFeedNonValidoError(ValueError):
    """Formato dell'URL inammissibile.

    Si scopre SENZA rete: è l'errore inline immediato sul campo (422).
    """


class DestinazioneNonAmmessaError(ValueError):
    """L'indirizzo risolto ricade su una rete vietata (NFR-17).

    In superficie NON si distingue da un URL irraggiungibile: altrimenti
    l'errore diventa un canale per mappare la rete interna.
    """


@dataclass(frozen=True, slots=True)
class PoliticaUscitaRete:
    timeout_connessione_secondi: float
    timeout_lettura_secondi: float
    dimensione_massima_byte: int
    max_redirect: int
    # Tetto sull'intero fetch: i timeout per-operazione non fermano un
    # portale che sgocciola. Default alto per non cambiare il comportamento
    # dei chiamanti che non lo impostano.
    deadline_totale_secondi: float = 30.0
    # Reti normalmente vietate ammesse per configurazione: vuoto in ogni
    # ambiente reale (un test lo sorveglia), serve ai test di integrazione
    # che parlano con un server HTTP su 127.0.0.1.
    reti_consentite: tuple[ReteIP, ...] = field(default=())

    @classmethod
    def da_configurazione(cls, settings: Settings) -> "PoliticaUscitaRete":
        return cls(
            timeout_connessione_secondi=settings.feed_timeout_connessione_secondi,
            timeout_lettura_secondi=settings.feed_timeout_lettura_secondi,
            dimensione_massima_byte=settings.feed_dimensione_massima_byte,
            max_redirect=settings.feed_max_redirect,
            deadline_totale_secondi=settings.feed_deadline_totale_secondi,
            reti_consentite=tuple(
                ipaddress.ip_network(voce.strip())
                for voce in settings.feed_reti_consentite.split(",")
                if voce.strip()
            ),
        )


def url_redatto(url: str) -> str:
    """URL senza segreti, per log e messaggi d'errore (AD-16).

    Redige **due** posti, non uno. Lo userinfo RFC 3986 è quello ovvio; la
    **query** è quello che conta davvero, perché negli export delle OTA il
    link *è* la credenziale: `.../calendar/ical/<id>.ics?s=<segreto>`. Un URL
    di quel tipo scritto per intero in un log è un token in chiaro che dà
    accesso al calendario di un Host.

    Il path non si tocca: contiene l'identificativo della risorsa e serve a
    capire di quale feed si stia parlando.
    """
    try:
        parti = urlsplit(url)
    except ValueError:
        return "<url non analizzabile>"
    netloc = parti.netloc
    if "@" in netloc:
        _, _, host = netloc.rpartition("@")
        netloc = f"***@{host}"
    query = "***" if parti.query else parti.query
    return parti._replace(netloc=netloc, query=query, fragment="").geturl()


def valida_formato(url: str) -> SplitResult:
    """Valida schema e host senza toccare la rete (errore inline, 422)."""
    try:
        parti = urlsplit(url.strip())
    except ValueError as exc:
        raise UrlFeedNonValidoError("URL non analizzabile") from exc
    if parti.scheme not in SCHEMI_AMMESSI:
        raise UrlFeedNonValidoError(
            f"schema '{parti.scheme}' non ammesso: solo http o https"
        )
    try:
        hostname, porta = parti.hostname, parti.port
    except ValueError as exc:
        raise UrlFeedNonValidoError("porta non valida") from exc
    if not hostname:
        raise UrlFeedNonValidoError("URL senza host")
    if porta is not None and not 1 <= porta <= 65535:
        raise UrlFeedNonValidoError("porta fuori intervallo")
    return parti


def _indirizzo_vietato(indirizzo: IndirizzoIP, politica: PoliticaUscitaRete) -> bool:
    if any(indirizzo in rete for rete in politica.reti_consentite):
        return False
    mappato = getattr(indirizzo, "ipv4_mapped", None)
    if mappato is not None:
        return _indirizzo_vietato(mappato, politica)
    if any(indirizzo in rete for rete in RETI_VIETATE_AGGIUNTIVE):
        return True
    # NAT64 incapsula un IPv4 negli ultimi 32 bit: senza srotolarlo,
    # `64:ff9b::7f00:1` raggiungerebbe 127.0.0.1 passando per pubblico.
    if isinstance(
        indirizzo, ipaddress.IPv6Address
    ) and indirizzo in ipaddress.ip_network("64:ff9b::/96"):
        return True
    return (
        indirizzo.is_loopback
        or indirizzo.is_private
        or indirizzo.is_link_local
        or indirizzo.is_multicast
        or indirizzo.is_reserved
        or indirizzo.is_unspecified
        # ASSICURAZIONE IN AVANTI, non copertura di oggi. Misurato: su
        # 800 000 indirizzi casuali non esiste una classe in cui questa
        # clausola sia il solo motivo di rifiuto — l'unica candidata, la CGNAT
        # `100.64.0.0/10`, è già in `RETI_VIETATE_AGGIUNTIVE`. Quindi oggi non
        # ha contributo dimostrabile, e dire il contrario sarebbe affermare una
        # copertura che non c'è.
        #
        # Si tiene perché il suo valore è nel FUTURO: quando la IANA assegna
        # una nuova destinazione speciale, `is_global` la prende con un
        # aggiornamento della stdlib, mentre la lista esplicita qui sopra no.
        # E si AGGIUNGE ai controlli espliciti, non li sostituisce: multicast,
        # NAT64 e `fec0::/10` risultano `is_global=True`, quindi da sola questa
        # riga li lascerebbe passare.
        or not indirizzo.is_global
    )


def risolutore_di_sistema(hostname: str) -> list[str]:
    """Risoluzione DNS reale: unico punto in cui la produzione fa I/O."""
    informazioni = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    return [str(voce[4][0]) for voce in informazioni]


def valida_destinazione(
    url: SplitResult,
    politica: PoliticaUscitaRete,
    risolutore: Risolutore = risolutore_di_sistema,
) -> tuple[str, ...]:
    """Indirizzi ammessi per l'host dell'URL, o `DestinazioneNonAmmessaError`.

    Un host che non risolve è già una destinazione non ammessa: l'esito per
    l'Host è lo stesso di un indirizzo vietato, e deve esserlo.
    """
    hostname = url.hostname or ""
    try:
        letterale = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        letterale = None

    if letterale is not None:
        indirizzi: list[IndirizzoIP] = [letterale]
    else:
        try:
            risolti = list(risolutore(hostname))
        except OSError as exc:
            raise DestinazioneNonAmmessaError("host non risolvibile") from exc
        if not risolti:
            raise DestinazioneNonAmmessaError("host senza indirizzi")
        try:
            indirizzi = [ipaddress.ip_address(voce) for voce in risolti]
        except ValueError as exc:
            raise DestinazioneNonAmmessaError("indirizzo non interpretabile") from exc

    for indirizzo in indirizzi:
        if _indirizzo_vietato(indirizzo, politica):
            # Il messaggio resta generico di proposito: l'esito della
            # risoluzione non deve arrivare a chi ha incollato l'URL.
            raise DestinazioneNonAmmessaError("destinazione non ammessa")
    return tuple(str(indirizzo) for indirizzo in indirizzi)


def valida_url_feed(
    url: str,
    politica: PoliticaUscitaRete,
    risolutore: Risolutore = risolutore_di_sistema,
) -> SplitResult:
    """Formato + destinazione: la coppia che ogni hop deve superare."""
    parti = valida_formato(url)
    valida_destinazione(parti, politica, risolutore)
    return parti
