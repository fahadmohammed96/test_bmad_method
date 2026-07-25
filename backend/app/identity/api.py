"""Endpoint di `identity`: registrazione, login, logout, profilo (AD-15)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.problems import DomainProblem
from app.core.config import get_settings
from app.core.db import get_db
from app.identity import service
from app.identity.deps import CurrentHost
from app.identity.schemas import (
    CambioPasswordInput,
    CredenzialiInput,
    HostOutput,
    PreferenzeInput,
)

auth_router = APIRouter(prefix="/auth", tags=["identity"])
hosts_router = APIRouter(prefix="/hosts", tags=["identity"])

DbSession = Annotated[Session, Depends(get_db)]


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_days * 86400,
        path="/",
    )


@auth_router.post("/registrazione", response_model=HostOutput, status_code=201)
def registrazione(
    credenziali: CredenzialiInput, response: Response, db: DbSession
) -> HostOutput:
    try:
        aperta = service.registra_host(db, credenziali.email, credenziali.password)
    except service.EmailGiaRegistrataError:
        raise DomainProblem(
            status=409,
            title="Email già registrata",
            type_slug="email-already-registered",
        ) from None
    _set_session_cookie(response, aperta.token)
    return HostOutput.model_validate(aperta.host)


@auth_router.post("/login", response_model=HostOutput)
def login(
    credenziali: CredenzialiInput, response: Response, db: DbSession
) -> HostOutput:
    try:
        aperta = service.login(db, credenziali.email, credenziali.password)
    except service.CredenzialiNonValideError:
        raise DomainProblem(
            status=401,
            title="Credenziali non valide",
            type_slug="invalid-credentials",
        ) from None
    _set_session_cookie(response, aperta.token)
    return HostOutput.model_validate(aperta.host)


@auth_router.post("/logout", status_code=204)
def logout(
    request: Request, response: Response, db: DbSession, host: CurrentHost
) -> None:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        service.logout(db, token)
    response.delete_cookie(settings.session_cookie_name, path="/")


@hosts_router.get("/me", response_model=HostOutput)
def me(host: CurrentHost) -> HostOutput:
    return HostOutput.model_validate(host)


@hosts_router.patch("/me/preferenze", response_model=HostOutput)
def aggiorna_preferenze(
    preferenze: PreferenzeInput, db: DbSession, host: CurrentHost
) -> HostOutput:
    aggiornato = service.aggiorna_preferenze(
        db, host, preferenze.canale_notifica_preferito
    )
    return HostOutput.model_validate(aggiornato)


@hosts_router.post("/me/password", status_code=204)
def cambia_password(
    cambio: CambioPasswordInput,
    request: Request,
    db: DbSession,
    host: CurrentHost,
) -> None:
    token = request.cookies.get(get_settings().session_cookie_name) or ""
    try:
        service.cambia_password(
            db, host, cambio.password_attuale, cambio.password_nuova, token
        )
    except service.CredenzialiNonValideError:
        raise DomainProblem(
            status=403,
            title="Password attuale errata",
            type_slug="invalid-current-password",
        ) from None
