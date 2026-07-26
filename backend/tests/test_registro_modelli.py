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
import pathlib

from app.registro_modelli import importa_tutti_i_modelli

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


def test_ogni_tabella_dichiarata_nel_sorgente_e_nei_metadati() -> None:
    metadata = importa_tutti_i_modelli().metadata
    mancanti = {
        str(percorso.relative_to(BACKEND)): sorted(tabelle - set(metadata.tables))
        for percorso, tabelle in _sorgenti_con_tabelle().items()
        if tabelle - set(metadata.tables)
    }
    assert mancanti == {}, (
        f"tabelle dichiarate nel sorgente ma assenti dai metadati: {mancanti} — "
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


def test_env_di_alembic_non_importa_i_modelli_a_mano() -> None:
    # Non un match di stringa: `"models as _" not in sorgente` passava su
    # `from app.strutture import models` senza alias, su
    # `import app.strutture.models` e su `from app.identity.models import *`.
    # Un ibrido (discovery mantenuta + import rimessi a mano) la evadeva.
    albero = ast.parse((BACKEND / "alembic" / "env.py").read_text(encoding="utf-8"))
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
    assert a_mano == [], (
        f"env.py importa modelli a mano: {a_mano} — un modulo nuovo "
        "sfuggirebbe ad Alembic senza far fallire nulla"
    )


def test_la_guardia_su_env_riconosce_ogni_forma_di_import() -> None:
    # Sentinella: le tre forme che il match di stringa precedente non vedeva.
    assert _punta_ai_modelli("app.strutture.models")
    assert _punta_ai_modelli("app.identity.models.Host")
    assert _punta_ai_modelli("app.core.jobs")
    assert _punta_ai_modelli("app.core.outbox")
    # E ciò che NON deve far scattare la guardia.
    assert not _punta_ai_modelli("app.core.config")
    assert not _punta_ai_modelli("app.registro_modelli")
    assert not _punta_ai_modelli("sqlalchemy")


def test_env_di_alembic_usa_la_discovery() -> None:
    sorgente = (BACKEND / "alembic" / "env.py").read_text(encoding="utf-8")
    assert "importa_tutti_i_modelli" in sorgente
