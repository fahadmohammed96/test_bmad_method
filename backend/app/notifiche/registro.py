"""Il registro dei compositori: come `notifiche` resta ignorante del dominio.

Il testo di una notifica dipende da dati che vivono in un altro modulo — la
Struttura e le date di un Conflitto stanno in `calendario` — e lo spine vieta
a `notifiche` di chiamarlo: l'unica dipendenza sincrona ammessa è `identity`,
in sola lettura. Se il testo lo componesse questo modulo, la fondazione che
l'Epic 3 e l'Epic 5 devono riusare nascerebbe legata al calendario (AC 4,
AC 11).

Qui si dichiara quindi solo il **contratto**: dato un `host_id` e il
riferimento, restituisci un `Messaggio`. Chi lo implementa è la radice di
composizione (`app/cablaggio.py`), che è l'unico posto autorizzato a conoscere
due moduli insieme. `notifiche` conosce una stringa e una funzione.

Il registro è anche il **catalogo** dei tipi di notifica (AD-17): un tipo
senza compositore non è consegnabile, e chiederne uno solleva invece di
produrre una notifica muta.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class Messaggio:
    """Il testo consegnato: un oggetto e un corpo, già in it-IT.

    Non porta destinatario né canale: chi lo compone non sa su quale canale
    finirà, ed è il motivo per cui lo stesso testo serve l'in-app e l'email
    senza doppioni di copy.
    """

    oggetto: str
    corpo: str


class FattoScomparsoError(Exception):
    """Il riferimento non esiste più: non c'è niente da raccontare.

    Non ha un trattamento suo — risale come qualunque altro fallimento del
    percorso di consegna, e il job si ritenta e poi va `failed` con questo
    nome scritto in `last_error`. Esiste per quel nome: un job fallito che
    dice «fatto scomparso» si diagnostica, uno che dice `AttributeError` no.
    """


class TipoNotificaSconosciutoError(Exception):
    """Nessun compositore per questo tipo: la notifica non ha un testo."""


# `(db, host_id, riferimento_id) -> Messaggio`. Riceve la sessione perché il
# testo si compone alla consegna LEGGENDO LO STATO CORRENTE (AC 6): un testo
# calcolato alla richiesta e trasportato nel payload sarebbe una fotografia
# scritta in una tabella append-only.
Compositore = Callable[[Session, uuid.UUID, uuid.UUID], Messaggio]


class CompositoriNotifica:
    """Registro dei tipi di notifica e del testo di ciascuno."""

    def __init__(self) -> None:
        self._compositori: dict[str, Compositore] = {}

    def registra(self, tipo: str) -> Callable[[Compositore], Compositore]:
        def decoratore(fn: Compositore) -> Compositore:
            self._compositori[tipo] = fn
            return fn

        return decoratore

    def compositore_per(self, tipo: str) -> Compositore:
        try:
            return self._compositori[tipo]
        except KeyError:
            raise TipoNotificaSconosciutoError(
                f"nessun compositore per '{tipo}': il tipo non è a catalogo "
                "(AD-17) e la notifica non avrebbe testo"
            ) from None


# Registro di produzione: la radice di composizione registra qui all'avvio del
# worker, con lo stesso effetto-di-import degli handler di job.
compositori = CompositoriNotifica()
