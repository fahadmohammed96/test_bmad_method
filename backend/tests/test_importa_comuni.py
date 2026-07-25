"""Test dell'import dell'anagrafica Comuni dal file ISTAT (AD-9).

L'import è un'operazione dati eseguita da riga di comando: il percorso
ricevuto va validato prima di toccare il filesystem.
"""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_normativa.importa_comuni import importa, percorso_validato
from app.config_normativa.models import Comune

INTESTAZIONE = (
    "Codice Comune formato alfanumerico;Denominazione in italiano;"
    "Sigla automobilistica;Codice Regione"
)


def _scrivi_csv(cartella: Path, righe: list[str], nome: str = "comuni.csv") -> Path:
    percorso = cartella / nome
    percorso.write_text("\n".join([INTESTAZIONE, *righe]) + "\n", encoding="utf-8-sig")
    return percorso


class TestPercorsoValidato:
    def test_accetta_un_csv_regolare_nel_perimetro(self, tmp_path: Path) -> None:
        percorso = _scrivi_csv(tmp_path, [])
        assert percorso_validato(str(percorso), base=tmp_path) == percorso.resolve()

    def test_rifiuta_un_file_fuori_dal_perimetro(self, tmp_path: Path) -> None:
        fuori = tmp_path / "fuori"
        fuori.mkdir()
        percorso = _scrivi_csv(fuori, [])
        dentro = tmp_path / "dentro"
        dentro.mkdir()
        with pytest.raises(ValueError, match="deve trovarsi sotto"):
            percorso_validato(str(percorso), base=dentro)

    def test_rifiuta_traversal_con_dot_dot(self, tmp_path: Path) -> None:
        _scrivi_csv(tmp_path, [], nome="segreti.csv")
        dentro = tmp_path / "dentro"
        dentro.mkdir()
        with pytest.raises(ValueError):
            percorso_validato(str(dentro / ".." / "segreti.csv"), base=dentro)

    def test_rifiuta_un_file_inesistente(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="non accessibile"):
            percorso_validato(str(tmp_path / "manca.csv"), base=tmp_path)

    def test_rifiuta_un_formato_diverso_da_csv(self, tmp_path: Path) -> None:
        altro = tmp_path / "anagrafica.txt"
        altro.write_text("niente", encoding="utf-8")
        with pytest.raises(ValueError, match="formato atteso"):
            percorso_validato(str(altro), base=tmp_path)


class TestImport:
    def test_importa_e_normalizza_il_codice_regione(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        percorso = _scrivi_csv(tmp_path, ["T00009;Testopoli;TS;8"])
        assert importa(db_session, percorso) == 1

        comune = db_session.scalars(select(Comune)).one()
        assert comune.codice_istat == "T00009"
        assert comune.nome == "Testopoli"
        assert comune.regione_codice_istat == "08"  # zero-padding ISTAT

    def test_rieseguire_l_import_non_duplica(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        percorso = _scrivi_csv(tmp_path, ["T00009;Testopoli;TS;08"])
        importa(db_session, percorso)
        aggiornato = _scrivi_csv(
            tmp_path, ["T00009;Testopoli Nuova;TS;08"], nome="comuni2.csv"
        )
        importa(db_session, aggiornato)

        comuni = db_session.scalars(select(Comune)).all()
        assert len(comuni) == 1  # upsert, non insert
        assert comuni[0].nome == "Testopoli Nuova"
