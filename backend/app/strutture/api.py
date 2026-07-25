"""Endpoint di `strutture` (FR-1): /api/v1/strutture."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.problems import DomainProblem
from app.core.db import get_db
from app.identity.deps import CurrentHost
from app.strutture import service
from app.strutture.schemas import StrutturaInput, StrutturaOutput, StrutturaUpdate

router = APIRouter(prefix="/strutture", tags=["strutture"])

DbSession = Annotated[Session, Depends(get_db)]


def _non_trovata() -> DomainProblem:
    return DomainProblem(
        status=404,
        title="Struttura non trovata",
        type_slug="struttura-not-found",
    )


@router.post("", response_model=StrutturaOutput, status_code=201)
def crea(dati: StrutturaInput, db: DbSession, host: CurrentHost) -> StrutturaOutput:
    try:
        struttura = service.crea_struttura(
            db,
            host.id,
            service.DatiStruttura(
                nome=dati.nome, comune=dati.comune, regione=dati.regione, cin=dati.cin
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


@router.get("", response_model=list[StrutturaOutput])
def lista(db: DbSession, host: CurrentHost) -> list[StrutturaOutput]:
    return [
        StrutturaOutput.model_validate(s) for s in service.lista_strutture(db, host.id)
    ]


@router.patch("/{struttura_id}", response_model=StrutturaOutput)
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


@router.post("/{struttura_id}/archivia", response_model=StrutturaOutput)
def archivia(
    struttura_id: uuid.UUID, db: DbSession, host: CurrentHost
) -> StrutturaOutput:
    try:
        struttura = service.archivia_struttura(db, host.id, struttura_id)
    except service.StrutturaNonTrovataError:
        raise _non_trovata() from None
    return StrutturaOutput.model_validate(struttura)
