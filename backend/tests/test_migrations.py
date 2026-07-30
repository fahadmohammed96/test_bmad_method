"""Test delle migrazioni Alembic forward-only (AR-11)."""

import re
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = BACKEND_DIR / "alembic" / "versions"

# `20260730_0014_prenotazione_manuale.py` → data, ordinale, slug.
NOME_MIGRAZIONE = re.compile(r"^(?P<data>\d{8})_(?P<ordinale>\d{4})_(?P<slug>\w+)\.py$")


def _config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def _file_migrazione() -> list[Path]:
    return sorted(p for p in VERSIONS_DIR.glob("*.py") if p.name != "__init__.py")


def test_upgrade_head_crea_le_tabelle_core(pg_engine: Engine) -> None:
    # L'upgrade è già stato eseguito dalla fixture di sessione.
    tabelle = set(inspect(pg_engine).get_table_names())
    assert {"outbox", "job"} <= tabelle


def test_il_downgrade_e_vietato(pg_engine: Engine) -> None:
    with pytest.raises(Exception, match="forward-only"):
        command.downgrade(_config(), "-1")


class TestCatenaLineare:
    """La catena delle migrazioni ha una sola punta (MYL-75).

    Due Story parallele che aggiungono ciascuna «la prossima migrazione»
    scelgono lo stesso ordinale e lo stesso `down_revision`: ognuna è
    coerente da sola, la collisione nasce SOLO sull'albero unito, e git non
    la vede perché i due file hanno nomi diversi — nessun conflitto testuale
    da risolvere. Successo il 30/07 con le PR #52 e #53, mergiate a nove
    secondi di distanza: `alembic upgrade head` su `main` ha smesso di
    sapere quale sia la testa, e con lui il job `backend` e gli e2e, che
    avviano il backend proprio con quel comando.

    Questi test girano senza database, e sul push a `main` girano sul vero
    albero unito: è lì che il difetto esiste.
    """

    def test_i_file_hanno_il_nome_convenzionale(self) -> None:
        fuori_convenzione = [
            p.name for p in _file_migrazione() if not NOME_MIGRAZIONE.match(p.name)
        ]
        # Un nome fuori convenzione non è pedanteria: sfuggirebbe al
        # controllo sugli ordinali qui sotto, che sul nome si regge.
        assert fuori_convenzione == []

    def test_nessun_ordinale_duplicato(self) -> None:
        per_ordinale: dict[str, list[str]] = {}
        for percorso in _file_migrazione():
            trovato = NOME_MIGRAZIONE.match(percorso.name)
            assert trovato is not None
            per_ordinale.setdefault(trovato["ordinale"], []).append(percorso.name)

        collisioni = {k: v for k, v in per_ordinale.items() if len(v) > 1}
        assert collisioni == {}, (
            f"Ordinali usati da più migrazioni: {collisioni}. "
            "Rinumera l'ultima arrivata e correggine il `down_revision`."
        )

    def test_ordinale_del_file_uguale_alla_revisione(self) -> None:
        # Senza questo, rinumerare il solo NOME di un file zittirebbe il test
        # sopra lasciando intatta la collisione vera, che è fra le `revision`.
        disallineati = {}
        for percorso in _file_migrazione():
            trovato = NOME_MIGRAZIONE.match(percorso.name)
            assert trovato is not None
            revisione = re.search(
                r'^revision = "(?P<id>[^"]+)"', percorso.read_text(encoding="utf-8"), re.M
            )
            assert revisione is not None, f"{percorso.name}: manca `revision = \"…\"`"
            if revisione["id"] != trovato["ordinale"]:
                disallineati[percorso.name] = revisione["id"]
        assert disallineati == {}

    def test_una_sola_head(self) -> None:
        # Il controllo che morde a valle di qualunque forma di divergenza,
        # anche quelle che i nomi dei file non mostrano: due `down_revision`
        # sullo stesso genitore con ordinali diversi biforcano comunque.
        teste = ScriptDirectory.from_config(_config()).get_heads()
        assert len(teste) == 1, (
            f"La catena ha {len(teste)} teste ({teste}): "
            "`alembic upgrade head` non può scegliere."
        )
