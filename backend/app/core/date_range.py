"""Semantica temporale unica (AD-3).

Una notte di Prenotazione è l'intervallo semiaperto [check_in, check_out)
su date locali Europe/Rome; sovrapposizione = intersezione non vuota.
I timestamp si persistono in UTC; le scadenze normative si calcolano in
Europe/Rome. Nessun modulo reimplementa questa logica: si importa da qui.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

TZ_ROME = ZoneInfo("Europe/Rome")


class EmptyDateRangeError(ValueError):
    """L'intervallo [check_in, check_out) deve contenere almeno una notte."""


class NaiveDatetimeError(ValueError):
    """I timestamp devono essere timezone-aware (persistenza in UTC)."""


@dataclass(frozen=True, slots=True)
class DateRange:
    """Intervallo semiaperto [check_in, check_out) su date locali Europe/Rome."""

    check_in: date
    check_out: date

    def __post_init__(self) -> None:
        if self.check_in >= self.check_out:
            raise EmptyDateRangeError(
                f"intervallo vuoto: [{self.check_in}, {self.check_out})"
            )

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    def overlaps(self, other: "DateRange") -> bool:
        return self.check_in < other.check_out and other.check_in < self.check_out

    def intersection(self, other: "DateRange") -> "DateRange | None":
        if not self.overlaps(other):
            return None
        return DateRange(
            check_in=max(self.check_in, other.check_in),
            check_out=min(self.check_out, other.check_out),
        )

    def contains(self, day: date) -> bool:
        return self.check_in <= day < self.check_out


def utcnow() -> datetime:
    """Istante corrente timezone-aware in UTC (unica sorgente per la persistenza)."""
    return datetime.now(UTC)


def rome_day(instant: datetime) -> date:
    """Giorno locale Europe/Rome di un istante timezone-aware."""
    if instant.tzinfo is None:
        raise NaiveDatetimeError("datetime naive: serve un istante timezone-aware")
    return instant.astimezone(TZ_ROME).date()


def today_rome() -> date:
    return rome_day(utcnow())
