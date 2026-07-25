"""HostPilot API — punto di ingresso del monolite modulare (AD-1, AD-14).

REST JSON sotto /api/v1, OpenAPI generato da FastAPI, errori RFC 9457.
Le convenzioni operative del repository sono in AGENTS.md.
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.problems import register_problem_handlers
from app.core.config import get_settings
from app.identity.api import auth_router, hosts_router

API_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(hosts_router)

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

# Il frontend gira su un'origin diversa e invia il cookie di sessione:
# origin esplicita + credentials, mai wildcard (AD-15).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
