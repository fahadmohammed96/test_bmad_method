"""Guardia strutturale (AD-2, AD-15): ogni endpoint sotto /api/v1 — salvo
login, registrazione e health — richiede una sessione valida.

Il test cammina le route dell'app: una Story futura che aggiunge un
endpoint senza `get_current_host` fallisce qui, non in produzione.
"""

from collections.abc import Iterator

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.identity.deps import get_current_host
from app.main import app

PUBBLICI = {
    "/api/v1/health",
    "/api/v1/auth/registrazione",
    "/api/v1/auth/login",
}


def _iter_endpoints(routes) -> Iterator[tuple[str, Dependant]]:
    """Appiattisce APIRoute e router inclusi lazy (FastAPI ≥ 0.139)."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route.path, route.dependant
        elif hasattr(route, "effective_route_contexts"):
            for ctx in route.effective_route_contexts():
                yield ctx.path, ctx.dependant
        elif hasattr(route, "routes"):
            yield from _iter_endpoints(route.routes)


def _dipende_da_auth(dependant: Dependant) -> bool:
    if dependant.call is get_current_host:
        return True
    return any(_dipende_da_auth(dep) for dep in dependant.dependencies)


def test_ogni_endpoint_non_pubblico_richiede_la_sessione() -> None:
    non_protetti = [
        path
        for path, dependant in _iter_endpoints(app.routes)
        if path not in PUBBLICI and not _dipende_da_auth(dependant)
    ]
    assert non_protetti == [], (
        f"endpoint senza get_current_host: {non_protetti} — "
        "ogni endpoint non pubblico risolve host_id dalla sessione (AD-15)"
    )


def test_gli_endpoint_pubblici_sono_solo_quelli_previsti() -> None:
    pubblici_reali = {
        path
        for path, dependant in _iter_endpoints(app.routes)
        if not _dipende_da_auth(dependant)
    }
    assert pubblici_reali == PUBBLICI
