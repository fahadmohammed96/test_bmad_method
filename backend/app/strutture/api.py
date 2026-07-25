"""Endpoint di `strutture` (FR-1): /api/v1/strutture."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.problems import DomainProblem
from app.config_normativa import service as config_service
from app.config_normativa.schemas import (
    AreaIstatOutput,
    AreaTassaOutput,
    ConfigurazioneNormativaOutput,
)
from app.core.date_range import today_rome
from app.core.db import get_db
from app.identity.deps import CurrentHost
from app.strutture import service
from app.strutture.schemas import (
    RegimeFiscaleOutput,
    StrutturaInput,
    StrutturaOutput,
    StrutturaUpdate,
)

router = APIRouter(prefix="/strutture", tags=["strutture"])
regime_router = APIRouter(prefix="/regime-fiscale", tags=["strutture"])

DbSession = Annotated[Session, Depends(get_db)]


def _non_trovata() -> DomainProblem:
    return DomainProblem(
        status=404,
        title="Struttura non trovata",
        type_slug="struttura-not-found",
    )


@router.post("", status_code=201)
def crea(dati: StrutturaInput, db: DbSession, host: CurrentHost) -> StrutturaOutput:
    try:
        struttura = service.crea_struttura(
            db,
            host.id,
            service.DatiStruttura(
                nome=dati.nome,
                comune=dati.comune,
                regione=dati.regione,
                cin=dati.cin,
                comune_codice_istat=dati.comune_codice_istat,
            ),
        )
    except service.CapStruttureAttiveError:
        raise DomainProblem(
            status=409,
            title="Limite di Strutture attive raggiunto",
            type_slug="cap-strutture-attive",
            detail=(
                "Il pilota copre da 1-3 Strutture attive: archivia una "
                "Struttura per registrarne una nuova."
            ),
        ) from None
    return StrutturaOutput.model_validate(struttura)


@router.get("")
def lista(db: DbSession, host: CurrentHost) -> list[StrutturaOutput]:
    return [
        StrutturaOutput.model_validate(s) for s in service.lista_strutture(db, host.id)
    ]


@router.patch("/{struttura_id}")
def aggiorna(
    struttura_id: uuid.UUID,
    modifiche: StrutturaUpdate,
    db: DbSession,
    host: CurrentHost,
) -> StrutturaOutput:
    try:
        struttura = service.aggiorna_struttura(
            db, host.id, struttura_id, modifiche.model_dump(exclude_unset=True)
        )
    except service.StrutturaNonTrovataError:
        raise _non_trovata() from None
    return StrutturaOutput.model_validate(struttura)


@regime_router.get("")
def regime_fiscale(db: DbSession, host: CurrentHost) -> RegimeFiscaleOutput:
    """Regime fiscale derivato dal numero di Strutture non archiviate."""
    return RegimeFiscaleOutput.model_validate(
        service.regime_fiscale(db, host.id), from_attributes=True
    )


@regime_router.post("/conferma-lettura", status_code=204)
def conferma_lettura(db: DbSession, host: CurrentHost) -> None:
    """L'Host ha letto il pannello a schermo intero (UX-DR14)."""
    service.conferma_lettura_regime(db, host.id)


@router.get("/{struttura_id}/configurazione-normativa")
def configurazione_normativa(
    struttura_id: uuid.UUID,
    db: DbSession,
    host: CurrentHost,
    alla_data: date | None = None,
) -> ConfigurazioneNormativaOutput:
    """Configurazione applicabile alla Struttura, con degrado sicuro (AD-9)."""
    try:
        struttura = service.leggi_struttura(db, host.id, struttura_id)
    except service.StrutturaNonTrovataError:
        raise _non_trovata() from None

    riferimento = alla_data or today_rome()
    return ConfigurazioneNormativaOutput(
        alla_data=riferimento,
        tassa_soggiorno=AreaTassaOutput.model_validate(
            config_service.risolvi_tassa(
                db, struttura.comune_codice_istat, riferimento
            ),
            from_attributes=True,
        ),
        istat=AreaIstatOutput.model_validate(
            config_service.risolvi_istat(
                db, struttura.regione_codice_istat, riferimento
            ),
            from_attributes=True,
        ),
    )


@router.post("/{struttura_id}/archivia")
def archivia(
    struttura_id: uuid.UUID, db: DbSession, host: CurrentHost
) -> StrutturaOutput:
    try:
        struttura = service.archivia_struttura(db, host.id, struttura_id)
    except service.StrutturaNonTrovataError:
        raise _non_trovata() from None
    return StrutturaOutput.model_validate(struttura)
