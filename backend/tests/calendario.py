"""Helper condivisi dei test di `calendario`: costruttori, non asserzioni.

Estratti da `test_calendario_sync.py` quando la Story 2.2 ha portato a tre i
file che ne hanno bisogno. Importarli da un file di test funzionava, ma la
fixture `contesto` importata insieme a loro diventava una ridefinizione a ogni
test che la richiedeva come parametro — le fixture si condividono dal
`conftest.py`, gli helper puri da un modulo.

Nessun dato reale di Ospiti (NFR-16): gli indirizzi sono `example.com`, i
Comuni sono inventati.
"""

import ipaddress
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import CanaleFeed, FeedIcal, Prenotazione, SyncRun
from app.calendario.trasporto import ClientFeedHttp
from app.calendario.uscita_rete import PoliticaUscitaRete
from app.identity.models import Host
from app.strutture.models import Struttura

FIXTURES = Path(__file__).parent / "fixtures" / "ical"
LOOPBACK = (ipaddress.ip_network("127.0.0.0/8"),)


def fixture_ical(nome: str) -> bytes:
    return (FIXTURES / nome).read_bytes()


def calendario(*eventi: str) -> bytes:
    corpo = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "".join(eventi) + "END:VCALENDAR\r\n"
    return corpo.encode("utf-8")


def vevent(uid: str, *, dal: str, al: str, extra: str = "") -> str:
    return (
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTART;VALUE=DATE:{dal}\r\n"
        f"DTEND;VALUE=DATE:{al}\r\n"
        f"SUMMARY:Prenotazione inventata {uid}\r\n"
        f"{extra}"
        "END:VEVENT\r\n"
    )


def politica(
    *,
    cap: int = 1_000_000,
    lettura: float = 5.0,
    max_redirect: int = 3,
    deadline: float = 30.0,
    reti_consentite: tuple = LOOPBACK,
) -> PoliticaUscitaRete:
    return PoliticaUscitaRete(
        timeout_connessione_secondi=2.0,
        timeout_lettura_secondi=lettura,
        dimensione_massima_byte=cap,
        max_redirect=max_redirect,
        deadline_totale_secondi=deadline,
        reti_consentite=reti_consentite,
    )


def client(**kwargs) -> ClientFeedHttp:
    """Client REALE con la politica del test: il confine resta la socket."""
    return ClientFeedHttp(politica(**kwargs))


@dataclass(frozen=True, slots=True)
class Contesto:
    host_id: uuid.UUID
    struttura_id: uuid.UUID


def crea_host(db: Session, email: str) -> Host:
    host = Host(email=email, password_hash="$argon2id$finto")
    db.add(host)
    db.flush()
    return host


def crea_struttura(db: Session, host_id: uuid.UUID, nome: str) -> Struttura:
    struttura = Struttura(
        host_id=host_id, nome=nome, comune="Testopoli", regione="Emilia-Romagna"
    )
    db.add(struttura)
    db.flush()
    return struttura


def crea_contesto(db: Session, *, email: str, nome: str) -> Contesto:
    host = crea_host(db, email)
    struttura = crea_struttura(db, host.id, nome)
    db.commit()
    return Contesto(host_id=host.id, struttura_id=struttura.id)


def collega(
    db: Session, contesto: Contesto, url: str, canale: CanaleFeed = CanaleFeed.AIRBNB
) -> FeedIcal:
    return service.collega_feed(
        db,
        contesto.host_id,
        service.DatiFeed(struttura_id=contesto.struttura_id, url=url, canale=canale),
    )


def sincronizza(db: Session, feed: FeedIcal, trasporto: ClientFeedHttp) -> SyncRun:
    run = service.esegui_sync(db, feed.host_id, feed.id, client=trasporto)
    db.commit()
    return run


def prenotazioni(db: Session, feed: FeedIcal) -> list[Prenotazione]:
    return service.prenotazioni_del_feed(db, feed.host_id, feed.id)
