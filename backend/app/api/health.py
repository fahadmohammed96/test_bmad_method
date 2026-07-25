"""Endpoint di health check: verifica che il servizio risponda."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Stato del servizio, usato da monitoraggio e smoke test."""
    return {"status": "ok"}
