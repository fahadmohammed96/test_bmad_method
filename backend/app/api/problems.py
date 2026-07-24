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


def problem_response(
    *,
    status: int,
    title: str,
    type_: str = "about:blank",
    detail: str | None = None,
    extra: dict | None = None,
) -> JSONResponse:
    body: dict = {"type": type_, "title": title, "status": status}
    if detail is not None:
        body["detail"] = detail
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_CONTENT_TYPE)


def register_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return problem_response(status=exc.status_code, title=str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return problem_response(
            status=422,
            title="Richiesta non valida",
            type_=TYPE_VALIDATION,
            extra={"errors": exc.errors()},
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
