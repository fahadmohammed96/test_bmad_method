"""Test della semantica temporale unica (AD-3).

Intervallo semiaperto [check_in, check_out) su date locali Europe/Rome;
sovrapposizione = intersezione non vuota; timestamp persistiti in UTC.
"""

from datetime import UTC, date, datetime

import pytest

from app.core.date_range import (
    TZ_ROME,
    DateRange,
    EmptyDateRangeError,
    NaiveDatetimeError,
    rome_day,
    utcnow,
)


class TestDateRangeInvariants:
    def test_check_in_deve_precedere_check_out(self) -> None:
        with pytest.raises(EmptyDateRangeError):
            DateRange(check_in=date(2026, 8, 15), check_out=date(2026, 8, 15))

    def test_check_out_prima_del_check_in_rifiutato(self) -> None:
        with pytest.raises(EmptyDateRangeError):
            DateRange(check_in=date(2026, 8, 17), check_out=date(2026, 8, 15))

    def test_notti_di_un_soggiorno(self) -> None:
        r = DateRange(check_in=date(2026, 8, 15), check_out=date(2026, 8, 17))
        assert r.nights == 2

    def test_e_immutabile(self) -> None:
        r = DateRange(check_in=date(2026, 8, 15), check_out=date(2026, 8, 17))
        with pytest.raises(AttributeError):
            r.check_in = date(2026, 8, 16)  # type: ignore[misc]


class TestOverlapSemiOpen:
    """Sovrapposizione = intersezione non vuota di intervalli semiaperti."""

    def test_intervalli_adiacenti_non_si_sovrappongono(self) -> None:
        # Il check-out del primo coincide col check-in del secondo:
        # nessuna doppia prenotazione (semantica semiaperta).
        a = DateRange(check_in=date(2026, 8, 1), check_out=date(2026, 8, 3))
        b = DateRange(check_in=date(2026, 8, 3), check_out=date(2026, 8, 5))
        assert not a.overlaps(b)
        assert not b.overlaps(a)

    def test_sovrapposizione_parziale(self) -> None:
        a = DateRange(check_in=date(2026, 8, 1), check_out=date(2026, 8, 4))
        b = DateRange(check_in=date(2026, 8, 3), check_out=date(2026, 8, 6))
        assert a.overlaps(b)
        assert b.overlaps(a)

    def test_contenimento_totale(self) -> None:
        outer = DateRange(check_in=date(2026, 8, 1), check_out=date(2026, 8, 10))
        inner = DateRange(check_in=date(2026, 8, 4), check_out=date(2026, 8, 5))
        assert outer.overlaps(inner)
        assert inner.overlaps(outer)

    def test_intervalli_disgiunti(self) -> None:
        a = DateRange(check_in=date(2026, 8, 1), check_out=date(2026, 8, 3))
        b = DateRange(check_in=date(2026, 8, 10), check_out=date(2026, 8, 12))
        assert not a.overlaps(b)

    def test_intersezione_non_vuota(self) -> None:
        a = DateRange(check_in=date(2026, 8, 1), check_out=date(2026, 8, 4))
        b = DateRange(check_in=date(2026, 8, 3), check_out=date(2026, 8, 6))
        both = a.intersection(b)
        assert both == DateRange(check_in=date(2026, 8, 3), check_out=date(2026, 8, 4))

    def test_intersezione_vuota_e_none(self) -> None:
        a = DateRange(check_in=date(2026, 8, 1), check_out=date(2026, 8, 3))
        b = DateRange(check_in=date(2026, 8, 3), check_out=date(2026, 8, 5))
        assert a.intersection(b) is None

    def test_contains_semiaperto(self) -> None:
        r = DateRange(check_in=date(2026, 8, 1), check_out=date(2026, 8, 3))
        assert r.contains(date(2026, 8, 1))
        assert r.contains(date(2026, 8, 2))
        assert not r.contains(date(2026, 8, 3))


class TestTimeSemantics:
    def test_utcnow_e_timezone_aware_utc(self) -> None:
        now = utcnow()
        assert now.tzinfo is not None
        assert now.utcoffset() == UTC.utcoffset(now)

    def test_rome_day_converte_un_istante_utc(self) -> None:
        # 2026-08-15 22:30 UTC = 2026-08-16 00:30 Europe/Rome (CEST, UTC+2)
        instant = datetime(2026, 8, 15, 22, 30, tzinfo=UTC)
        assert rome_day(instant) == date(2026, 8, 16)

    def test_rome_day_in_inverno(self) -> None:
        # 2026-01-15 23:30 UTC = 2026-01-16 00:30 Europe/Rome (CET, UTC+1)
        instant = datetime(2026, 1, 15, 23, 30, tzinfo=UTC)
        assert rome_day(instant) == date(2026, 1, 16)

    def test_rome_day_rifiuta_datetime_naive(self) -> None:
        with pytest.raises(NaiveDatetimeError):
            rome_day(datetime(2026, 8, 15, 22, 30))

    def test_tz_rome_e_europe_rome(self) -> None:
        assert str(TZ_ROME) == "Europe/Rome"
