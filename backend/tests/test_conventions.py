"""Test delle Consistency Conventions dello spine.

UUIDv7 come PK, importi in centesimi interi, enum di stato con literal stabili.
"""

from decimal import Decimal

import pytest

from app.core.db import new_uuid7
from app.core.jobs import JobStatus
from app.core.money import eur_to_cent


class TestUuid7:
    def test_le_pk_sono_uuid_versione_7(self) -> None:
        assert new_uuid7().version == 7

    def test_uuid7_ordinabili_temporalmente(self) -> None:
        # UUIDv7 è time-ordered: generazioni successive crescono.
        prima = [new_uuid7() for _ in range(50)]
        assert prima == sorted(prima)


class TestImportiInCentesimi:
    def test_conversione_euro_centesimi(self) -> None:
        assert eur_to_cent(Decimal("145.00")) == 14500

    def test_arrotondamento_half_up(self) -> None:
        assert eur_to_cent(Decimal("10.005")) == 1001
        assert eur_to_cent(Decimal("10.004")) == 1000

    def test_stringa_decimale_accettata(self) -> None:
        assert eur_to_cent("99.90") == 9990

    def test_float_rifiutato(self) -> None:
        # I float introducono errori binari sugli importi: vietati.
        with pytest.raises(TypeError):
            eur_to_cent(99.90)  # type: ignore[arg-type]


class TestEnumDiStato:
    def test_literal_stato_job_stabili(self) -> None:
        assert {s.value for s in JobStatus} == {
            "pending",
            "running",
            "completed",
            "failed",
        }
