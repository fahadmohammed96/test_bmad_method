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
from datetime import date, datetime
from typing import cast

from sqlalchemy import Select, case, func, literal, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.calendario.models import (
    CanaleFeed,
    EsitoSyncRun,
    FeedIcal,
    Ospite,
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

    def dell_host(
        self, host_id: uuid.UUID, *, struttura_id: uuid.UUID | None = None
    ) -> list[FeedIcal]:
        """Tutti i Feed dell'Host, o quelli di una sola Struttura.

        È il perimetro su cui il Calendario deriva «dati aggiornati alle
        HH:MM»: la vista aggregata mostra dati che vengono da PIÙ Feed, e la
        loro freschezza è quella del più vecchio (UX-DR1, NFR-2).
        """
        criteri = [FeedIcal.host_id == host_id]
        if struttura_id is not None:
            criteri.append(FeedIcal.struttura_id == struttura_id)
        return list(
            self._db.scalars(
                select(FeedIcal).where(*criteri).order_by(FeedIcal.collegato_il)
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
        """Sorgente del «dati aggiornati alle HH:MM»: include i run da 304.

        Un 304 è una verifica riuscita — abbiamo chiesto al portale e ci ha
        confermato che i dati che mostriamo sono correnti — quindi il
        timestamp deve avanzare. Per i CONTEGGI serve l'altra domanda:
        `ultimo_riconciliato`.
        """
        return self._db.scalars(
            self._per_feed(host_id, feed_id)
            .where(SyncRun.esito == EsitoSyncRun.RIUSCITO)
            .limit(1)
        ).first()

    def ultimo_riconciliato(
        self, host_id: uuid.UUID, feed_id: uuid.UUID
    ) -> SyncRun | None:
        """L'ultimo run che ha davvero letto e riconciliato un calendario.

        Distinto da `ultimo_riuscito` per una ragione che si vede solo
        mettendo insieme il 304 e la superficie: `eventi_malformati` e
        `eventi_ricorrenti_non_espansi` sono AVVISI all'Host su righe che non
        sono state importate. Un run da 304 è riuscito e ha tutti i contatori
        a zero, quindi derivarli da `ultimo_riuscito` li spegnerebbe — e li
        spegnerebbe **perché non è cambiato niente**, cioè proprio quando gli
        eventi illeggibili ci sono ancora tutti. Un avviso che sparisce da sé
        è peggio di nessun avviso.
        """
        return self._db.scalars(
            self._per_feed(host_id, feed_id)
            .where(
                SyncRun.esito == EsitoSyncRun.RIUSCITO,
                SyncRun.non_modificato.is_(False),
            )
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
            cessata_il=adesso if cancellata else None,
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
                # `cessata_il` segue lo stato RISULTANTE, e si conserva se
                # c'era già: è la decorrenza della retention (AD-21), e
                # riscriverla a ogni sync sposterebbe in avanti la scadenza
                # di un'anagrafica ferma da mesi — un dato personale
                # conservato per sempre, un sync alla volta.
                "cessata_il": self._cessata_il_dopo_upsert(adesso, cancellata),
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

    @staticmethod
    def _cessata_il_dopo_upsert(adesso: datetime, cancellata: bool) -> object:
        """Quando la Prenotazione è uscita da `attiva`, dopo questo upsert.

        Tre casi, e nessuno dei tre è «adesso» incondizionato:

        - il feed la dà cancellata ⇒ è cessata; ma se lo era già, vale la
          data di ALLORA (`COALESCE`), altrimenti ogni sync rimanderebbe
          avanti la retention di novanta giorni;
        - il feed la dà viva ma la riga è `rimossa_dal_feed` ⇒ lo stato non
          risale (vedi sopra), quindi nemmeno la sua decorrenza;
        - il feed la dà viva e la riga torna/resta `attiva` ⇒ `NULL`: una
          Prenotazione attiva non ha una data di cessazione, e lasciarne una
          vecchia farebbe scadere l'anagrafica di un soggiorno futuro.
        """
        if cancellata:
            return func.coalesce(Prenotazione.cessata_il, adesso)
        return case(
            (
                Prenotazione.stato == StatoPrenotazione.RIMOSSA_DAL_FEED,
                Prenotazione.cessata_il,
            ),
            else_=None,
        )

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
        adesso = utcnow()
        istruzione = (
            update(Prenotazione)
            .where(
                Prenotazione.host_id == host_id,
                Prenotazione.feed_id == feed_id,
                Prenotazione.stato == StatoPrenotazione.ATTIVA,
                Prenotazione.ical_uid.not_in(uid_presenti),
            )
            .values(
                stato=StatoPrenotazione.RIMOSSA_DAL_FEED,
                # Uscita da `attiva`: da qui decorre la retention
                # dell'anagrafica Ospite se precede il `check_out` (AD-21).
                # Il filtro seleziona solo righe `attiva`, che hanno
                # `cessata_il` a NULL: nessuna data preesistente da salvare.
                cessata_il=adesso,
                aggiornata_il=adesso,
            )
        )
        # `cast`: `Session.execute` è tipizzato genericamente, ma una UPDATE
        # restituisce sempre un CursorResult, che espone `rowcount` (stesso
        # motivo del `cast` in app/identity/jobs.py).
        esito = cast(CursorResult, self._db.execute(istruzione))
        return int(esito.rowcount or 0)

    def by_id(
        self, host_id: uuid.UUID, prenotazione_id: uuid.UUID
    ) -> Prenotazione | None:
        return self._db.scalars(
            select(Prenotazione).where(
                Prenotazione.host_id == host_id, Prenotazione.id == prenotazione_id
            )
        ).one_or_none()

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

        `da` è il primo giorno che al chiamante interessa, e non è «oggi»: il
        chiamante passa il primo giorno NON ancora iniziato, perché un
        check-in odierno è un arrivo già avvenuto e con `LIMIT 1`
        oscurerebbe quello di domani. La decisione sta nel service, che è
        l'unico posto in cui «arrivo futuro» ha un significato.

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

    def nel_periodo(
        self,
        host_id: uuid.UUID,
        *,
        da: date,
        a: date,
        struttura_id: uuid.UUID | None = None,
    ) -> list[Prenotazione]:
        """Prenotazioni che occupano almeno una notte fra `da` e `a` inclusi.

        Il periodo della griglia è un insieme di NOTTI, e una Prenotazione
        occupa `[check_in, check_out)` (AD-3): tocca il periodo quando
        `check_in <= a` e `check_out > da`. Il `>` stretto sul `check_out` è
        il confine dell'intervallo semiaperto — con `>=` una Prenotazione
        che finisce il primo giorno visibile comparirebbe in un mese in cui
        non c'è nessun suo pernottamento, e la stessa riga si vedrebbe due
        volte cambiando pagina.

        **Tutti gli stati**, non solo `attiva`: una Prenotazione uscita da
        `attiva` resta visibile con la sua etichetta. Farla sparire senza
        traccia contraddirebbe «archiviare, mai distruggere» agli occhi
        dell'Host, che quella prenotazione l'ha vista ieri (AD-19, AD-20,
        test design §4.2-12).
        """
        criteri = [
            Prenotazione.host_id == host_id,
            Prenotazione.check_in <= a,
            Prenotazione.check_out > da,
        ]
        if struttura_id is not None:
            criteri.append(Prenotazione.struttura_id == struttura_id)
        return list(
            self._db.scalars(
                select(Prenotazione)
                .where(*criteri)
                # Ordine STABILE: la griglia assegna le corsie nell'ordine in
                # cui riceve le Prenotazioni, e un ordine che dipende dal
                # piano del database farebbe saltare le righe da una corsia
                # all'altra fra due letture identiche.
                .order_by(
                    Prenotazione.check_in,
                    Prenotazione.check_out,
                    Prenotazione.id,
                )
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


class OspiteRepository:
    """Anagrafica Ospite (AD-21): scritta SOLO da `calendario` (AD-18).

    Nessun metodo scrive `nome`, `email` o `telefono` a partire da un altro
    campo: i valori arrivano dal chiamante, che li ha ricevuti dall'Host o
    letti esplicitamente dal Feed. Non c'è un percorso «deduci» perché non
    deve essercene uno (NFR-11).
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, host_id: uuid.UUID, ospite: Ospite) -> Ospite:
        ospite.host_id = host_id
        self._db.add(ospite)
        return ospite

    def della_prenotazione(
        self, host_id: uuid.UUID, prenotazione_id: uuid.UUID
    ) -> list[Ospite]:
        """Gli Ospiti di una Prenotazione, il principale per primo."""
        return list(
            self._db.scalars(
                select(Ospite)
                .where(
                    Ospite.host_id == host_id,
                    Ospite.prenotazione_id == prenotazione_id,
                )
                .order_by(Ospite.principale.desc(), Ospite.creato_il, Ospite.id)
            )
        )

    def per_prenotazioni(
        self, host_id: uuid.UUID, prenotazione_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[Ospite]]:
        """Gli Ospiti di più Prenotazioni in una lettura sola.

        Con `prenotazione_ids` VUOTO non si interroga affatto: un `IN ()`
        costruito da una lista calcolata a runtime è la trappola che in
        questo stesso modulo è già costata un P0 (`NOT IN ()` che degenera
        in «tutte le righe»). Qui l'`IN` vuoto darebbe zero righe invece di
        tutte — ma la guardia sta comunque nel punto più basso, perché la
        regola è «nessun predicato di insieme costruito da una lista che può
        essere vuota», non «questo caso è innocuo».
        """
        if not prenotazione_ids:
            return {}
        raggruppati: dict[uuid.UUID, list[Ospite]] = {}
        righe = self._db.scalars(
            select(Ospite)
            .where(
                Ospite.host_id == host_id,
                Ospite.prenotazione_id.in_(prenotazione_ids),
            )
            .order_by(Ospite.principale.desc(), Ospite.creato_il, Ospite.id)
        )
        for ospite in righe:
            raggruppati.setdefault(ospite.prenotazione_id, []).append(ospite)
        return raggruppati
