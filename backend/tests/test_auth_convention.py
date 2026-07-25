"""Guardia strutturale (AD-2, AD-15): ogni endpoint sotto /api/v1 richiede
una sessione Host valida, salvo gli endpoint pubblici dichiarati e quelli
interni protetti dal token di servizio.

Il test cammina le route dell'app: una Story futura che aggiunge un
endpoint senza protezione fallisce qui, non in produzione.
"""

from collections.abc import Iterator

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.config_normativa.deps import require_admin_token
from app.identity.deps import get_current_host
from app.main import app

# Superfici raggiungibili senza sessione: solo quelle necessarie prima
# dell'accesso (l'anagrafica Regioni alimenta il form di onboarding).
PUBBLICI = {
    "/api/v1/health",
    "/api/v1/auth/registrazione",
    "/api/v1/auth/login",
    "/api/v1/regioni",
}

PROTETTORI = (get_current_host, require_admin_token)


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


def _protetto(dependant: Dependant) -> bool:
    if dependant.call in PROTETTORI:
        return True
    return any(_protetto(dep) for dep in dependant.dependencies)


def test_ogni_endpoint_non_pubblico_e_protetto() -> None:
    non_protetti = [
        path
        for path, dependant in _iter_endpoints(app.routes)
        if path not in PUBBLICI and not _protetto(dependant)
    ]
    assert non_protetti == [], (
        f"endpoint senza protezione: {non_protetti} — ogni endpoint non "
        "pubblico richiede la sessione Host (AD-15) o il token interno (AD-9)"
    )


def test_gli_endpoint_pubblici_sono_solo_quelli_previsti() -> None:
    pubblici_reali = {
        path
        for path, dependant in _iter_endpoints(app.routes)
        if not _protetto(dependant)
    }
    assert pubblici_reali == PUBBLICI


def test_gli_endpoint_interni_non_usano_la_sessione_host() -> None:
    # Gli endpoint /interno aggiornano dati condivisi: non appartengono a
    # un Host e devono passare SOLO dal token di servizio.
    for path, dependant in _iter_endpoints(app.routes):
        if path.startswith("/api/v1/interno"):
            assert _dipende_da(dependant, require_admin_token), path
            assert not _dipende_da(dependant, get_current_host), path


def _dipende_da(dependant: Dependant, protettore) -> bool:
    if dependant.call is protettore:
        return True
    return any(_dipende_da(dep, protettore) for dep in dependant.dependencies)
