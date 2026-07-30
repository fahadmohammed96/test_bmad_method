"""Repository di `strutture`: OGNI metodo richiede host_id (AD-2, G-3).

La guardia tests/test_tenancy_convention.py impone questa firma a tutti
i repository dei moduli di dominio.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.date_range import utcnow
from app.core.lock import NAMESPACE_CAP_STRUTTURE, blocca_per_id
from app.strutture.models import RegimeLettura, StatoStruttura, Struttura


class StrutturaRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def blocca_creazioni_dell_host(self, host_id: uuid.UUID) -> None:
        """Serializza le creazioni concorrenti dello stesso Host (F-1).

        Conteggio e insert non sono atomici: senza serializzazione due
        richieste simultanee possono superare entrambe il cap. Il lock è
        consultivo e legato alla TRANSAZIONE (si rilascia da solo al
        commit o al rollback) e non tocca tabelle di altri moduli.

        Una collisione di hash fra Host diversi serializzerebbe due
        creazioni non correlate: un costo trascurabile, mai un errore.

        Il namespace vive in `app.core.lock`, non qui: dal secondo advisory
        lock del prodotto la loro distinzione è una proprietà globale, e una
        costante per modulo non la rende verificabile (RT-3).
        """
        blocca_per_id(self._db, NAMESPACE_CAP_STRUTTURE, host_id)

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

    def _conferma_valida(self, host_id: uuid.UUID) -> RegimeLettura | None:
        """La conferma che vale ORA, se c'è.

        La tabella è un registro: porta anche le conferme revocate dei giri
        precedenti. «Esiste una riga» non è più la domanda giusta, e
        `one_or_none()` resta legittimo perché l'indice unico parziale ammette
        al più una conferma non revocata per Host.
        """
        return self._db.scalars(
            select(RegimeLettura).where(
                RegimeLettura.host_id == host_id,
                RegimeLettura.revocata_il.is_(None),
            )
        ).one_or_none()

    def confermata(self, host_id: uuid.UUID) -> bool:
        return self._conferma_valida(host_id) is not None

    def revoca(self, host_id: uuid.UUID) -> None:
        """Il rientro sotto soglia REVOCA la conferma: se l'Host risale, il
        pannello a schermo intero è di nuovo dovuto (UJ-4 edge).

        La riga resta con la sua evidenza datata — `conteggio_confermato` e
        `confermato_il` attestano che l'Host è stato informato della soglia
        fiscale — e la revoca aggiunge quando ha smesso di valere: transizione
        tracciata, mai `delete` (AD-19, AD-20; decisione MYL-68).

        Idempotente perché agisce sulla sola conferma valida: la data di una
        revoca già avvenuta non si riscrive.
        """
        conferma = self._conferma_valida(host_id)
        if conferma is not None:
            conferma.revocata_il = utcnow()

    def conferma(self, host_id: uuid.UUID, conteggio: int) -> None:
        """Dopo una revoca la conferma è una riga NUOVA: la storia resta.

        Riconfermare mentre la conferma vale aggiorna invece il conteggio a cui
        si riferisce, sulla stessa riga: il registro cresce di un giro di
        soglia, non di un click sull'endpoint.
        """
        conferma = self._conferma_valida(host_id)
        if conferma is None:
            self._db.add(RegimeLettura(host_id=host_id, conteggio_confermato=conteggio))
        else:
            conferma.conteggio_confermato = conteggio
            conferma.confermato_il = utcnow()
