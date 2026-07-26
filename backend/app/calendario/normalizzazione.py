"""VEVENT grezzo → `DateRange` su date locali Europe/Rome (AD-3, AD-4).

È il singolo punto in cui `[check_in, check_out)` incontra la realtà di un
formato che non abbiamo scritto noi. Funzione pura: nessun I/O, nessuna
sessione, nessuna rete.

Scelte dichiarate, perché il silenzio qui costa Prenotazioni (NFR-1):

- `DTEND` di un `VALUE=DATE` è già **esclusivo** in iCal: coincide con
  `check_out` di AD-3 senza correzioni. La corrispondenza si ASSERISCE nei
  test, non si assume.
- Un `DATETIME` si riporta al **giorno locale Europe/Rome**: `Z`, `TZID` e
  floating passano tutti da lì, così l'ora legale non sposta la notte.
- `DTEND` assente si ricava da `DURATION`; senza nessuno dei due l'evento è
  malformato — non si inventa una durata.
- Un `RRULE` **non** si espande nell'MVP: l'evento entra come singola
  occorrenza e resta marcato `ricorrente`, perché un evento ricorrente
  ignorato in silenzio è una Prenotazione persa.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.calendario.ical import Proprieta, Vevent
from app.core.date_range import TZ_ROME, DateRange, rome_day

LUNGHEZZA_MASSIMA_SOMMARIO = 500

_DURATA = re.compile(
    r"^(?P<segno>[+-])?P"
    r"(?:(?P<settimane>\d+)W)?"
    r"(?:(?P<giorni>\d+)D)?"
    r"(?:T(?:(?P<ore>\d+)H)?(?:(?P<minuti>\d+)M)?(?:(?P<secondi>\d+)S)?)?$"
)


class EventoNonNormalizzabileError(ValueError):
    """Il VEVENT non porta i dati minimi per diventare una Prenotazione."""


@dataclass(frozen=True, slots=True)
class EventoFeed:
    ical_uid: str
    soggiorno: DateRange
    sommario: str | None
    cancellato: bool
    ricorrente: bool


def _zona(proprieta: Proprieta) -> ZoneInfo | None:
    tzid = proprieta.parametri.get("TZID")
    if not tzid:
        return None
    try:
        return ZoneInfo(tzid)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise EventoNonNormalizzabileError(f"fuso orario '{tzid}' sconosciuto") from exc


def _giorno_locale(proprieta: Proprieta) -> date:
    """Giorno Europe/Rome della proprietà, qualunque forma abbia il valore."""
    valore = proprieta.valore.strip()
    if proprieta.parametri.get("VALUE", "").upper() == "DATE" or len(valore) == 8:
        try:
            return datetime.strptime(valore, "%Y%m%d").date()
        except ValueError as exc:
            raise EventoNonNormalizzabileError(f"data '{valore}' non valida") from exc
    return _istante(proprieta).astimezone(TZ_ROME).date()


def _istante(proprieta: Proprieta) -> datetime:
    valore = proprieta.valore.strip()
    formato = "%Y%m%dT%H%M%SZ" if valore.endswith("Z") else "%Y%m%dT%H%M%S"
    try:
        naive = datetime.strptime(valore, formato)
    except ValueError as exc:
        raise EventoNonNormalizzabileError(f"istante '{valore}' non valido") from exc
    if valore.endswith("Z"):
        return naive.replace(tzinfo=ZoneInfo("UTC"))
    # Senza `Z` e senza `TZID` il valore è floating: RFC 5545 lo lega all'ora
    # locale di chi lo legge, che per noi è sempre Europe/Rome (AD-3).
    return naive.replace(tzinfo=_zona(proprieta) or TZ_ROME)


def _e_data_pura(proprieta: Proprieta) -> bool:
    valore = proprieta.valore.strip()
    return proprieta.parametri.get("VALUE", "").upper() == "DATE" or len(valore) == 8


def _durata(valore: str) -> timedelta:
    trovato = _DURATA.match(valore.strip())
    if trovato is None or trovato.group(0) in ("P", "-P", "+P"):
        raise EventoNonNormalizzabileError(f"durata '{valore}' non interpretabile")
    pezzi = trovato.groupdict()
    delta = timedelta(
        weeks=int(pezzi["settimane"] or 0),
        days=int(pezzi["giorni"] or 0),
        hours=int(pezzi["ore"] or 0),
        minutes=int(pezzi["minuti"] or 0),
        seconds=int(pezzi["secondi"] or 0),
    )
    return -delta if pezzi["segno"] == "-" else delta


def _fine(vevent: Vevent, inizio: Proprieta) -> date:
    dtend = vevent.prima("DTEND")
    if dtend is not None:
        return _giorno_locale(dtend)
    durata = vevent.prima("DURATION")
    if durata is None:
        raise EventoNonNormalizzabileError("né DTEND né DURATION: durata sconosciuta")
    delta = _durata(durata.valore)
    if _e_data_pura(inizio):
        return _giorno_locale(inizio) + delta
    return rome_day(_istante(inizio) + delta)


def normalizza(vevent: Vevent) -> EventoFeed:
    """Evento del feed pronto per l'upsert, o errore dichiarato.

    Solleva `EventoNonNormalizzabileError` per i dati mancanti o illeggibili
    e lascia passare `EmptyDateRangeError` (AD-3) quando le date sono
    invertite o coincidenti: un soggiorno di zero notti non è un intervallo
    vuoto da tollerare, è un evento da rifiutare.
    """
    uid = vevent.uid
    if uid is None:
        raise EventoNonNormalizzabileError("VEVENT senza UID: identità assente")
    inizio = vevent.prima("DTSTART")
    if inizio is None:
        raise EventoNonNormalizzabileError("VEVENT senza DTSTART")

    soggiorno = DateRange(
        check_in=_giorno_locale(inizio), check_out=_fine(vevent, inizio)
    )
    sommario = vevent.valore("SUMMARY")
    stato = (vevent.valore("STATUS") or "").strip().upper()
    return EventoFeed(
        ical_uid=uid,
        soggiorno=soggiorno,
        sommario=(None if sommario is None else sommario[:LUNGHEZZA_MASSIMA_SOMMARIO]),
        cancellato=stato == "CANCELLED",
        ricorrente=vevent.prima("RRULE") is not None,
    )
