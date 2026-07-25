"""Accesso agli endpoint interni di configurazione (AD-9).

Non sono endpoint pubblici né endpoint di Host: aggiornano dati normativi
condivisi e vivono dietro un token di servizio, con ogni scrittura
auditata. Il token sta nel secret manager dell'ambiente, mai nel repo.
Se non è configurato, gli endpoint restano chiusi.
"""

import secrets
from typing import Annotated

from fastapi import Depends, Header

from app.api.problems import DomainProblem
from app.core.config import get_settings


def require_admin_token(
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    atteso = get_settings().admin_token
    if not atteso or not x_admin_token:
        raise _accesso_negato()
    if not secrets.compare_digest(x_admin_token, atteso):
        raise _accesso_negato()


def _accesso_negato() -> DomainProblem:
    return DomainProblem(
        status=403,
        title="Accesso riservato agli endpoint interni",
        type_slug="admin-token-required",
    )


AdminToken = Annotated[None, Depends(require_admin_token)]
