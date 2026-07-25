"""Repository di `config_normativa`.

Anagrafica e configurazione sono dati di RIFERIMENTO condivisi, non
tenant-owned: qui non c'è `host_id` (vedi allowlist esplicita in
tests/test_tenancy_convention.py). Lo scoping per Host avviene nel
modulo `strutture`, che possiede il legame Struttura → Comune/Regione.
"""

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config_normativa.models import (
    Comune,
    ComuneConfig,
    ParametroFiscale,
    Regione,
    RegioneConfig,
)


class AnagraficaRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def regioni(self) -> list[Regione]:
        return list(self._db.scalars(select(Regione).order_by(Regione.nome)))

    def regione_by_codice(self, codice_istat: str) -> Regione | None:
        return self._db.get(Regione, codice_istat)

    def regione_by_nome(self, nome: str) -> Regione | None:
        return self._db.scalars(
            select(Regione).where(Regione.nome.ilike(nome.strip()))
        ).first()

    def comune_by_codice(self, codice_istat: str) -> Comune | None:
        return self._db.get(Comune, codice_istat)

    def cerca_comuni(self, ricerca: str, limite: int = 20) -> list[Comune]:
        return list(
            self._db.scalars(
                select(Comune)
                .where(Comune.nome.ilike(f"{ricerca.strip()}%"))
                .order_by(Comune.nome)
                .limit(limite)
            )
        )


class ConfigRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _vigente(colonna_dal, colonna_al, alla_data: date):
        return (
            colonna_dal <= alla_data,
            or_(colonna_al.is_(None), colonna_al >= alla_data),
        )

    def comune_config_vigente(
        self, comune_codice_istat: str, alla_data: date
    ) -> ComuneConfig | None:
        return self._db.scalars(
            select(ComuneConfig)
            .where(
                ComuneConfig.comune_codice_istat == comune_codice_istat,
                *self._vigente(
                    ComuneConfig.valido_dal, ComuneConfig.valido_al, alla_data
                ),
            )
            # A parità di decorrenza vale l'ULTIMA emessa: senza questo
            # tiebreaker l'esito dipenderebbe dall'ordine di Postgres.
            .order_by(ComuneConfig.valido_dal.desc(), ComuneConfig.creato_il.desc())
        ).first()

    def regione_config_vigente(
        self, regione_codice_istat: str, alla_data: date
    ) -> RegioneConfig | None:
        return self._db.scalars(
            select(RegioneConfig)
            .where(
                RegioneConfig.regione_codice_istat == regione_codice_istat,
                *self._vigente(
                    RegioneConfig.valido_dal, RegioneConfig.valido_al, alla_data
                ),
            )
            .order_by(RegioneConfig.valido_dal.desc(), RegioneConfig.creato_il.desc())
        ).first()

    def parametro_fiscale_vigente(self, alla_data: date) -> ParametroFiscale | None:
        return self._db.scalars(
            select(ParametroFiscale)
            .where(
                *self._vigente(
                    ParametroFiscale.valido_dal, ParametroFiscale.valido_al, alla_data
                )
            )
            .order_by(
                ParametroFiscale.valido_dal.desc(), ParametroFiscale.creato_il.desc()
            )
        ).first()

    def parametri_fiscali_aperti_dal(self, valido_dal: date) -> list[ParametroFiscale]:
        return list(
            self._db.scalars(
                select(ParametroFiscale).where(
                    ParametroFiscale.valido_dal <= valido_dal,
                    ParametroFiscale.valido_al.is_(None),
                )
            )
        )

    def comune_config_aperte_dal(
        self, comune_codice_istat: str, valido_dal: date
    ) -> list[ComuneConfig]:
        """Configurazioni ancora aperte che una nuova delibera va a chiudere.

        Include quelle di PARI decorrenza (delibera ri-emessa per
        correzione): altrimenti resterebbero due periodi aperti con la
        stessa data e la risoluzione non sarebbe deterministica.
        """
        return list(
            self._db.scalars(
                select(ComuneConfig).where(
                    ComuneConfig.comune_codice_istat == comune_codice_istat,
                    ComuneConfig.valido_dal <= valido_dal,
                    ComuneConfig.valido_al.is_(None),
                )
            )
        )

    def regione_config_aperte_dal(
        self, regione_codice_istat: str, valido_dal: date
    ) -> list[RegioneConfig]:
        return list(
            self._db.scalars(
                select(RegioneConfig).where(
                    RegioneConfig.regione_codice_istat == regione_codice_istat,
                    RegioneConfig.valido_dal <= valido_dal,
                    RegioneConfig.valido_al.is_(None),
                )
            )
        )
