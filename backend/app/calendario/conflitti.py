"""Rilevazione dei Conflitti: la REGOLA, pura (AD-5, AD-3).

Nessun import di sessione, di modello o di rete: la rilevazione è una
funzione dell'insieme delle Prenotazioni `attiva` di una Struttura, e
`tests/test_conflitti_rilevazione.py` la esercita senza database. Se
smettesse di essere chiamabile così, la purezza sarebbe già violata — è un
finding, non un problema di test.

Tre proprietà, e ciascuna esiste per un difetto preciso:

- **il confine è quello di `DateRange`** (AD-3) e non si reimplementa qui:
  `check_out` di una uguale a `check_in` dell'altra non è un Conflitto,
  perché il turnover dello stesso giorno è il caso normale di un affitto
  breve. Reimplementarlo significherebbe che il confine è in un punto nel
  Calendario e in un altro nella rilevazione;
- **la coppia è NON ORDINATA e canonicalizzata** (§4.2-4, ratificato):
  `(A,B)` e `(B,A)` sono la stessa identità. Emetterle entrambe darebbe al
  database due righe da inserire per lo stesso fatto — una la rifiuterebbe
  il vincolo, cioè un errore su un percorso normale;
- **l'unità è la coppia, non il gruppo** (§4.2-5, ratificato): tre
  Prenotazioni sovrapposte a due a due producono TRE Conflitti. Cambia il
  conteggio del badge (2.8) e la misura di SM-1, quindi non è una scelta
  interna.

La rilevazione **non decide cosa decade**: dice quali coppie si sovrappongono
ADESSO. Il `decadere` di un Conflitto è governato dall'uscita di una
Prenotazione dallo stato `attiva` (AD-5, AD-19), che arriva come evento — ed
è la ragione per cui un import fallito, che non produce alcun evento, non può
produrre falsi `decaduto` (AC 11).
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations

from app.core.date_range import DateRange


@dataclass(frozen=True, slots=True)
class PrenotazioneAttiva:
    """Ciò che serve a rilevare, e nient'altro.

    Il nome dichiara la precondizione: entrano SOLO le Prenotazioni in stato
    `attiva` (AD-19). Il filtro vive nella query che le legge — è una
    proprietà del chiamante, e i due difetti sono distinti (test design
    2.5 §10).

    Non è la riga `prenotazione`: portarsi dietro l'entità significherebbe
    che una colonna aggiunta domani entra nella regola senza che nessuno
    l'abbia decisa, e che questa funzione non è più chiamabile senza il
    modello.
    """

    id: uuid.UUID
    struttura_id: uuid.UUID
    soggiorno: DateRange


@dataclass(frozen=True, slots=True)
class CoppiaSovrapposta:
    """L'identità di un Conflitto: `(struttura_id, coppia)` (AD-5).

    I due identificatori sono già in ordine canonico — `min` e `max` — e i
    nomi lo dicono: è la stessa forma dell'indice UNIQUE parziale che impone
    l'invariante nel database, e chiamarli `a` e `b` inviterebbe a
    ricostruire l'ordine altrove.
    """

    struttura_id: uuid.UUID
    prenotazione_min_id: uuid.UUID
    prenotazione_max_id: uuid.UUID


def coppie_sovrapposte(
    prenotazioni: Iterable[PrenotazioneAttiva],
) -> list[CoppiaSovrapposta]:
    """Le coppie che si sovrappongono, in ordine STABILE.

    Il confronto è fra Prenotazioni della STESSA Struttura: due appartamenti
    pieni la stessa settimana sono un Host che lavora, non un Conflitto
    (AD-2, AD-3). Il perimetro è nel criterio e non solo nella query perché
    sono due difetti diversi, e questo è quello che nessun chiamante può
    reintrodurre.

    L'ordine dell'esito non dipende dall'ordine dell'ingresso: una rilevazione
    rieseguita sullo stesso insieme deve dare la stessa sequenza, altrimenti
    due esecuzioni non sono confrontabili — a partire dai test.

    Quadratico nel numero di Prenotazioni **di una Struttura**, che è la
    dimensione giusta: un Host con 1-3 appartamenti ne ha decine, e una
    sofisticazione (ordinamento per `check_in` e uscita anticipata) sarebbe
    codice in più su un insieme che sta in una schermata.
    """
    per_struttura: dict[uuid.UUID, list[PrenotazioneAttiva]] = {}
    for riga in prenotazioni:
        per_struttura.setdefault(riga.struttura_id, []).append(riga)

    coppie: set[CoppiaSovrapposta] = set()
    for struttura_id, insieme in per_struttura.items():
        for prima, seconda in combinations(insieme, 2):
            # Una Prenotazione non è in conflitto con sé stessa: se il
            # chiamante l'ha passata due volte, il confronto è perfetto e
            # produrrebbe un Conflitto con `min == max`.
            if prima.id == seconda.id:
                continue
            if not prima.soggiorno.overlaps(seconda.soggiorno):
                continue
            coppie.add(
                CoppiaSovrapposta(
                    struttura_id=struttura_id,
                    prenotazione_min_id=min(prima.id, seconda.id),
                    prenotazione_max_id=max(prima.id, seconda.id),
                )
            )
    return sorted(
        coppie,
        key=lambda riga: (
            riga.struttura_id,
            riga.prenotazione_min_id,
            riga.prenotazione_max_id,
        ),
    )


__all__ = ["CoppiaSovrapposta", "PrenotazioneAttiva", "coppie_sovrapposte"]
