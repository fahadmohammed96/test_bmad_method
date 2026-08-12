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
from dataclasses import dataclass
from datetime import date, datetime
from typing import cast

from sqlalchemy import (
    DateTime,
    Select,
    Uuid,
    case,
    func,
    literal,
    or_,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.calendario.models import (
    AzzeramentoAudit,
    CanaleFeed,
    Conflitto,
    EsitoSyncRun,
    FeedIcal,
    Ospite,
    Prenotazione,
    StatoConflitto,
    StatoPrenotazione,
    SyncRun,
)
from app.core.date_range import utcnow
from app.core.db import new_uuid7
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


@dataclass(frozen=True, slots=True)
class PrenotazioneCessata:
    """Una Prenotazione appena USCITA da `attiva`, in soli identificatori.

    È ciò che serve a emettere `prenotazione.cessata` (AD-19, MYL-69): la
    `struttura_id` viaggia col fatto perché la rilevazione dei Conflitti è
    scopata alla Struttura, e senza di essa il consumatore dovrebbe rileggere
    la Prenotazione solo per sapere dove guardare.
    """

    id: uuid.UUID
    struttura_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ConflittoDecaduto:
    """Un Conflitto appena passato a `decaduto`, in soli identificatori."""

    id: uuid.UUID
    struttura_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class EsitoUpsert:
    """Cosa è successo alla riga, e se ha lasciato lo stato `attiva`.

    Due informazioni distinte, e la seconda non è deducibile dalla prima:
    `"aggiornata"` copre sia il sync che non cambia niente sia quello che
    porta la Prenotazione da `attiva` a `cancellata` perché il portale l'ha
    annullata — che è la TRANSIZIONE su cui la Story 2.5 fa `decadere` un
    Conflitto.
    """

    prenotazione_id: uuid.UUID
    esito: str
    uscita_da_attiva: bool


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
    ) -> EsitoUpsert:
        """Inserisce o aggiorna la Prenotazione; ritorna cosa è successo.

        Esiti possibili: `"importata"`, `"aggiornata"`, `"ricomparsa"`.

        Sul conflitto lo stato NON risale mai da `rimossa_dal_feed`: un
        evento che ricompare nel feed non torna `attiva` da solo, perché la
        transizione di ritorno è una decisione di prodotto ancora aperta
        (test design §4.2-2). Il fatto non si perde: l'esito `"ricomparsa"`
        lo porta nel `sync_run`.

        **Come si riconosce la transizione `attiva → cancellata`** (MYL-69,
        strada 3). In un `ON CONFLICT DO UPDATE` il `RETURNING` di Postgres
        vede la riga NUOVA, mai quella vecchia: «è `cancellata`» si legge,
        «ERA `attiva` e ora è `cancellata`» no — e sono due proprietà diverse,
        perché la prima è vera anche al decimo sync consecutivo che trova la
        stessa Prenotazione già annullata da settimane.

        L'informazione che manca è però già scritta qui accanto:
        `_cessata_il_dopo_upsert` conserva con un `COALESCE` la decorrenza di
        una riga già cessata, quindi `cessata_il` torna uguale ad `adesso`
        **solo** se questa esecuzione è quella che l'ha fatta uscire da
        `attiva`. È lo stesso dato che protegge la retention di AD-21 dallo
        spostamento in avanti, letto per la domanda gemella.

        Emettere a ogni sync invece che alla transizione non darebbe alcun
        errore: farebbe `decadere` più volte lo stesso Conflitto e
        rimanderebbe avanti la scadenza di un dato personale.
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
                # Un campo azzerato non è ripopolabile da un sync successivo
                # (AD-21): su una Prenotazione anonimizzata il `sommario` resta
                # quello che è, cioè `NULL`. Senza questa clausola un feed che
                # conserva i VEVENT passati riscriverebbe il campo appena
                # azzerato, e `anonimizzato_il` resterebbe lì ad attestare un
                # azzeramento non più vero — un'evidenza che mente, peggio
                # dell'assenza di evidenza.
                #
                # La guardia è sul CAMPO, non sulla riga: `check_in`,
                # `check_out` e `stato` qui sopra continuano ad aggiornarsi.
                "sommario": case(
                    (
                        Prenotazione.anonimizzato_il.is_not(None),
                        Prenotazione.sommario,
                    ),
                    else_=inserimento.excluded.sommario,
                ),
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
            Prenotazione.id,
            Prenotazione.stato,
            Prenotazione.cessata_il,
        )
        inserita, prenotazione_id, stato, cessata_il = self._db.execute(
            istruzione
        ).one()
        # Una riga INSERITA ora non è mai uscita da `attiva`: non c'è mai
        # stata. Un VEVENT già `CANCELLED` al primo import nasce `cancellata`
        # e non ha alcun Conflitto da far decadere, quindi non è il fatto che
        # `prenotazione.cessata` racconta.
        uscita_da_attiva = (
            not inserita
            and stato is StatoPrenotazione.CANCELLATA
            and cessata_il == adesso
        )
        if inserita:
            return EsitoUpsert(
                prenotazione_id=prenotazione_id,
                esito="importata",
                uscita_da_attiva=False,
            )
        if stato is StatoPrenotazione.RIMOSSA_DAL_FEED:
            return EsitoUpsert(
                prenotazione_id=prenotazione_id,
                esito="ricomparsa",
                uscita_da_attiva=False,
            )
        return EsitoUpsert(
            prenotazione_id=prenotazione_id,
            esito="aggiornata",
            uscita_da_attiva=uscita_da_attiva,
        )

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

    def crea_manuale(
        self,
        host_id: uuid.UUID,
        *,
        struttura_id: uuid.UUID,
        check_in: date,
        check_out: date,
        sommario: str | None,
    ) -> Prenotazione:
        """La Prenotazione scritta dall'Host (Story 2.4): mai legata a un Feed.

        `feed_id` e `ical_uid` restano `NULL` — è ciò che distingue una manuale,
        ed è il motivo per cui il UNIQUE `(feed_id, ical_uid)` non le collassa:
        in Postgres i `NULL` sono distinti fra loro dentro un indice. Il CHECK
        `(feed_id IS NULL) = (ical_uid IS NULL)` chiude la forma mista, che
        sarebbe l'unica in grado di aggirare quel UNIQUE.

        Nessun `commit`: la transazione è del chiamante, come ovunque in questo
        modulo.
        """
        adesso = utcnow()
        prenotazione = Prenotazione(
            host_id=host_id,
            struttura_id=struttura_id,
            canale=CanaleFeed.MANUALE,
            check_in=check_in,
            check_out=check_out,
            sommario=sommario,
            stato=StatoPrenotazione.ATTIVA,
            creata_il=adesso,
            aggiornata_il=adesso,
        )
        self._db.add(prenotazione)
        return prenotazione

    def marca_cancellata(
        self, host_id: uuid.UUID, *, prenotazione_id: uuid.UUID, adesso: datetime
    ) -> int:
        """Porta una manuale ATTIVA a `cancellata`; ritorna quante righe.

        Transizione, mai una `DELETE` (AD-19, AD-20, GS-6).

        La condizione sullo stato sta **dentro** la `UPDATE`, non in un `if`
        che la precede: così la lettura e la scrittura sono la stessa
        istruzione e il doppio click di un Host — o due schede aperte — non è
        un check-then-write. Il chiamante lo scopre dal `rowcount`: chi ottiene
        `1` ha fatto la transizione ed emette l'evento, chi ottiene `0` trova
        la Prenotazione già cessata e non emette nulla.

        Con l'`if` fuori passerebbero entrambi: misurato su otto contendenti,
        **cinque** `prenotazione.cessata` invece di uno
        (`tests/test_gara_cancellazione_prenotazione.py`). Le conseguenze sono
        due, e nessuna delle due dà errore: `cessata_il` riscritta rimanda in
        avanti la scadenza di un dato personale (AD-21), e nella Story 2.5 lo
        stesso Conflitto farebbe `decadere` più volte.

        `feed_id IS NULL` nel filtro è difesa in profondità: lo stato di una
        Prenotazione da Feed lo decide il portale (AD-4), e il service la
        rifiuta già con un errore parlante. Qui il vincolo resta anche per un
        chiamante futuro che quel controllo non lo faccia.
        """
        istruzione = (
            update(Prenotazione)
            .where(
                Prenotazione.host_id == host_id,
                Prenotazione.id == prenotazione_id,
                Prenotazione.feed_id.is_(None),
                Prenotazione.stato == StatoPrenotazione.ATTIVA,
            )
            .values(
                stato=StatoPrenotazione.CANCELLATA,
                # Uscita da `attiva`: da qui decorre la retention
                # dell'anagrafica se precede il `check_out` (AD-21). Il filtro
                # seleziona solo righe `attiva`, che hanno `cessata_il` a
                # `NULL`: nessuna data preesistente da conservare.
                cessata_il=adesso,
                aggiornata_il=adesso,
            )
        )
        esito = cast(CursorResult, self._db.execute(istruzione))
        return int(esito.rowcount or 0)

    def marca_rimosse_dal_feed(
        self, host_id: uuid.UUID, *, feed_id: uuid.UUID, uid_presenti: Sequence[str]
    ) -> list["PrenotazioneCessata"]:
        """Transizione, non cancellazione (AD-4, AD-19): ritorna QUALI.

        **Quali, non quante**, ed è il cambiamento che la Story 2.5 richiede
        (MYL-69, opzione A). Ogni uscita da `attiva` emette
        `prenotazione.cessata`, e un evento per Prenotazione ha bisogno degli
        identificatori delle righe toccate: questa è una `UPDATE` di massa, e
        un `rowcount` dice quante sono state ma non chi. `RETURNING` è ciò che
        rende la domanda rispondibile senza una seconda lettura — che sarebbe
        anche una lettura su uno stato già cambiato, quindi non più in grado
        di distinguere chi è appena transitato da chi lo era già.

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
            return []
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
            .returning(Prenotazione.id, Prenotazione.struttura_id)
        )
        return [
            PrenotazioneCessata(id=riga_id, struttura_id=struttura_id)
            for riga_id, struttura_id in self._db.execute(istruzione).all()
        ]

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

    def attive_della_struttura(
        self, host_id: uuid.UUID, struttura_id: uuid.UUID
    ) -> list[Prenotazione]:
        """L'insieme su cui gira la rilevazione dei Conflitti (AD-5, AD-19).

        **Solo `attiva`**, e il filtro sta nella query: una Prenotazione
        cancellata o `rimossa_dal_feed` non concorre ai Conflitti, e
        selezionarle tutte per scartarle in Python renderebbe la regola pura
        responsabile di una decisione che è di AD-19.

        Ordine STABILE fino all'`id`: la rilevazione è deterministica per
        costruzione, ma un insieme che arriva in ordine diverso a ogni
        lettura rende irriproducibile qualunque confronto fra due esecuzioni.

        Sostituisce il precedente `della_struttura`, che non aveva chiamanti
        in produzione (E2-F23: i soli 10 mutanti `no tests` dello spike
        MYL-72). La forma che serviva alla 2.5 è questa — l'insieme `attiva`
        di una Struttura — e un metodo senza chiamante è il posto in cui il
        prossimo difetto della stessa famiglia si nasconde.
        """
        return list(
            self._db.scalars(
                select(Prenotazione)
                .where(
                    Prenotazione.host_id == host_id,
                    Prenotazione.struttura_id == struttura_id,
                    Prenotazione.stato == StatoPrenotazione.ATTIVA,
                )
                .order_by(
                    Prenotazione.check_in,
                    Prenotazione.check_out,
                    Prenotazione.id,
                )
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

    def by_id(self, host_id: uuid.UUID, ospite_id: uuid.UUID) -> Ospite | None:
        return self._db.scalars(
            select(Ospite).where(Ospite.host_id == host_id, Ospite.id == ospite_id)
        ).one_or_none()

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


class ConflittoRepository:
    """Il Conflitto (AD-5): si apre, si fa decadere, non si cancella MAI.

    Nessun metodo scrive lo stato `gestito`: quella transizione è un'azione
    esplicita dell'Host e arriva con la Story 2.7. Nessun metodo cancella:
    `decaduto` è una transizione tracciata, e la riga resta nello storico
    (AD-20, GS-6).
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def apri(
        self,
        host_id: uuid.UUID,
        *,
        struttura_id: uuid.UUID,
        prenotazione_min_id: uuid.UUID,
        prenotazione_max_id: uuid.UUID,
        adesso: datetime,
    ) -> uuid.UUID | None:
        """Apre il Conflitto della coppia; `None` se ce n'è già uno aperto.

        **Una sola istruzione**, e non è un vezzo: «esiste già?» seguito da
        «aprilo» è un check-then-write, e sotto otto rilevazioni concorrenti
        sulla stessa Struttura — due Feed che concludono l'import insieme —
        lo passano tutti (gara A3-4). Qui a decidere è il database, in due
        modi che coprono due casi diversi:

        - `ON CONFLICT DO NOTHING` sull'indice UNIQUE parziale ferma il
          secondo `rilevato` per la stessa coppia. È l'invariante di AD-5, e
          vive nello schema perché sotto concorrenza il codice perde;
        - il `WHERE NOT EXISTS` sullo stato `gestito` impedisce di riaprire
          da sé un Conflitto che l'Host ha già chiuso. La riapertura dopo
          `gestito` esiste (AD-5) ma ha una finestra configurabile e un
          collegamento al precedente: è materia della Story 2.7, e una
          rilevazione che aprisse un `rilevato` nuovo al primo sync
          successivo la scavalcherebbe silenziosamente.

        Il chiamante decide dal ritorno: chi ottiene un id ha aperto il
        Conflitto ed emette l'evento, chi ottiene `None` ha trovato il lavoro
        già fatto e non emette nulla — la stessa forma di `marca_cancellata`.
        """
        nuovo_id = new_uuid7()
        gia_gestito = (
            select(Conflitto.id)
            .where(
                Conflitto.host_id == host_id,
                Conflitto.struttura_id == struttura_id,
                Conflitto.prenotazione_min_id == prenotazione_min_id,
                Conflitto.prenotazione_max_id == prenotazione_max_id,
                Conflitto.stato == StatoConflitto.GESTITO,
            )
            .exists()
        )
        sorgente = select(
            literal(nuovo_id, Uuid),
            literal(host_id, Uuid),
            literal(struttura_id, Uuid),
            literal(prenotazione_min_id, Uuid),
            literal(prenotazione_max_id, Uuid),
            literal(StatoConflitto.RILEVATO, Conflitto.__table__.c.stato.type),
            literal(adesso, DateTime(timezone=True)),
        ).where(~gia_gestito)
        istruzione = (
            pg_insert(Conflitto)
            .from_select(
                [
                    "id",
                    "host_id",
                    "struttura_id",
                    "prenotazione_min_id",
                    "prenotazione_max_id",
                    "stato",
                    "rilevato_il",
                ],
                sorgente,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "struttura_id",
                    "prenotazione_min_id",
                    "prenotazione_max_id",
                ],
                # Letterale e non un parametro: Postgres deduce l'indice
                # dalla forma del predicato, e un `$1` non gli permette di
                # riconoscere quello parziale.
                index_where=text("stato = 'rilevato'"),
            )
            # `RETURNING` e non il `rowcount`: su un `INSERT … SELECT`
            # SQLAlchemy non garantisce il conteggio e restituisce `-1`
            # quando non lo ha — un valore VERO in un `if`, quindi ogni
            # tentativo si sarebbe dichiarato riuscito e ogni rilevazione
            # avrebbe emesso un `conflitto.rilevato` di troppo. Misurato:
            # il vincolo faceva il suo lavoro (nessuna riga doppia) e il
            # chiamante non se ne accorgeva. Con `RETURNING` la domanda «ho
            # inserito?» ha per risposta la riga stessa.
            .returning(Conflitto.id)
        )
        inserito = self._db.execute(istruzione).first()
        return None if inserito is None else nuovo_id

    def decadi_per_prenotazione(
        self, host_id: uuid.UUID, *, prenotazione_id: uuid.UUID, adesso: datetime
    ) -> list["ConflittoDecaduto"]:
        """Fa decadere i Conflitti aperti che coinvolgono la Prenotazione.

        Transizione di SISTEMA (AD-5), tracciata e distinta da `gestito`: la
        sovrapposizione è cessata perché una delle due Prenotazioni è uscita
        da `attiva`, non perché l'Host abbia deciso qualcosa.

        La condizione sullo stato sta **dentro** la `UPDATE`: la consegna
        degli eventi è at-least-once (AD-10), quindi questo percorso viene
        rieseguito sullo stesso fatto ogni volta che un handler più avanti
        nel batch fallisce. Con l'`if` fuori il secondo giro riscriverebbe
        `decaduto_il` — cioè sposterebbe la data di un fatto già avvenuto,
        che è ciò che SM-C1 misura — e riemetterebbe l'evento. Qui il secondo
        giro tocca zero righe e non ritorna niente.

        La coppia non è ordinata: la Prenotazione può essere il `min` o il
        `max`, e cercare in una sola delle due colonne lascerebbe metà dei
        Conflitti accesi su una Prenotazione che non esiste più.

        **La Prenotazione deve essere fuori da `attiva` ADESSO** (F1). Non è
        una ripetizione dell'idempotenza, che regge da sola: è la difesa
        contro un fatto **vero quando è stato scritto e falso quando lo si
        consuma**. La consegna è asincrona, e fra le due cose lo stato può
        essere tornato indietro — una `cancellata` che il portale ritira
        torna `attiva`, perché la clausola che blocca il ritorno nell'upsert
        protegge solo `rimossa_dal_feed`. Senza questa condizione un evento
        in ritardo spegne un Conflitto fra due Prenotazioni ancora vive e
        ancora sovrapposte: l'AC 11 dal lato opposto, con un
        `conflitto.decaduto` di troppo che `outbox` conserva per sempre.

        Sta **dentro** la `UPDATE` per la stessa ragione di tutto il resto in
        questo modulo: fuori sarebbe un check-then-write, e la rilevazione
        che riporta `attiva` la Prenotazione gira in un'altra transazione.
        """
        ancora_attiva = (
            select(Prenotazione.id)
            .where(
                Prenotazione.host_id == host_id,
                Prenotazione.id == prenotazione_id,
                Prenotazione.stato == StatoPrenotazione.ATTIVA,
            )
            .exists()
        )
        istruzione = (
            update(Conflitto)
            .where(
                Conflitto.host_id == host_id,
                or_(
                    Conflitto.prenotazione_min_id == prenotazione_id,
                    Conflitto.prenotazione_max_id == prenotazione_id,
                ),
                # `rilevato` E `gestito`: AD-5 ammette il decadimento da
                # entrambi — una sovrapposizione che cessa dopo che l'Host
                # l'ha gestita è comunque cessata.
                Conflitto.stato != StatoConflitto.DECADUTO,
                ~ancora_attiva,
            )
            .values(stato=StatoConflitto.DECADUTO, decaduto_il=adesso)
            .returning(Conflitto.id, Conflitto.struttura_id)
        )
        return [
            ConflittoDecaduto(id=riga_id, struttura_id=struttura_id)
            for riga_id, struttura_id in self._db.execute(istruzione).all()
        ]

    def rilevati(
        self, host_id: uuid.UUID, *, struttura_id: uuid.UUID | None = None
    ) -> list[Conflitto]:
        """I Conflitti che aspettano una decisione dell'Host (FR-6).

        Nessun filtro temporale, e l'assenza è il requisito: un Conflitto
        `rilevato` resta in evidenza finché non è gestito. Un'esclusione «dopo
        N giorni» lo farebbe sparire da solo dalla Dashboard — cioè il
        prodotto smetterebbe di segnalare una doppia prenotazione che è
        ancora lì (gemello di AD-8).
        """
        criteri = [
            Conflitto.host_id == host_id,
            Conflitto.stato == StatoConflitto.RILEVATO,
        ]
        if struttura_id is not None:
            criteri.append(Conflitto.struttura_id == struttura_id)
        return list(
            self._db.scalars(
                select(Conflitto)
                .where(*criteri)
                # Il più vecchio per primo: è quello che aspetta da più tempo,
                # e l'ordine non deve dipendere dal piano del database.
                .order_by(Conflitto.rilevato_il, Conflitto.id)
            )
        )

    # `by_id` era stato rimosso nella 2.5 perché non aveva chiamanti (E2-F23):
    # un metodo di repository arriva con il percorso che lo usa, o non arriva.
    # Il percorso è arrivato con la 2.6 — il testo della notifica si compone
    # alla consegna a partire dall'identificatore del Conflitto — e il metodo
    # torna insieme a lui.
    def by_id(self, host_id: uuid.UUID, conflitto_id: uuid.UUID) -> Conflitto | None:
        return self._db.scalars(
            select(Conflitto).where(
                Conflitto.host_id == host_id, Conflitto.id == conflitto_id
            )
        ).one_or_none()


class AzzeramentoAuditRepository:
    """Traccia chi/cosa/quando degli azzeramenti CHIESTI (NFR-15).

    Append-only: si scrive e non si rilegge da nessun percorso applicativo —
    esiste per essere interrogata quando qualcuno deve dimostrare che una
    richiesta è stata evasa, e una traccia che il codice può modificare non
    dimostra niente.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, host_id: uuid.UUID, audit: AzzeramentoAudit) -> AzzeramentoAudit:
        audit.host_id = host_id
        self._db.add(audit)
        return audit
