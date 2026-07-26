"""Registro dei moduli che dichiarano tabelle, scoperti invece che elencati.

`Base.metadata` contiene solo le tabelle dei moduli **importati**. Finché
l'elenco è scritto a mano, un modulo nuovo dimenticato non fa fallire nulla:
`alembic --autogenerate` semplicemente non vede le sue tabelle e propone di
**cancellarle**. È la classe di difetti delle «assenze» — un pezzo mancante
non fallisce, tace — applicata al punto peggiore possibile.

Da qui l'elenco non esiste più: i moduli si scoprono. Un modulo di dominio
nuovo entra nei metadati senza che nessuno se ne ricordi, e la guardia
`tests/test_registro_modelli.py` verifica che la scoperta copra davvero tutto.

Non vive in `app/core/`: il kernel condiviso non deve MAI importare moduli di
dominio (AD-1). Questo è codice di supporto agli strumenti (Alembic, guardie),
e sta un livello sopra.
"""

import importlib
import pkgutil
from types import ModuleType

import app
from app.core.db import Base

# `core` e `api` non sono moduli di dominio: il primo dichiara le tabelle di
# infrastruttura (importate esplicitamente qui sotto), il secondo non ne ha.
MODULI_NON_DI_DOMINIO = frozenset({"core", "api"})

# Tabelle di infrastruttura del kernel: non stanno in un modulo di dominio,
# ma fanno parte del modello.
MODULI_INFRASTRUTTURALI = ("app.core.jobs", "app.core.outbox")


def moduli_di_dominio() -> list[str]:
    """Pacchetti di dominio sotto `app/`, in ordine stabile."""
    return sorted(
        info.name
        for info in pkgutil.iter_modules(app.__path__)
        if info.ispkg and info.name not in MODULI_NON_DI_DOMINIO
    )


def importa_tutti_i_modelli() -> type[Base]:
    """Importa ogni modulo che dichiara tabelle e ritorna la Base popolata."""
    for nome in MODULI_INFRASTRUTTURALI:
        importlib.import_module(nome)
    for modulo in moduli_di_dominio():
        _importa_se_esiste(f"app.{modulo}.models")
    return Base


def _importa_se_esiste(nome: str) -> ModuleType | None:
    try:
        return importlib.import_module(nome)
    except ModuleNotFoundError:
        # Un modulo di dominio può legittimamente non avere tabelle proprie.
        return None
