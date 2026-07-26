"""Accesso ai metadati per le guardie: una sola sorgente di verita'.

La discovery dei moduli che dichiarano tabelle vive in
`app/registro_modelli.py`, perche' la usa anche `alembic/env.py`. Qui c'e' solo
l'alias che le guardie chiamano: due implementazioni della stessa scoperta
sarebbero due cose che possono divergere.
"""

from app.core.db import Base
from app.registro_modelli import importa_tutti_i_modelli, moduli_di_dominio

__all__ = ["Base", "carica_modelli", "moduli_di_dominio"]


def carica_modelli() -> type[Base]:
    """Importa ogni modulo che dichiara tabelle e ritorna la Base popolata."""
    return importa_tutti_i_modelli()
