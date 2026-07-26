"""Repository di `calendario`: OGNI metodo richiede host_id (AD-2, G-3).

L'idempotenza dell'import vive qui, e vive nel DATABASE: `upsert` è un
`INSERT ... ON CONFLICT (feed_id, ical_uid) DO UPDATE`, senza alcun
pre-check applicativo. Un pre-check («esiste già?» poi «inserisci») è un
check-then-write: sotto due sync concorrenti dello stesso Feed passano
entrambi il controllo e nascono due righe. A decidere deve essere il
constraint (lezione G-2 dell'Epic 1, test di gara A3-1).
"""

import uuid
from collections.abc import Sequence
from datetime import date
from typing import cast

from sqlalchemy import Select, case, func, literal, select, text, tuple_, update
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

    def aggiorna_validatori(
        self,
        host_id: uuid.UUID,
        *,
        feed_id: uuid.UUID,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        """Sostituisce i validatori di cache dopo un import riuscito (AD-4).

        Si SOSTITUISCONO, non si fondono: una risposta 200 senza `ETag` deve
        azzerare quello vecchio. Tenerlo significherebbe continuare a mandare
        un `If-None-Match` che il portale non ha più modo di soddisfare — e
        se per qualunque ragione lo soddisfacesse, il Feed resterebbe fermo
        su un validatore che non descrive più niente, dichiarandosi
        aggiornato.
        """
        self._db.execute(
            update(FeedIcal)
            .where(FeedIcal.host_id == host_id, FeedIcal.id == feed_id)
            .values(etag=etag, last_modified=last_modified)
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

    def fallimenti_consecutivi(self, host_id: uuid.UUID, feed_id: uuid.UUID) -> int:
        """Quanti run falliti dall'ultimo riuscito in poi (AR-10, NFR-1).

        DERIVATO dalla traccia append-only, non tenuto in un contatore sul
        Feed. È la stessa scelta di `ultimo_sync_riuscito_il`, e per la stessa
        ragione: un contatore mantenuto a parte ha due punti di scrittura —
        l'incremento sul fallimento e **l'azzeramento al primo successo** — e
        il secondo è quello che si dimentica. Un contatore che non si azzera
        fa suonare l'alert per sempre su un Feed che ha ripreso a funzionare,
        e un alert che suona sempre è un alert spento.

        Derivandolo, l'azzeramento non è codice che qualcuno deve ricordarsi
        di scrivere: è una conseguenza della domanda.
        """
        ultimo_riuscito = self.ultimo_riuscito(host_id, feed_id)
        falliti = select(func.count()).where(
            SyncRun.host_id == host_id,
            SyncRun.feed_id == feed_id,
            SyncRun.esito == EsitoSyncRun.FALLITO,
        )
        if ultimo_riuscito is not None:
            # Tupla `(concluso_il, id)` e non il solo timestamp: è lo stesso
            # ordinamento di `_per_feed`, e due run conclusi nello stesso
            # istante — che nei test succede, e in produzione può succedere —
            # devono ordinarsi allo stesso modo qui e là, altrimenti il
            # conteggio e «l'ultimo riuscito» parlerebbero di insiemi diversi.
            falliti = falliti.where(
                tuple_(SyncRun.concluso_il, SyncRun.id)
                > tuple_(
                    literal(ultimo_riuscito.concluso_il),
                    literal(ultimo_riuscito.id),
                )
            )
        return int(self._db.scalar(falliti) or 0)

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
        self, host_id: uuid.UUID, *, feed_id: uuid.UUID, uid_presenti: Sequence[str]
    ) -> int:
        """Transizione, non cancellazione (AD-4, AD-19): ritorna quante.

        `uid_presenti` deve contenere **tutti** gli uid letti dal feed, non
        solo quelli normalizzati con successo: un VEVENT malformato ma con
        uid è comunque nel feed, e trattarlo come scomparso marcherebbe
        `rimossa_dal_feed` una Prenotazione viva.

        Con `uid_presenti` **vuoto** questa funzione non fa nulla, e la
        guardia è esplicita per una ragione precisa: SQLAlchemy rende un
        `NOT IN ()` espandibile come `(ical_uid NOT IN (NULL) OR (1 = 1))`,
        che è vero per ogni riga. La UPDATE degenererebbe in «tutte le
        Prenotazioni attive del Feed», cioè l'opposto esatto del suo scopo.
        Il chiamante non deve poterci arrivare — e se ci arriva, non deve
        succedere niente.
        """
        if not uid_presenti:
            return 0
        istruzione = (
            update(Prenotazione)
            .where(
                Prenotazione.host_id == host_id,
                Prenotazione.feed_id == feed_id,
                Prenotazione.stato == StatoPrenotazione.ATTIVA,
                Prenotazione.ical_uid.not_in(uid_presenti),
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

    def prossimo_check_in(
        self, host_id: uuid.UUID, *, struttura_id: uuid.UUID, da: date
    ) -> date | None:
        """Il primo check-in ATTIVO della Struttura da `da` in poi (G3-5).

        Serve all'intervallo adattivo: un Feed che ha un ospite in arrivo si
        risincronizza più spesso, perché è lì che una cancellazione tardiva
        non vista costa di più.

        Solo le Prenotazioni `attiva`: una `rimossa_dal_feed` o `cancellata`
        non è un arrivo, e trattarla come tale terrebbe un Feed morto sul
        ritmo stretto per sempre.
        """
        return self._db.scalars(
            select(Prenotazione.check_in)
            .where(
                Prenotazione.host_id == host_id,
                Prenotazione.struttura_id == struttura_id,
                Prenotazione.stato == StatoPrenotazione.ATTIVA,
                Prenotazione.check_in >= da,
            )
            .order_by(Prenotazione.check_in)
            .limit(1)
        ).first()

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
