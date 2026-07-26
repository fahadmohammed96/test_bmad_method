"""Carica TUTTI i modelli di dominio prima di leggere `Base.metadata`.

`Base.metadata.tables` contiene solo le tabelle dei moduli effettivamente
importati. Finché ogni modulo era raggiungibile da `app.main` la cosa non si
notava; ma una guardia che legge i metadati **prima** che un modulo sia
importato non fallisce: tace, e la tabella nuova sfugge al controllo.

È la stessa classe di difetti che le guardie stesse combattono (le
«assenze»), applicata alle guardie. Da qui in poi ogni guardia sul modello
chiama `carica_modelli()` per prima cosa.
"""

import importlib
import pkgutil

import app
from app.core.db import Base

MODULI_NON_DI_DOMINIO = {"core", "api"}

# Tabelle di infrastruttura: non stanno in un modulo di dominio, ma fanno
# parte del modello e le guardie devono vederle.
MODULI_INFRASTRUTTURALI = ("app.core.jobs", "app.core.outbox")


def moduli_di_dominio() -> list[str]:
    return [
        info.name
        for info in pkgutil.iter_modules(app.__path__)
        if info.ispkg and info.name not in MODULI_NON_DI_DOMINIO
    ]


def carica_modelli() -> type[Base]:
    """Importa ogni modulo che dichiara tabelle e ritorna la Base popolata."""
    for modulo in MODULI_INFRASTRUTTURALI:
        importlib.import_module(modulo)
    for modulo in moduli_di_dominio():
        try:
            importlib.import_module(f"app.{modulo}.models")
        except ModuleNotFoundError:
            continue
    return Base
