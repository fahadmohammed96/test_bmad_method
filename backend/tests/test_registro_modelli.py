"""Guardia: i metadati di Alembic non possono perdere una tabella.

`alembic --autogenerate` confronta il database con `target_metadata`. Se un
modulo non è importato, le sue tabelle non compaiono nei metadati e
l'autogenerate propone `op.drop_table(...)`: la migrazione distruttiva più
probabile del progetto non nasce da malizia, nasce da un import mancante.

`env.py` non si può importare in un test — a import-time esegue le migrazioni.
La discovery vive quindi in `app.registro_modelli`, che è ciò che `env.py`
usa, e qui si verifica che copra davvero tutto.
"""

import pathlib

from app.registro_modelli import importa_tutti_i_modelli, moduli_di_dominio

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def test_ogni_modulo_di_dominio_con_tabelle_e_nei_metadati() -> None:
    metadata = importa_tutti_i_modelli().metadata
    mancanti = [
        modulo
        for modulo in moduli_di_dominio()
        if (BACKEND / "app" / modulo / "models.py").exists()
        and not _ha_almeno_una_tabella(metadata, modulo)
    ]
    assert mancanti == [], (
        f"moduli con models.py assenti dai metadati: {mancanti} — "
        "l'autogenerate proporrebbe di cancellarne le tabelle"
    )


def _ha_almeno_una_tabella(metadata: object, modulo: str) -> bool:
    import importlib

    modelli = importlib.import_module(f"app.{modulo}.models")
    nomi = {
        oggetto.__tablename__
        for oggetto in vars(modelli).values()
        if hasattr(oggetto, "__tablename__")
    }
    return bool(nomi & set(metadata.tables))  # type: ignore[attr-defined]


def test_env_di_alembic_non_elenca_i_modelli_a_mano() -> None:
    # Se qualcuno tornasse a un elenco di import, la guardia sopra tornerebbe
    # a poter tacere: il presidio è la DISCOVERY, e va difeso in quanto tale.
    sorgente = (BACKEND / "alembic" / "env.py").read_text(encoding="utf-8")
    assert "importa_tutti_i_modelli" in sorgente
    assert "models as _" not in sorgente, (
        "env.py è tornato a elencare i modelli a mano: un modulo nuovo "
        "sfuggirebbe ad Alembic senza far fallire nulla"
    )


def test_il_modulo_calendario_e_scoperto() -> None:
    # La guardia non deve mai svuotarsi in silenzio.
    assert "calendario" in moduli_di_dominio()
    tabelle = set(importa_tutti_i_modelli().metadata.tables)
    assert {"feed_ical", "sync_run", "prenotazione"} <= tabelle
