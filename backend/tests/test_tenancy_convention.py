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
from tests.modello import carica_modelli

# I metadati vanno letti DOPO aver importato ogni modulo di dominio: una
# guardia che li legge prima non fallisce, tace (vedi tests/modello.py).
Base = carica_modelli()

# Tabelle senza host_id ammesse: infrastruttura core, la radice tenancy e
# i DATI DI RIFERIMENTO condivisi (anagrafica ISTAT e configurazione
# normativa, AD-9) — non appartengono a un Host, valgono per tutti.
TABELLE_NON_TENANT = {"outbox", "job", "host"}
# Tracce PRE-autenticazione: si scrivono prima di sapere se l'account
# esiste, quindi non possono portare `host_id` — legarle all'Host
# rivelerebbe quali email sono registrate (G-5).
TABELLE_PRE_AUTENTICAZIONE = {"tentativo_login"}
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
    esentate = TABELLE_NON_TENANT | TABELLE_DI_RIFERIMENTO | TABELLE_PRE_AUTENTICAZIONE
    for tabella in Base.metadata.tables.values():
        if tabella.name in esentate:
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


# Quanti metodi la guardia deve almeno ISPEZIONARE. Verificare che i moduli
# ci siano non basta: il filtro e' su `endswith("Repository")`, quindi
# rinominare `PrenotazioneRepository` in `PrenotazioneStore` farebbe uscire
# dieci metodi dal controllo lasciando tutti i test verdi. Un pavimento sul
# numero di metodi ispezionati e' cio' che rende la cecita' rumorosa.
PAVIMENTO_METODI_ISPEZIONATI = 12


def _metodi_ispezionati() -> list[str]:
    ispezionati = []
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
            ispezionati += [
                f"{modulo}.{nome_classe}.{nome}"
                for nome, _ in inspect.getmembers(classe, inspect.isfunction)
                if not nome.startswith("_")
            ]
    return ispezionati


def test_esiste_almeno_un_modulo_di_dominio_sorvegliato() -> None:
    # La guardia non deve mai svuotarsi in silenzio.
    assert "strutture" in _moduli_di_dominio()
    assert "calendario" in _moduli_di_dominio()


def test_la_guardia_ispeziona_davvero_i_repository() -> None:
    ispezionati = _metodi_ispezionati()
    assert len(ispezionati) >= PAVIMENTO_METODI_ISPEZIONATI, (
        f"solo {len(ispezionati)} metodi ispezionati ({sorted(ispezionati)}): "
        "una classe di repository e' sfuggita al filtro sul nome. Se il calo "
        "e' voluto, abbassare il pavimento CON una motivazione scritta"
    )
    # Se una classe di repository di `calendario` venisse rinominata, questa
    # riga cadrebbe invece di tacere.
    assert any(voce.startswith("calendario.") for voce in ispezionati)


def test_le_tabelle_esentate_non_acquisiscono_un_legame_con_host() -> None:
    # L'esenzione vale perché quei dati non appartengono a un Host: dati
    # di riferimento condivisi, o tracce scritte prima di sapere chi è.
    # Se una di queste tabelle acquisisse `host_id` o una FK verso host,
    # l'esenzione decadrebbe e questo test lo dice subito.
    for nome in TABELLE_DI_RIFERIMENTO | TABELLE_PRE_AUTENTICAZIONE:
        tabella = Base.metadata.tables[nome]
        assert "host_id" not in tabella.columns
        riferimenti = {
            fk.column.table.name for col in tabella.columns for fk in col.foreign_keys
        }
        assert "host" not in riferimenti, nome
