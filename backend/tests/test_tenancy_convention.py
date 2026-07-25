"""Guardia strutturale G-3 (AD-2, NFR-14): tenancy imposta dalla struttura.

1. Ogni tabella dati fuori dall'allowlist infrastrutturale porta `host_id`
   NOT NULL con FK verso host.
2. Nei moduli di dominio applicativo, ogni metodo pubblico di ogni
   repository richiede `host_id`: una query non scopata non può nemmeno
   essere scritta senza far fallire la CI.
"""

import importlib
import inspect
import pkgutil

import app
from app.core.db import Base

# Tabelle senza host_id ammesse: infrastruttura core, la radice tenancy e
# i DATI DI RIFERIMENTO condivisi (anagrafica ISTAT e configurazione
# normativa, AD-9) — non appartengono a un Host, valgono per tutti.
TABELLE_NON_TENANT = {"outbox", "job", "host"}
TABELLE_DI_RIFERIMENTO = {
    "regione",
    "comune",
    "comune_config",
    "regione_config",
    "parametro_fiscale",
    "config_audit",
}

# Moduli esclusi dalla guardia sui repository: `core`/`api` sono
# infrastruttura; `identity` È il produttore di host_id (le sue lookup
# per token/email sono il meccanismo di autenticazione stesso);
# `config_normativa` espone solo dati di riferimento condivisi — lo
# scoping per Host avviene in `strutture`, che possiede il legame
# Struttura → Comune/Regione.
MODULI_ESCLUSI = {"core", "api", "identity", "config_normativa"}


def test_ogni_tabella_dati_porta_host_id_not_null() -> None:
    fuori_norma = []
    for tabella in Base.metadata.tables.values():
        if tabella.name in TABELLE_NON_TENANT | TABELLE_DI_RIFERIMENTO:
            continue
        colonna = tabella.columns.get("host_id")
        if colonna is None or colonna.nullable:
            fuori_norma.append(tabella.name)
            continue
        fk_verso_host = any(
            fk.column.table.name == "host" for fk in colonna.foreign_keys
        )
        if not fk_verso_host:
            fuori_norma.append(tabella.name)
    assert fuori_norma == [], (
        f"tabelle senza host_id NOT NULL + FK host: {fuori_norma} (AD-2)"
    )


def _moduli_di_dominio() -> list[str]:
    return [
        info.name
        for info in pkgutil.iter_modules(app.__path__)
        if info.ispkg and info.name not in MODULI_ESCLUSI
    ]


def test_ogni_metodo_di_repository_di_dominio_richiede_host_id() -> None:
    fuori_norma = []
    for modulo in _moduli_di_dominio():
        try:
            repository = importlib.import_module(f"app.{modulo}.repository")
        except ModuleNotFoundError:
            continue
        for nome_classe, classe in inspect.getmembers(repository, inspect.isclass):
            if not nome_classe.endswith("Repository"):
                continue
            if classe.__module__ != repository.__name__:
                continue
            for nome_metodo, metodo in inspect.getmembers(classe, inspect.isfunction):
                if nome_metodo.startswith("_"):
                    continue
                if "host_id" not in inspect.signature(metodo).parameters:
                    fuori_norma.append(f"{modulo}.{nome_classe}.{nome_metodo}")
    assert fuori_norma == [], (
        f"metodi repository senza host_id: {fuori_norma} — "
        "ogni query di dominio è scopata per host (AD-2, G-3)"
    )


def test_esiste_almeno_un_modulo_di_dominio_sorvegliato() -> None:
    # La guardia non deve mai svuotarsi in silenzio.
    assert "strutture" in _moduli_di_dominio()


def test_le_tabelle_di_riferimento_non_contengono_dati_di_host() -> None:
    # L'allowlist vale perché sono dati condivisi: se una di queste
    # tabelle acquisisse un legame con l'Host, l'esenzione decadrebbe.
    for nome in TABELLE_DI_RIFERIMENTO:
        tabella = Base.metadata.tables[nome]
        assert "host_id" not in tabella.columns
        riferimenti = {
            fk.column.table.name for col in tabella.columns for fk in col.foreign_keys
        }
        assert "host" not in riferimenti, nome
