"""Errori RFC 9457 `application/problem+json` (AD-14).

`type` stabile per errore di dominio; mai stacktrace al client.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"

TYPE_VALIDATION = "urn:hostpilot:problem:validation-error"
TYPE_INTERNAL = "urn:hostpilot:problem:internal-error"


class DomainProblem(Exception):
    """Errore di dominio con `type` RFC 9457 stabile (AD-14)."""

    def __init__(
        self,
        *,
        status: int,
        title: str,
        type_slug: str,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(title)
        self.status = status
        self.title = title
        self.type = f"urn:hostpilot:problem:{type_slug}"
        self.detail = detail
        self.headers = headers


def problem_response(
    *,
    status: int,
    title: str,
    type_: str = "about:blank",
    detail: str | None = None,
    extra: dict | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict = {"type": type_, "title": title, "status": status}
    if detail is not None:
        body["detail"] = detail
    if extra:
        body.update(extra)
    return JSONResponse(
        body,
        status_code=status,
        media_type=PROBLEM_CONTENT_TYPE,
        headers=headers,
    )


def register_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainProblem)
    async def domain_problem_handler(
        request: Request, exc: DomainProblem
    ) -> JSONResponse:
        return problem_response(
            status=exc.status,
            title=exc.title,
            type_=exc.type,
            detail=exc.detail,
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return problem_response(status=exc.status_code, title=str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Redazione (G-4): `errors[].input` di Pydantic v2 rimanda indietro
        # il valore inviato — con campi sensibili (password) è un leak.
        # Restano loc/msg/type: sufficienti al client per correggere.
        errors = [
            {k: v for k, v in error.items() if k not in {"input", "url", "ctx"}}
            for error in exc.errors()
        ]
        return problem_response(
            status=422,
            title="Richiesta non valida",
            type_=TYPE_VALIDATION,
            extra={"errors": errors},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("errore non gestito")
        return problem_response(
            status=500,
            title="Errore interno",
            type_=TYPE_INTERNAL,
        )
