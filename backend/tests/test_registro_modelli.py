"""Guardia: i metadati di Alembic non possono perdere una tabella.

`alembic --autogenerate` confronta il database con `target_metadata`. Se un
modulo non è importato, le sue tabelle non compaiono nei metadati e
l'autogenerate propone `op.drop_table(...)`: la migrazione distruttiva più
probabile del progetto non nasce da malizia, nasce da un import mancante.

`env.py` non si può importare in un test — a import-time esegue le migrazioni.
La discovery vive quindi in `app.registro_modelli`, che è ciò che `env.py`
usa, e qui si verifica che copra davvero tutto.

**I bersagli si derivano dal FILESYSTEM, non da `moduli_di_dominio()`.** Una
guardia che chiede alla funzione sotto test quali moduli esistono è
autoreferenziale: aggiungere `strutture` a `MODULI_NON_DI_DOMINIO` lo farebbe
sparire dai metadati con tutti i test verdi.
"""

import ast
import json
import pathlib
import subprocess
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
APP = BACKEND / "app"


def _tabelle_dichiarate_nel_sorgente(percorso: pathlib.Path) -> set[str]:
    """`__tablename__ = "..."` presenti nel file, letti come TESTO.

    Anche questo passa dal filesystem e non dall'import: chiedere al modulo
    importato quali tabelle dichiara significherebbe importarlo, cioè fare da
    sé il lavoro che la guardia deve verificare che qualcun altro faccia.
    """
    albero = ast.parse(percorso.read_text(encoding="utf-8"))
    nomi: set[str] = set()
    for nodo in ast.walk(albero):
        if not isinstance(nodo, ast.Assign):
            continue
        bersagli = [b.id for b in nodo.targets if isinstance(b, ast.Name)]
        if "__tablename__" in bersagli and isinstance(nodo.value, ast.Constant):
            nomi.add(str(nodo.value.value))
    return nomi


def _sorgenti_con_tabelle() -> dict[pathlib.Path, set[str]]:
    trovate = {}
    for percorso in sorted(APP.rglob("*.py")):
        tabelle = _tabelle_dichiarate_nel_sorgente(percorso)
        if tabelle:
            trovate[percorso] = tabelle
    return trovate


SCOPERTA_IN_PROCESSO_FRESCO = """
import json
from app.registro_modelli import importa_tutti_i_modelli

print(json.dumps(sorted(importa_tutti_i_modelli().metadata.tables)))
"""


def _tabelle_scoperte_in_processo_fresco() -> set[str]:
    """Tabelle che la discovery trova in un interprete NUOVO.

    Confrontare col `Base.metadata` di QUESTO processo non dimostra niente:
    pytest ha già importato i moduli di dominio per via di altri file di test,
    quindi le tabelle sono nei metadati anche se la discovery le salta.
    Aggiungere `calendario` a `MODULI_NON_DI_DOMINIO` lasciava il test verde in
    suite completa e rosso solo lanciando il file da solo — la forma peggiore,
    verde dove conta.
    """
    esito = subprocess.run(
        [sys.executable, "-c", SCOPERTA_IN_PROCESSO_FRESCO],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert esito.returncode == 0, (
        f"la discovery non gira in un interprete fresco:\n{esito.stderr[-2000:]}"
    )
    return set(json.loads(esito.stdout))


def test_ogni_tabella_dichiarata_nel_sorgente_e_scoperta_da_sola() -> None:
    scoperte = _tabelle_scoperte_in_processo_fresco()
    mancanti = {
        str(percorso.relative_to(BACKEND)): sorted(tabelle - scoperte)
        for percorso, tabelle in _sorgenti_con_tabelle().items()
        if tabelle - scoperte
    }
    assert mancanti == {}, (
        f"tabelle dichiarate nel sorgente ma non scoperte: {mancanti} — "
        "l'autogenerate proporrebbe di cancellarle"
    )


def test_la_guardia_trova_qualcosa_da_controllare() -> None:
    # Non deve mai svuotarsi in silenzio: se il rilevamento delle
    # dichiarazioni si rompesse, il test sopra passerebbe a vuoto.
    sorgenti = _sorgenti_con_tabelle()
    assert len(sorgenti) >= 4
    tutte = {tabella for tabelle in sorgenti.values() for tabella in tabelle}
    # Dominio E infrastruttura: `app/core/` dichiara tabelle fuori dai moduli
    # di dominio, ed era il punto in cui la discovery aveva ancora un elenco
    # scritto a mano.
    assert {"feed_ical", "sync_run", "prenotazione"} <= tutte
    assert {"outbox", "job"} <= tutte


def _punta_ai_modelli(nome: str) -> bool:
    pezzi = nome.split(".")
    if len(pezzi) < 2 or pezzi[0] != "app":
        return False
    # `app.<modulo>.models`, `app.core.jobs`, `app.core.outbox`: i moduli che
    # dichiarano tabelle, in qualunque forma vengano importati.
    return "models" in pezzi[1:] or pezzi[-1] in {"jobs", "outbox"}


def _import_a_mano(sorgente: str) -> list[str]:
    """Import che puntano a moduli con tabelle, in qualunque forma.

    Prende il SORGENTE e non il percorso, così la sentinella qui sotto può
    darle codice finto: la versione precedente esercitava solo
    `_punta_ai_modelli`, quindi cancellare il ramo `ast.Import` non faceva
    cadere nulla — nessun sorgente veniva mai attraversato.
    """
    albero = ast.parse(sorgente)
    a_mano: list[str] = []
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            a_mano += [
                alias.name for alias in nodo.names if _punta_ai_modelli(alias.name)
            ]
        elif isinstance(nodo, ast.ImportFrom):
            modulo = nodo.module or ""
            if _punta_ai_modelli(modulo):
                a_mano.append(modulo)
            else:
                a_mano += [
                    f"{modulo}.{alias.name}"
                    for alias in nodo.names
                    if _punta_ai_modelli(f"{modulo}.{alias.name}")
                ]
    return a_mano


def test_env_di_alembic_non_importa_i_modelli_a_mano() -> None:
    sorgente = (BACKEND / "alembic" / "env.py").read_text(encoding="utf-8")
    a_mano = _import_a_mano(sorgente)
    assert a_mano == [], (
        f"env.py importa modelli a mano: {a_mano} — un modulo nuovo "
        "sfuggirebbe ad Alembic senza far fallire nulla"
    )


@pytest.mark.parametrize(
    "sorgente",
    [
        # Le tre forme che il match di stringa `"models as _" not in sorgente`
        # non vedeva, piu' l'import assoluto.
        "from app.strutture import models",
        "import app.strutture.models",
        "from app.identity.models import *",
        "from app.core import jobs",
        "import app.core.outbox as _o",
    ],
)
def test_la_sentinella_riconosce_ogni_forma_di_import_a_mano(sorgente: str) -> None:
    # Esercita il VISITATORE su sorgenti finti: e' l'unico modo perche' i rami
    # `ast.Import` e `ast.ImportFrom` siano davvero attraversati.
    assert _import_a_mano(sorgente), f"forma non riconosciuta: {sorgente}"


@pytest.mark.parametrize(
    "sorgente",
    [
        "from app.registro_modelli import importa_tutti_i_modelli",
        "from app.core.config import get_settings",
        "from sqlalchemy import create_engine",
        "target_metadata = importa_tutti_i_modelli().metadata",
    ],
)
def test_la_sentinella_non_segnala_gli_import_legittimi(sorgente: str) -> None:
    # L'altra metà: una sentinella che segnala tutto non discrimina, e
    # `env.py` deve poter importare la discovery.
    assert _import_a_mano(sorgente) == []


def test_env_di_alembic_usa_la_discovery() -> None:
    sorgente = (BACKEND / "alembic" / "env.py").read_text(encoding="utf-8")
    assert "importa_tutti_i_modelli" in sorgente
