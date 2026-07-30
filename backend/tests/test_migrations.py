"""Test delle migrazioni Alembic forward-only (AR-11)."""

import re
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[1]
VERSIONI = BACKEND_DIR / "alembic" / "versions"

_REVISION = re.compile(r"^revision\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


def _config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def test_upgrade_head_crea_le_tabelle_core(pg_engine: Engine) -> None:
    # L'upgrade è già stato eseguito dalla fixture di sessione.
    tabelle = set(inspect(pg_engine).get_table_names())
    assert {"outbox", "job"} <= tabelle


def test_il_downgrade_e_vietato(pg_engine: Engine) -> None:
    with pytest.raises(Exception, match="forward-only"):
        command.downgrade(_config(), "-1")


# ---------------------------------------------------------------------------
# Guardia sul GRAFO delle migrazioni (MYL-72).
#
# Il 30/07 `main` è rimasto rosso per quattro merge consecutivi con 431 test in
# errore: le PR #52 e #53 avevano aggiunto ciascuna una migrazione `revision =
# "0013"` con `down_revision = "0012"`. Alembic si è trovato due head, e
# `command.upgrade(cfg, "head")` — che la fixture di sessione `pg_engine`
# esegue prima di QUALUNQUE test su database — è morto con `MultipleHeads`.
# Da lì in poi ogni test che tocca Postgres è un errore, e il messaggio non
# nomina la causa.
#
# Perché nessun cancello se ne è accorto: il difetto **non esiste in nessuna
# delle due PR**. Ognuna era verde sulla propria base, dove l'altra `0013` non
# c'era ancora; nasce nel trunk, all'atto del secondo merge. È la stessa forma
# della PR #36 che ha prodotto `base-della-pr.yml` — il difetto sta *fra* i
# controlli, e il posto dove va cercato è l'albero risultante, non il diff.
#
# Queste due guardie girano SENZA database di proposito: sono le prime a
# cadere, e cadono dicendo cosa è rotto invece di lasciare 431 errori che
# parlano di connessioni.
# ---------------------------------------------------------------------------


def _revisioni_per_file() -> dict[Path, str]:
    revisioni: dict[Path, str] = {}
    for file in sorted(VERSIONI.glob("*.py")):
        trovate = _REVISION.findall(file.read_text("utf-8"))
        assert trovate, f"{file.name}: nessun `revision = ...` trovato"
        revisioni[file] = trovate[0]
    return revisioni


def test_nessun_identificativo_di_revisione_e_usato_due_volte() -> None:
    """Due file con la stessa `revision` sono un merge andato male, non una scelta.

    Controllo puramente testuale, e non via `ScriptDirectory`: quando due file
    dichiarano lo stesso identificativo, Alembic ne carica uno e degrada
    l'altro a `UserWarning` — cioè la duplicazione è già invisibile allo
    strumento che dovrebbe segnalarla.
    """
    revisioni = _revisioni_per_file()
    per_identificativo: dict[str, list[str]] = {}
    for file, revisione in revisioni.items():
        per_identificativo.setdefault(revisione, []).append(file.name)

    duplicate = {r: f for r, f in per_identificativo.items() if len(f) > 1}
    assert duplicate == {}, (
        f"identificativi di revisione usati più volte: {duplicate}. "
        "Due Story hanno numerato la propria migrazione sulla stessa base: "
        "rinumerare quella arrivata per seconda e agganciarla alla prima "
        "(`down_revision`), mai lasciarle entrambe appese a `0012`."
    )


def test_le_migrazioni_hanno_una_sola_head() -> None:
    """`command.upgrade(cfg, "head")` esiste solo se la head è una.

    Il ramo parallelo è tecnicamente legittimo in Alembic (si chiude con una
    revisione di merge) ma qui non lo è: le migrazioni sono forward-only e
    lineari (AR-11), e `conftest.py` fa `upgrade(head)` al singolare.
    """
    heads = ScriptDirectory.from_config(_config()).get_heads()
    assert len(heads) == 1, (
        f"il grafo delle migrazioni ha {len(heads)} head ({heads}), e "
        "`upgrade(head)` non sa quale scegliere: ogni test su database "
        "diventa un errore che parla di connessioni invece che di migrazioni."
    )
