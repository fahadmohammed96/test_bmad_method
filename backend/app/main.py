"""HostPilot API — punto di ingresso del monolite modulare (AD-1, AD-14).

REST JSON sotto /api/v1, OpenAPI generato da FastAPI, errori RFC 9457.
Le convenzioni operative del repository sono in AGENTS.md.
"""

from fastapi import APIRouter, FastAPI

from app.api.health import router as health_router
from app.api.problems import register_problem_handlers

API_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(health_router)

app = FastAPI(
    title="HostPilot API",
    version="0.1.0",
    description=(
        "Gestionale per host privati di affitti brevi: calendario unificato, "
        "adempimenti italiani, regole di prezzo, operatività."
    ),
    openapi_url=f"{API_PREFIX}/openapi.json",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=None,
)
app.include_router(api_router)
register_problem_handlers(app)
