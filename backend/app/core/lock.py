"""Namespace dei lock consultivi di Postgres — la convenzione di RT-3.

`pg_advisory_xact_lock(namespace, chiave)` prende due interi a 32 bit e li
tratta come una sola chiave a 64 bit. Il `namespace` è ciò che impedisce a
due percorsi scorrelati di serializzarsi a vicenda: senza, `hashtext(host_id)`
del cap Strutture e `hashtext(feed_id)` del poller potrebbero collidere e un
Host che collega un Feed bloccherebbe la creazione di una Struttura di un
altro Host — un accoppiamento invisibile, senza errore, che si manifesta solo
sotto carico.

Finché di advisory lock ce n'era **uno** la convenzione poteva restare
implicita (RT-3 del test design dell'Epic 1: «rivalutare al secondo advisory
lock»). Questo è il secondo, quindi la convenzione si scrive:

1. ogni percorso serializzato dichiara il proprio namespace **qui**, mai in
   linea nel modulo che lo usa;
2. i namespace sono distinti, e la guardia
   `tests/test_lock_convention.py` lo impone insieme al divieto di
   `pg_advisory_*` con un namespace letterale fuori da questo modulo;
3. il lock è legato alla TRANSAZIONE (`_xact_`): si rilascia da solo al commit
   o al rollback, quindi non esiste un percorso di errore che lo lasci
   appeso.

Il lock è consultivo: non protegge una tabella, protegge una **sequenza**
leggi-poi-scrivi che nessun vincolo del database può arbitrare da sé.
"""

import uuid
from typing import Final

from sqlalchemy import text
from sqlalchemy.orm import Session

# Cap di prodotto sulle Strutture ATTIVE di un Host (F-1, Story 1.4):
# conta-poi-inserisci.
NAMESPACE_CAP_STRUTTURE: Final = 1001

# Bootstrap del ciclo periodico di sync di un Feed (A3-3, Story 2.2):
# «c'è già un job in coda?»-poi-`schedule`.
NAMESPACE_SYNC_PERIODICO: Final = 1002

# I tre che seguono serializzano un bootstrap SINGOLETTO: un solo ciclo in
# coda per tutto il sistema, non uno per risorsa. Namespace distinti anche fra
# loro — con un namespace condiviso il bootstrap del purge sessioni e quello
# della retention Ospite si aspetterebbero a vicenda all'avvio del worker,
# senza alcun errore e senza alcuna ragione.
NAMESPACE_PURGE_SESSIONI: Final = 1003
NAMESPACE_RETENTION_OSPITE: Final = 1004
NAMESPACE_PURGE_JOB: Final = 1005

# Chiave costante dei percorsi singoletto: la risorsa contesa è UNA, quindi
# non c'è nulla da cui derivare la chiave. È il namespace a distinguerli.
CHIAVE_SINGOLETTO: Final = "singoletto"


def blocca(db: Session, namespace: int, chiave: str) -> None:
    """Serializza per `(namespace, chiave)` fino alla fine della transazione.

    `hashtext` riduce la chiave applicativa a 32 bit: due chiavi diverse
    possono collidere e serializzare due sequenze scorrelate. È un costo di
    prestazioni trascurabile, mai un errore di correttezza — l'opposto della
    collisione fra namespace, che invece serializzerebbe percorsi che non
    sanno l'uno dell'altro.
    """
    db.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:chiave))"),
        {"namespace": namespace, "chiave": chiave},
    )


def blocca_per_id(db: Session, namespace: int, identificatore: uuid.UUID) -> None:
    """`blocca` per le chiavi che sono un UUID, che è il caso normale."""
    blocca(db, namespace, str(identificatore))


def blocca_singoletto(db: Session, namespace: int) -> None:
    """`blocca` per un percorso che è UNO per tutto il sistema.

    Il lock per RISORSA (`blocca_per_id`) è la forma preferibile ovunque
    esista una risorsa: due Feed non si aspettano mai, e una serializzazione
    globale trasformerebbe il bootstrap dell'avvio in una fila indiana senza
    che nessun conteggio lo dica. Ma i cicli periodici di manutenzione — purge
    delle sessioni, retention dell'anagrafica Ospite, purge della coda `job` —
    sono singoletti per costruzione: **un solo** job in coda per l'intero
    sistema. Lì non c'è alcuna risorsa da cui derivare la chiave, e inventarne
    una darebbe l'illusione di una granularità che non esiste.

    Che la chiave sia costante è quindi la forma giusta e non una scorciatoia,
    ma rende il namespace l'unica cosa che separa questi percorsi: due che ne
    condividessero uno si serializzerebbero a vicenda in silenzio. È la
    ragione per cui i namespace stanno tutti qui sopra, in un posto in cui si
    vede se collidono.
    """
    blocca(db, namespace, CHIAVE_SINGOLETTO)
