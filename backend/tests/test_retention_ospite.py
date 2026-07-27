"""Retention dell'anagrafica Ospite (AD-21, NFR-12, NFR-15).

Tre livelli, e ognuno copre ciò che gli altri non possono:

- **unit** sulla regola pura — il confine fra scaduto e non scaduto, dove
  vive il difetto (un giorno di scarto è novanta giorni di dati personali
  conservati oltre il dovuto, o azzerati un giorno prima);
- **integrazione** sul job — che azzeri i CAMPI e non cancelli la riga, che
  la riesecuzione non cambi nulla, che si riprogrammi;
- **accordo** fra la regola pura e il predicato SQL che la traduce: sono due
  espressioni della stessa cosa e questo test è ciò che impedisce loro di
  divergere in silenzio.

Nessun dato reale di Ospiti (NFR-16): i nomi sono inventati, gli indirizzi
sono `example.com`.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.calendario.jobs import (
    TIPO_JOB_RETENTION_OSPITE,
    assicura_retention_periodica,
    azzera_anagrafiche_scadute,
)
from app.calendario.models import Ospite, Prenotazione, StatoPrenotazione
from app.calendario.retention import (
    LimiteRetention,
    PeriodoRetentionNonValidoError,
    filtro_scadute,
    limite_retention,
    scaduta,
)
from app.core.events import PayloadValidationError, catalog
from app.core.jobs import Job, JobStatus, run_due_jobs
from tests.calendario import Contesto, crea_prenotazione, registra_ospite

NOVANTA = timedelta(days=90)


def _limite(giorno: date, ora: str = "12:00") -> LimiteRetention:
    istante = datetime.fromisoformat(f"{giorno.isoformat()}T{ora}:00+00:00")
    return LimiteRetention(istante=istante, giorno=giorno)


class TestLaRegola:
    """Unit sulla regola pura: nessun database, nessun orologio."""

    def test_un_periodo_non_positivo_ferma_tutto(self) -> None:
        # Un `HOSTPILOT_OSPITE_RETENTION_GIORNI=0` letto dall'ambiente
        # azzererebbe i contatti della Prenotazione in corso, e il dato
        # azzerato non torna. Deve fermare l'avvio, non degradare.
        for periodo in (timedelta(0), timedelta(days=-1)):
            with pytest.raises(PeriodoRetentionNonValidoError):
                limite_retention(adesso=datetime.now(UTC), periodo=periodo)

    def test_il_limite_e_il_giorno_ROMANO_dell_istante_non_quello_utc(self) -> None:
        # 23:30 UTC del 15 gennaio è già il 16 gennaio a Roma (CET, +1): un
        # `.date()` sull'istante UTC direbbe il 15, e una Prenotazione
        # conclusa il 16 resterebbe con i contatti per un giorno in più —
        # ogni giorno, per sempre, senza che nessun test funzionale se ne
        # accorga.
        limite = limite_retention(
            adesso=datetime(2026, 1, 15, 23, 30, tzinfo=UTC) + NOVANTA,
            periodo=NOVANTA,
        )
        assert limite.giorno == date(2026, 1, 16)

    def test_lo_stesso_orario_utc_cade_in_due_giorni_diversi_secondo_l_ora_legale(
        self,
    ) -> None:
        # 22:30 UTC: d'inverno (CET, +1) è ancora lo stesso giorno a Roma,
        # d'estate (CEST, +2) è già quello dopo. È la ragione per cui la
        # conversione sta in una funzione provata e non in una sottrazione.
        inverno = limite_retention(
            adesso=datetime(2026, 1, 15, 22, 30, tzinfo=UTC) + NOVANTA, periodo=NOVANTA
        )
        estate = limite_retention(
            adesso=datetime(2026, 7, 15, 22, 30, tzinfo=UTC) + NOVANTA, periodo=NOVANTA
        )
        assert inverno.giorno == date(2026, 1, 15)
        assert estate.giorno == date(2026, 7, 16)

    @pytest.mark.parametrize(
        ("check_out", "attesa"),
        [
            (date(2026, 4, 27), True),  # ben oltre
            (date(2026, 4, 28), True),  # ESATTAMENTE al confine: scaduta
            (date(2026, 4, 29), False),  # il giorno dopo: non ancora
        ],
    )
    def test_il_confine_del_check_out_e_inclusivo(
        self, check_out: date, attesa: bool
    ) -> None:
        assert (
            scaduta(
                check_out=check_out,
                cessata_il=None,
                limite=_limite(date(2026, 4, 28)),
            )
            is attesa
        )

    def test_l_uscita_da_attiva_anticipa_la_decorrenza(self) -> None:
        # Una Prenotazione cancellata molto prima dell'arrivo: quel soggiorno
        # non avverrà, e la ragione per cui i contatti erano lì è finita
        # nell'istante della cancellazione. Aspettare il `check_out` +
        # novanta giorni significherebbe conservare dati personali di terzi
        # per un soggiorno che non c'è mai stato.
        assert scaduta(
            check_out=date(2027, 12, 31),
            cessata_il=datetime(2026, 4, 1, tzinfo=UTC),
            limite=_limite(date(2026, 4, 28)),
        )

    def test_l_uscita_da_attiva_DOPO_il_check_out_non_rimanda_nulla(self) -> None:
        # L'altra metà: «se precedente». Una Prenotazione conclusa e poi
        # archiviata ha già fatto decorrere il periodo dal `check_out`, e una
        # cessazione successiva non lo sposta in avanti — altrimenti bastasse
        # toccare lo stato per rinnovare la conservazione.
        assert scaduta(
            check_out=date(2026, 1, 10),
            cessata_il=datetime(2030, 1, 1, tzinfo=UTC),
            limite=_limite(date(2026, 4, 28)),
        )

    def test_una_prenotazione_futura_e_ancora_attiva_non_scade(self) -> None:
        assert not scaduta(
            check_out=date(2026, 12, 24),
            cessata_il=None,
            limite=_limite(date(2026, 4, 28)),
        )

    def test_la_cessazione_al_confine_e_inclusiva(self) -> None:
        limite = _limite(date(2026, 4, 28))
        assert scaduta(
            check_out=date(2030, 1, 1), cessata_il=limite.istante, limite=limite
        )
        assert not scaduta(
            check_out=date(2030, 1, 1),
            cessata_il=limite.istante + timedelta(microseconds=1),
            limite=limite,
        )


# Casi al confine, riusati sia dalla regola pura sia dal filtro SQL: sono la
# stessa domanda posta in due linguaggi, e devono rispondere uguale.
CASI = [
    (date(2026, 4, 27), None),
    (date(2026, 4, 28), None),
    (date(2026, 4, 29), None),
    (date(2030, 1, 1), None),
    (date(2030, 1, 1), datetime(2026, 4, 28, 11, 59, tzinfo=UTC)),
    (date(2030, 1, 1), datetime(2026, 4, 28, 12, 0, tzinfo=UTC)),
    (date(2030, 1, 1), datetime(2026, 4, 28, 12, 1, tzinfo=UTC)),
    (date(2026, 1, 1), datetime(2030, 1, 1, tzinfo=UTC)),
]


def test_la_regola_e_il_filtro_concordano(
    db_session: Session, contesto: Contesto
) -> None:
    """`scaduta` e `filtro_scadute` sono la stessa regola: devono coincidere.

    Il job non può filtrare in Python — leggerebbe l'intera tabella a ogni
    giro — quindi la regola esiste due volte. Questo test è il prezzo di
    quella scelta, e va pagato qui invece che novanta giorni dopo su dati
    che non tornano.
    """
    limite = _limite(date(2026, 4, 28))
    attese = {}
    for check_out, cessata_il in CASI:
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=check_out - timedelta(days=2),
            check_out=check_out,
            cessata_il=cessata_il,
        )
        attese[prenotazione.id] = scaduta(
            check_out=check_out, cessata_il=cessata_il, limite=limite
        )
    db_session.flush()

    dal_database = set(
        db_session.scalars(select(Prenotazione.id).where(filtro_scadute(limite)))
    )

    assert dal_database == {id_ for id_, attesa in attese.items() if attesa}
    # La guardia della guardia: se ogni caso cadesse dalla stessa parte, il
    # confronto passerebbe anche con due regole sbagliate allo stesso modo.
    assert 0 < len(dal_database) < len(attese)


class TestIlJob:
    """Integrazione: cosa succede DAVVERO alle righe."""

    def _scaduta_con_contatti(
        self, db_session: Session, contesto: Contesto
    ) -> tuple[Prenotazione, Ospite]:
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2020, 1, 1),
            check_out=date(2020, 1, 5),
            sommario="Testo opaco del portale",
        )
        ospite = registra_ospite(
            db_session,
            contesto,
            prenotazione,
            nome="Ospite Inventato",
            email="ospite.inventato@example.com",
            telefono="+39 000 0000000",
            principale=True,
        )
        db_session.commit()
        return prenotazione, ospite

    def test_azzera_i_campi_e_LASCIA_la_riga(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione, ospite = self._scaduta_con_contatti(db_session, contesto)

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        db_session.expire_all()

        rimasto = db_session.get(Ospite, ospite.id)
        assert rimasto is not None, (
            "l'azzeramento ha cancellato la riga: sarebbe una quarta "
            "cancellazione distruttiva, fuori dalla lista di AD-20"
        )
        assert (rimasto.nome, rimasto.email, rimasto.telefono) == (None, None, None)
        # Il legame e il ruolo restano: la storia della Prenotazione dice
        # ancora che c'era un Ospite, solo non più chi.
        assert rimasto.prenotazione_id == prenotazione.id
        assert rimasto.principale is True
        assert rimasto.anonimizzato_il is not None

    def test_la_prenotazione_e_la_sua_storia_restano_intatte(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        """La RIGA resta, con la sua storia: si azzerano i CAMPI (AD-20).

        L'asserzione sul `sommario` è cambiata di segno rispetto alla Story
        2.3, dove diceva che la retention dell'Ospite non lo toccava. Allora
        era vero e MYL-47 era una proposta aperta; ora AD-21 su `main` lo
        include nell'azzeramento, e questo test è il punto in cui il codice e
        l'invariante tornano a dire la stessa cosa.
        """
        prenotazione, _ = self._scaduta_con_contatti(db_session, contesto)

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        db_session.expire_all()

        sopravvissuta = db_session.get(Prenotazione, prenotazione.id)
        assert sopravvissuta is not None
        assert sopravvissuta.stato is StatoPrenotazione.ATTIVA
        assert sopravvissuta.check_in == date(2020, 1, 1)
        assert sopravvissuta.check_out == date(2020, 1, 5)
        # Il `SUMMARY` dei feed OTA contiene spesso il nome dell'Ospite:
        # azzerare l'anagrafica lasciandolo in vita vanificherebbe la
        # retention (AD-21, decisione MYL-47).
        assert sopravvissuta.sommario is None
        assert sopravvissuta.anonimizzato_il is not None

    def test_rieseguirlo_non_cambia_NULLA(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        """Idempotenza dimostrata, non dichiarata (AD-10).

        La consegna dei job è at-least-once: questo handler girerà due volte
        sullo stesso stato, e la seconda non deve né fallire né riscrivere
        l'evidenza — un `anonimizzato_il` che avanza a ogni giro sposterebbe
        la data dell'adempimento e la renderebbe inutile come prova.
        """
        _, ospite = self._scaduta_con_contatti(db_session, contesto)
        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        db_session.expire_all()
        prima = db_session.get(Ospite, ospite.id)
        assert prima is not None
        istantanea = (prima.anonimizzato_il, prima.aggiornato_il)

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        db_session.expire_all()

        dopo = db_session.get(Ospite, ospite.id)
        assert dopo is not None
        assert (dopo.anonimizzato_il, dopo.aggiornato_il) == istantanea

    def test_un_contatto_reinserito_DOPO_l_azzeramento_scade_di_nuovo(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        """La selezione chiede «c'è qualcosa da azzerare?», non «l'ho già fatto?».

        Dalla Story 2.4 l'Host può scrivere un contatto su un'anagrafica già
        azzerata. Filtrare su `anonimizzato_il IS NULL` sembrerebbe la
        condizione naturale — ed è il difetto: quel dato non scadrebbe mai
        più, cioè un dato personale conservato per sempre proprio sulla riga
        che il sistema aveva già dichiarato di aver ripulito.

        La mutazione che questo test esiste per cogliere non la vede il test
        di idempotenza: dopo l'azzeramento i tre campi sono `NULL`, quindi
        con o senza quella clausola il secondo giro tocca zero righe.
        """
        _, ospite = self._scaduta_con_contatti(db_session, contesto)
        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        db_session.expire_all()
        riaperto = db_session.get(Ospite, ospite.id)
        assert riaperto is not None
        riaperto.email = "reinserita@example.com"
        db_session.commit()

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        db_session.expire_all()

        richiuso = db_session.get(Ospite, ospite.id)
        assert richiuso is not None
        assert richiuso.email is None

    def test_non_tocca_un_anagrafica_ancora_nel_periodo(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=date.today() + timedelta(days=10),
            check_out=date.today() + timedelta(days=13),
        )
        ospite = registra_ospite(
            db_session, contesto, prenotazione, nome="Ospite Futuro", principale=True
        )
        db_session.commit()

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        db_session.expire_all()

        vivo = db_session.get(Ospite, ospite.id)
        assert vivo is not None
        assert vivo.nome == "Ospite Futuro"
        assert vivo.anonimizzato_il is None

    def test_non_marca_come_anonimizzata_un_anagrafica_senza_contatti(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Una riga senza contatti non ha nulla da azzerare: marcarla
        # `anonimizzato_il` sarebbe l'evidenza di un adempimento che non è
        # avvenuto, su dati che non sono mai esistiti. Ed è anche ciò che
        # rende il job idempotente per costruzione invece che per fortuna.
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2020, 1, 1),
            check_out=date(2020, 1, 5),
        )
        ospite = registra_ospite(db_session, contesto, prenotazione, principale=True)
        db_session.commit()

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        db_session.expire_all()

        muto = db_session.get(Ospite, ospite.id)
        assert muto is not None
        assert muto.anonimizzato_il is None

    def test_azzera_le_anagrafiche_di_TUTTI_gli_host(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # La query è deliberatamente non scopata per Host: è manutenzione del
        # worker, e scoparla significherebbe non adempiere per tutti gli
        # altri. Se qualcuno la «correggesse» aggiungendo un `host_id`, tutti
        # gli Host tranne uno resterebbero con i contatti scaduti.
        from tests.calendario import crea_contesto

        altro = crea_contesto(
            db_session, email="host.secondo@example.com", nome="Altra Struttura"
        )
        ospiti = []
        for chi in (contesto, altro):
            prenotazione = crea_prenotazione(
                db_session, chi, check_in=date(2020, 1, 1), check_out=date(2020, 1, 5)
            )
            ospiti.append(
                registra_ospite(
                    db_session, chi, prenotazione, email="chiunque@example.com"
                )
            )
        db_session.commit()

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        db_session.expire_all()

        for ospite in ospiti:
            riletto = db_session.get(Ospite, ospite.id)
            assert riletto is not None
            assert riletto.email is None

    def test_si_riprogramma_da_se(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        prossimo = db_session.scalars(
            select(Job).where(Job.job_type == TIPO_JOB_RETENTION_OSPITE)
        ).all()
        assert len(prossimo) == 1
        # Mai già scaduto: sarebbe preso nello stesso giro di worker che l'ha
        # creato e il ciclo girerebbe stretto.
        assert prossimo[0].due_at > datetime.now(UTC)

    def test_il_log_non_porta_dati_personali(
        self,
        db_session: Session,
        contesto: Contesto,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """NFR-11/AD-16: nei log solo conteggi e confini.

        Si assertisce sui `record`, non su `caplog.text`: gli attributi
        passati con `extra=` non finiscono nel testo reso, quindi un
        `not in caplog.text` passerebbe anche loggando il nome in chiaro.
        """
        self._scaduta_con_contatti(db_session, contesto)

        with caplog.at_level("INFO", logger="app.calendario.jobs"):
            azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        righe = [
            record
            for record in caplog.records
            if record.message.startswith("retention dell'anagrafica")
        ]
        assert len(righe) == 1
        riga = righe[0]
        assert riga.anagrafiche_azzerate == 1
        # Conteggi DISTINTI: un totale unico nasconderebbe il caso in cui uno
        # dei due adempimenti non è avvenuto.
        assert riga.sommari_azzerati == 1
        assert riga.decorrenza_entro_il
        emesso = " ".join(str(valore) for valore in vars(riga).values())
        assert "Ospite Inventato" not in emesso
        assert "ospite.inventato@example.com" not in emesso

    def test_il_tipo_di_job_e_a_catalogo_con_payload_vuoto(self) -> None:
        # AD-17: i tipi si dichiarano, e il payload non porta nulla — un
        # nome scritto nella coda `job` sopravviverebbe all'azzeramento che
        # il job stesso esegue.
        assert TIPO_JOB_RETENTION_OSPITE in catalog.job_names()
        assert catalog.job(TIPO_JOB_RETENTION_OSPITE).payload_keys == frozenset()
        catalog.validate_job_payload(TIPO_JOB_RETENTION_OSPITE, {})
        with pytest.raises(PayloadValidationError):
            catalog.validate_job_payload(
                TIPO_JOB_RETENTION_OSPITE, {"nome": "Chiunque"}
            )


class TestIlCicloNonSiSpegneDaSolo:
    """E2-F1: un errore nell'azzeramento non deve fermare la retention.

    Il modo di guasto è preciso e silenzioso: l'eccezione porta il job a
    `failed` al quinto tentativo, e da lì in coda non resta **nessun** job di
    retention — i dati personali restano oltre il termine a tempo
    indefinito, fino al prossimo riavvio del worker. Un `logger.error` e
    basta.

    **Perché il `try/finally` non sarebbe bastato.** L'handler gira dentro il
    SAVEPOINT per item di `run_due_jobs` (G-1): una riprogrammazione scritta
    in un `finally` verrebbe annullata insieme all'eccezione che la ha
    provocata, e la coda resterebbe vuota lo stesso. La prova è il secondo
    test di questa classe, che fa fallire l'`UPDATE` **nel database**: senza
    savepoint interno la transazione resta abortita e anche l'`INSERT` della
    riprogrammazione fallisce.
    """

    def _con_anagrafica_scaduta(self, db_session: Session, contesto: Contesto) -> None:
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2020, 1, 1),
            check_out=date(2020, 1, 5),
        )
        registra_ospite(
            db_session, contesto, prenotazione, nome="Ospite Inventato", principale=True
        )
        db_session.commit()

    def test_un_errore_PRIMA_dell_azzeramento_non_spegne_il_ciclo(
        self,
        db_session: Session,
        contesto: Contesto,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._con_anagrafica_scaduta(db_session, contesto)

        def esplode(_limite: object) -> object:
            raise RuntimeError("guasto simulato prima della UPDATE")

        monkeypatch.setattr("app.calendario.jobs.filtro_scadute", esplode)
        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        in_coda = db_session.scalars(
            select(Job).where(
                Job.job_type == TIPO_JOB_RETENTION_OSPITE,
                Job.status == JobStatus.PENDING,
            )
        ).all()
        assert len(in_coda) == 1, (
            "dopo un errore la coda è rimasta senza ciclo di retention: "
            "i dati personali resterebbero oltre il termine"
        )

    def test_un_errore_DEL_DATABASE_non_spegne_il_ciclo(
        self,
        db_session: Session,
        contesto: Contesto,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Il caso che il `finally` non copre: la UPDATE fallisce nel
        # database, la transazione resta abortita, e senza savepoint interno
        # anche l'INSERT della riprogrammazione fallirebbe — il rimedio
        # morirebbe dello stesso errore da cui deve proteggere.
        self._con_anagrafica_scaduta(db_session, contesto)
        monkeypatch.setattr(
            "app.calendario.jobs.filtro_scadute",
            lambda _limite: text("colonna_che_non_esiste > 1"),
        )

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        in_coda = db_session.scalars(
            select(Job).where(
                Job.job_type == TIPO_JOB_RETENTION_OSPITE,
                Job.status == JobStatus.PENDING,
            )
        ).all()
        assert len(in_coda) == 1

    def test_il_fallimento_e_VISIBILE_non_silenzioso(
        self,
        db_session: Session,
        contesto: Contesto,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Un adempimento non eseguito che non lascia traccia è
        # indistinguibile da uno eseguito su zero righe.
        self._con_anagrafica_scaduta(db_session, contesto)
        monkeypatch.setattr(
            "app.calendario.jobs.filtro_scadute",
            lambda _limite: text("colonna_che_non_esiste > 1"),
        )

        with caplog.at_level("ERROR", logger="app.calendario.jobs"):
            azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        messaggi = [record.message for record in caplog.records]
        assert any("non eseguita" in messaggio for messaggio in messaggi)

    def test_dopo_un_giro_fallito_il_giro_dopo_azzera_davvero(
        self,
        db_session: Session,
        contesto: Contesto,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # La prova che il ciclo non è solo «in coda» ma anche utile: il
        # guasto era transitorio, e l'adempimento si recupera da sé.
        self._con_anagrafica_scaduta(db_session, contesto)
        monkeypatch.setattr(
            "app.calendario.jobs.filtro_scadute",
            lambda _limite: text("colonna_che_non_esiste > 1"),
        )
        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        monkeypatch.undo()

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        db_session.expire_all()

        superstiti = db_session.scalars(select(Ospite)).all()
        assert [ospite.nome for ospite in superstiti] == [None]

    def test_il_worker_non_manda_il_job_a_failed_per_un_guasto_dell_azzeramento(
        self,
        db_session: Session,
        contesto: Contesto,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Il percorso reale, non l'handler chiamato a mano: `run_due_jobs`
        # esegue dentro il SAVEPOINT per item, ed è lì che il difetto
        # nasceva. Cinque giri di seguito e la coda deve restare viva.
        self._con_anagrafica_scaduta(db_session, contesto)
        assicura_retention_periodica(db_session)
        db_session.commit()
        monkeypatch.setattr(
            "app.calendario.jobs.filtro_scadute",
            lambda _limite: text("colonna_che_non_esiste > 1"),
        )

        for _ in range(5):
            prossimo = db_session.scalars(
                select(Job).where(
                    Job.job_type == TIPO_JOB_RETENTION_OSPITE,
                    Job.status == JobStatus.PENDING,
                )
            ).first()
            assert prossimo is not None, "il ciclo di retention si è spento"
            run_due_jobs(db_session, now=prossimo.due_at)
            db_session.commit()

        assert (
            db_session.scalars(
                select(Job).where(
                    Job.job_type == TIPO_JOB_RETENTION_OSPITE,
                    Job.status == JobStatus.FAILED,
                )
            ).all()
            == []
        )


class TestIParametriDiConfigurazione:
    """E2-F1, seconda metà: un parametro sbagliato ferma l'avvio.

    `retention.py` lo dichiarava e nessuno lo imponeva dove l'avvio lo
    incontra: `Settings` accettava `0` e il difetto si manifestava a regime,
    quando i contatti della Prenotazione in corso venivano azzerati.
    """

    @pytest.mark.parametrize(
        "parametro",
        ["ospite_retention_giorni", "ospite_retention_intervallo_minuti"],
    )
    @pytest.mark.parametrize("valore", [0, -1])
    def test_un_valore_non_positivo_non_costruisce_la_configurazione(
        self, parametro: str, valore: int
    ) -> None:
        from pydantic import ValidationError

        from app.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(**{parametro: valore})


class TestBootstrapDellaRetention:
    def test_accoda_il_ciclo_se_manca(self, db_session: Session) -> None:
        assicura_retention_periodica(db_session)
        db_session.commit()

        assert (
            db_session.scalars(
                select(Job).where(Job.job_type == TIPO_JOB_RETENTION_OSPITE)
            ).all()
            != []
        )

    def test_non_ne_accoda_un_secondo(self, db_session: Session) -> None:
        # Un bootstrap non idempotente moltiplica il ciclo a ogni riavvio del
        # worker, e la coda cresce per sempre.
        assicura_retention_periodica(db_session)
        db_session.commit()
        assicura_retention_periodica(db_session)
        db_session.commit()

        in_coda = db_session.scalars(
            select(Job).where(
                Job.job_type == TIPO_JOB_RETENTION_OSPITE,
                Job.status == JobStatus.PENDING,
            )
        ).all()
        assert len(in_coda) == 1
