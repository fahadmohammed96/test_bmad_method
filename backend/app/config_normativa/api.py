"""Endpoint di `config_normativa`: anagrafica (Host) e configurazione (interni)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.problems import DomainProblem
from app.config_normativa import service
from app.config_normativa.deps import AdminToken
from app.config_normativa.repository import AnagraficaRepository
from app.config_normativa.schemas import (
    ComuneConfigInput,
    ComuneOutput,
    ConfigSalvataOutput,
    RegioneConfigInput,
    RegioneOutput,
)
from app.core.db import get_db
from app.identity.deps import CurrentHost

anagrafica_router = APIRouter(tags=["config_normativa"])
interno_router = APIRouter(prefix="/interno", tags=["config_normativa"])

DbSession = Annotated[Session, Depends(get_db)]


@anagrafica_router.get("/regioni")
def regioni(db: DbSession) -> list[RegioneOutput]:
    """Anagrafica pubblica: serve anche prima dell'accesso (form di onboarding)."""
    return [RegioneOutput.model_validate(r) for r in AnagraficaRepository(db).regioni()]


@anagrafica_router.get("/comuni")
def comuni(
    db: DbSession,
    host: CurrentHost,
    ricerca: Annotated[str, Query(min_length=2, max_length=120)],
) -> list[ComuneOutput]:
    return [
        ComuneOutput.model_validate(c)
        for c in AnagraficaRepository(db).cerca_comuni(ricerca)
    ]


@interno_router.put("/comuni/{codice_istat}/configurazione")
def configura_comune(
    codice_istat: str,
    dati: ComuneConfigInput,
    db: DbSession,
    _: AdminToken,
) -> ConfigSalvataOutput:
    try:
        config = service.aggiorna_comune_config(
            db,
            codice_istat,
            attore=dati.attore,
            tassa_importo_cent=dati.tassa_importo_cent,
            tassa_periodicita=dati.tassa_periodicita,
            esenzione_eta_max=dati.esenzione_eta_max,
            esenzione_notti_oltre=dati.esenzione_notti_oltre,
            valido_dal=dati.valido_dal,
            valido_al=dati.valido_al,
        )
    except service.ComuneSconosciutoError:
        raise DomainProblem(
            status=404,
            title="Comune non presente in anagrafica",
            type_slug="comune-not-found",
        ) from None
    return ConfigSalvataOutput(valido_dal=config.valido_dal, valido_al=config.valido_al)


@interno_router.put("/regioni/{codice_istat}/configurazione")
def configura_regione(
    codice_istat: str,
    dati: RegioneConfigInput,
    db: DbSession,
    _: AdminToken,
) -> ConfigSalvataOutput:
    try:
        config = service.aggiorna_regione_config(
            db,
            codice_istat,
            attore=dati.attore,
            istat_tracciato=dati.istat_tracciato,
            istat_periodicita=dati.istat_periodicita,
            valido_dal=dati.valido_dal,
            valido_al=dati.valido_al,
        )
    except service.RegioneSconosciutaError:
        raise DomainProblem(
            status=404,
            title="Regione non presente in anagrafica",
            type_slug="regione-not-found",
        ) from None
    return ConfigSalvataOutput(valido_dal=config.valido_dal, valido_al=config.valido_al)
