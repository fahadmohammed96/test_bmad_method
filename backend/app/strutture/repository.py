"""Repository di `strutture`: OGNI metodo richiede host_id (AD-2, G-3).

La guardia tests/test_tenancy_convention.py impone questa firma a tutti
i repository dei moduli di dominio.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.date_range import utcnow
from app.strutture.models import RegimeLettura, StatoStruttura, Struttura


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


class RegimeLetturaRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _lettura(self, host_id: uuid.UUID) -> RegimeLettura | None:
        return self._db.scalars(
            select(RegimeLettura).where(RegimeLettura.host_id == host_id)
        ).one_or_none()

    def confermata(self, host_id: uuid.UUID) -> bool:
        return self._lettura(host_id) is not None

    def azzera(self, host_id: uuid.UUID) -> None:
        """Il rientro sotto soglia cancella la conferma: se l'Host risale,
        il pannello a schermo intero è di nuovo dovuto (UJ-4 edge)."""
        lettura = self._lettura(host_id)
        if lettura is not None:
            self._db.delete(lettura)

    def conferma(self, host_id: uuid.UUID, conteggio: int) -> None:
        lettura = self._lettura(host_id)
        if lettura is None:
            self._db.add(RegimeLettura(host_id=host_id, conteggio_confermato=conteggio))
        else:
            lettura.conteggio_confermato = conteggio
            lettura.confermato_il = utcnow()
