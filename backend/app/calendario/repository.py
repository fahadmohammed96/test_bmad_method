"""Repository di `calendario`: OGNI metodo richiede host_id (AD-2, G-3).

L'idempotenza dell'import vive qui, e vive nel DATABASE: `upsert` è un
`INSERT ... ON CONFLICT (feed_id, ical_uid) DO UPDATE`, senza alcun
pre-check applicativo. Un pre-check («esiste già?» poi «inserisci») è un
check-then-write: sotto due sync concorrenti dello stesso Feed passano
entrambi il controllo e nascono due righe. A decidere deve essere il
constraint (lezione G-2 dell'Epic 1, test di gara A3-1).
"""

import uuid
from collections.abc import Iterable, Sequence
from typing import cast

from sqlalchemy import Select, case, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.calendario.models import (
    CanaleFeed,
    EsitoSyncRun,
    FeedIcal,
    Prenotazione,
    StatoPrenotazione,
    SyncRun,
)
from app.core.date_range import utcnow
from app.core.jobs import Job, JobStatus


class FeedIcalRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, host_id: uuid.UUID, feed: FeedIcal) -> FeedIcal:
        feed.host_id = host_id
        self._db.add(feed)
        return feed

    def by_id(self, host_id: uuid.UUID, feed_id: uuid.UUID) -> FeedIcal | None:
        return self._db.scalars(
            select(FeedIcal).where(FeedIcal.host_id == host_id, FeedIcal.id == feed_id)
        ).one_or_none()

    def della_struttura(
        self, host_id: uuid.UUID, struttura_id: uuid.UUID
    ) -> list[FeedIcal]:
        return list(
            self._db.scalars(
                select(FeedIcal)
                .where(
                    FeedIcal.host_id == host_id,
                    FeedIcal.struttura_id == struttura_id,
                )
                .order_by(FeedIcal.collegato_il)
            )
        )

    def sync_in_coda(
        self, host_id: uuid.UUID, feed_id: uuid.UUID, *, tipo_job: str
    ) -> bool:
        """C'è un sync accodato o in esecuzione per questo Feed?

        È ciò che distingue «Importazione in corso…» da «mai sincronizzato»:
        senza questa domanda l'Host non saprebbe se attendere o se qualcosa è
        andato storto. `tipo_job` arriva dal chiamante perché `jobs` importa
        `service`, che importa questo modulo: passarlo evita il ciclo.
        """
        return (
            self._db.scalars(
                select(Job.id)
                .where(
                    Job.job_type == tipo_job,
                    Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
                    Job.payload["feed_id"].astext == str(feed_id),
                    Job.payload["host_id"].astext == str(host_id),
                )
                .limit(1)
            ).first()
            is not None
        )


class SyncRunRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, host_id: uuid.UUID, run: SyncRun) -> SyncRun:
        run.host_id = host_id
        self._db.add(run)
        return run

    def ultimo(self, host_id: uuid.UUID, feed_id: uuid.UUID) -> SyncRun | None:
        return self._db.scalars(self._per_feed(host_id, feed_id).limit(1)).first()

    def ultimo_riuscito(self, host_id: uuid.UUID, feed_id: uuid.UUID) -> SyncRun | None:
        return self._db.scalars(
            self._per_feed(host_id, feed_id)
            .where(SyncRun.esito == EsitoSyncRun.RIUSCITO)
            .limit(1)
        ).first()

    @staticmethod
    def _per_feed(host_id: uuid.UUID, feed_id: uuid.UUID) -> Select[tuple[SyncRun]]:
        return (
            select(SyncRun)
            .where(SyncRun.host_id == host_id, SyncRun.feed_id == feed_id)
            .order_by(SyncRun.concluso_il.desc(), SyncRun.id.desc())
        )


class PrenotazioneRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def upsert_dal_feed(
        self,
        host_id: uuid.UUID,
        *,
        feed_id: uuid.UUID,
        struttura_id: uuid.UUID,
        canale: CanaleFeed,
        ical_uid: str,
        check_in: object,
        check_out: object,
        sommario: str | None,
        cancellata: bool,
    ) -> str:
        """Inserisce o aggiorna la Prenotazione; ritorna cosa è successo.

        Esiti possibili: `"importata"`, `"aggiornata"`, `"ricomparsa"`.

        Sul conflitto lo stato NON risale mai da `rimossa_dal_feed`: un
        evento che ricompare nel feed non torna `attiva` da solo, perché la
        transizione di ritorno è una decisione di prodotto ancora aperta
        (test design §4.2-2). Il fatto non si perde: l'esito `"ricomparsa"`
        lo porta nel `sync_run`.
        """
        adesso = utcnow()
        stato_dal_feed = (
            StatoPrenotazione.CANCELLATA if cancellata else StatoPrenotazione.ATTIVA
        )
        inserimento = pg_insert(Prenotazione).values(
            host_id=host_id,
            struttura_id=struttura_id,
            feed_id=feed_id,
            ical_uid=ical_uid,
            canale=canale,
            check_in=check_in,
            check_out=check_out,
            sommario=sommario,
            stato=stato_dal_feed,
            creata_il=adesso,
            aggiornata_il=adesso,
        )
        istruzione = inserimento.on_conflict_do_update(
            constraint="uq_prenotazione_feed_ical_uid",
            set_={
                "check_in": inserimento.excluded.check_in,
                "check_out": inserimento.excluded.check_out,
                "sommario": inserimento.excluded.sommario,
                "stato": case(
                    (
                        Prenotazione.stato == StatoPrenotazione.RIMOSSA_DAL_FEED,
                        Prenotazione.stato,
                    ),
                    else_=inserimento.excluded.stato,
                ),
                "aggiornata_il": inserimento.excluded.aggiornata_il,
            },
        ).returning(
            # `xmax = 0` distingue la riga appena inserita da quella
            # aggiornata: senza questo il conteggio «importate» sarebbe una
            # stima.
            text("(xmax = 0) AS inserita"),
            Prenotazione.stato,
        )
        inserita, stato = self._db.execute(istruzione).one()
        if inserita:
            return "importata"
        if stato is StatoPrenotazione.RIMOSSA_DAL_FEED:
            return "ricomparsa"
        return "aggiornata"

    def marca_rimosse_dal_feed(
        self, host_id: uuid.UUID, *, feed_id: uuid.UUID, uid_presenti: Iterable[str]
    ) -> int:
        """Transizione, non cancellazione (AD-4, AD-19): ritorna quante.

        `uid_presenti` deve contenere **tutti** gli uid letti dal feed, non
        solo quelli normalizzati con successo: un VEVENT malformato ma con
        uid è comunque nel feed, e trattarlo come scomparso marcherebbe
        `rimossa_dal_feed` una Prenotazione viva.
        """
        istruzione = (
            update(Prenotazione)
            .where(
                Prenotazione.host_id == host_id,
                Prenotazione.feed_id == feed_id,
                Prenotazione.stato == StatoPrenotazione.ATTIVA,
                Prenotazione.ical_uid.not_in(list(uid_presenti)),
            )
            .values(stato=StatoPrenotazione.RIMOSSA_DAL_FEED, aggiornata_il=utcnow())
        )
        # `cast`: `Session.execute` è tipizzato genericamente, ma una UPDATE
        # restituisce sempre un CursorResult, che espone `rowcount` (stesso
        # motivo del `cast` in app/identity/jobs.py).
        esito = cast(CursorResult, self._db.execute(istruzione))
        return int(esito.rowcount or 0)

    def del_feed(self, host_id: uuid.UUID, feed_id: uuid.UUID) -> list[Prenotazione]:
        return list(
            self._db.scalars(
                select(Prenotazione)
                .where(
                    Prenotazione.host_id == host_id,
                    Prenotazione.feed_id == feed_id,
                )
                .order_by(Prenotazione.check_in, Prenotazione.ical_uid)
            )
        )

    def della_struttura(
        self, host_id: uuid.UUID, struttura_id: uuid.UUID
    ) -> list[Prenotazione]:
        return list(
            self._db.scalars(
                select(Prenotazione)
                .where(
                    Prenotazione.host_id == host_id,
                    Prenotazione.struttura_id == struttura_id,
                )
                .order_by(Prenotazione.check_in)
            )
        )

    def conta_per_stato(
        self, host_id: uuid.UUID, feed_id: uuid.UUID
    ) -> dict[StatoPrenotazione, int]:
        righe: Sequence[tuple[StatoPrenotazione, int]] = self._db.execute(
            select(Prenotazione.stato, func.count())
            .where(
                Prenotazione.host_id == host_id,
                Prenotazione.feed_id == feed_id,
            )
            .group_by(Prenotazione.stato)
        ).all()  # type: ignore[assignment]
        return {stato: conteggio for stato, conteggio in righe}
