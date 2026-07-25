"""Repository di `strutture`: OGNI metodo richiede host_id (AD-2, G-3).

La guardia tests/test_tenancy_convention.py impone questa firma a tutti
i repository dei moduli di dominio.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.strutture.models import StatoStruttura, Struttura


class StrutturaRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def by_id(self, host_id: uuid.UUID, struttura_id: uuid.UUID) -> Struttura | None:
        return self._db.scalars(
            select(Struttura).where(
                Struttura.host_id == host_id, Struttura.id == struttura_id
            )
        ).one_or_none()

    def lista(self, host_id: uuid.UUID) -> list[Struttura]:
        return list(
            self._db.scalars(
                select(Struttura)
                .where(Struttura.host_id == host_id)
                .order_by(Struttura.created_at)
            )
        )

    def conta_attive(self, host_id: uuid.UUID) -> int:
        return int(
            self._db.scalar(
                select(func.count())
                .select_from(Struttura)
                .where(
                    Struttura.host_id == host_id,
                    Struttura.stato == StatoStruttura.ATTIVA,
                )
            )
            or 0
        )

    def add(self, host_id: uuid.UUID, struttura: Struttura) -> Struttura:
        struttura.host_id = host_id
        self._db.add(struttura)
        return struttura
