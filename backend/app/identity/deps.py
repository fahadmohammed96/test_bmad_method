"""Dependency di autenticazione (AD-2, AD-15).

`host_id` si risolve SOLO dalla sessione (cookie HttpOnly), mai da input
client. Ogni endpoint non pubblico dichiara questa dependency — la
convenzione è verificata strutturalmente da tests/test_auth_convention.py.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.problems import DomainProblem
from app.core.config import get_settings
from app.core.db import get_db
from app.identity import service
from app.identity.models import Host


def _non_autenticato() -> DomainProblem:
    return DomainProblem(
        status=401,
        title="Sessione assente o non valida",
        type_slug="not-authenticated",
    )


def get_current_host(request: Request, db: Annotated[Session, Depends(get_db)]) -> Host:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise _non_autenticato()
    host = service.host_da_token(db, token)
    if host is None:
        raise _non_autenticato()
    return host


CurrentHost = Annotated[Host, Depends(get_current_host)]
