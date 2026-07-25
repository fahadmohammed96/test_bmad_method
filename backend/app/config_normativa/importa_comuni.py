"""Import dell'anagrafica Comuni dal file ufficiale ISTAT (AD-9).

Operazione DATI, non un rilascio: si esegue quando ISTAT pubblica un
aggiornamento dell'elenco (fusioni, nuove denominazioni).

    uv run --no-sync python -m app.config_normativa.importa_comuni <file.csv>

Il CSV atteso è quello pubblicato da ISTAT ("Codici statistici delle
unità amministrative territoriali"), separatore `;`, con le colonne:
`Codice Comune formato alfanumerico`, `Denominazione in italiano`,
`Sigla automobilistica`, `Codice Regione`.
"""

import csv
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_normativa.models import Comune
from app.core.db import get_sessionmaker

COLONNA_CODICE = "Codice Comune formato alfanumerico"
COLONNA_NOME = "Denominazione in italiano"
COLONNA_PROVINCIA = "Sigla automobilistica"
COLONNA_REGIONE = "Codice Regione"


def percorso_validato(argomento: str, base: Path | None = None) -> Path:
    """Valida il percorso ricevuto da riga di comando prima di aprirlo.

    Il file deve essere un CSV regolare, esistente e contenuto nella
    directory di lavoro (o in quella indicata): un argomento malformato
    non può portare a leggere file fuori dal perimetro previsto.
    """
    radice = (base or Path.cwd()).resolve()
    try:
        percorso = Path(argomento).resolve(strict=True)
    except OSError as errore:
        raise ValueError(f"file non accessibile: {argomento}") from errore
    if not percorso.is_relative_to(radice):
        raise ValueError(f"il file deve trovarsi sotto {radice}: {percorso}")
    if not percorso.is_file():
        raise ValueError(f"non è un file regolare: {percorso}")
    if percorso.suffix.lower() != ".csv":
        raise ValueError(f"formato atteso .csv: {percorso.name}")
    return percorso


def importa(db: Session, percorso: Path) -> int:
    """Upsert idempotente dell'anagrafica: rieseguire non duplica."""
    esistenti = {c.codice_istat: c for c in db.scalars(select(Comune))}
    with percorso.open(encoding="utf-8-sig", newline="") as sorgente:
        righe = list(csv.DictReader(sorgente, delimiter=";"))

    for riga in righe:
        codice = riga[COLONNA_CODICE].strip()
        regione = riga[COLONNA_REGIONE].strip().zfill(2)
        comune = esistenti.get(codice)
        if comune is None:
            comune = Comune(codice_istat=codice)
            db.add(comune)
        comune.nome = riga[COLONNA_NOME].strip()
        comune.provincia = riga[COLONNA_PROVINCIA].strip()
        comune.regione_codice_istat = regione
    db.commit()
    return len(righe)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "uso: python -m app.config_normativa.importa_comuni <file.csv>"
        )
    try:
        percorso = percorso_validato(sys.argv[1])
    except ValueError as errore:
        raise SystemExit(str(errore)) from errore
    with get_sessionmaker()() as db:
        totale = importa(db, percorso)
    print(f"Anagrafica Comuni aggiornata: {totale} righe da {percorso}")


if __name__ == "__main__":
    main()
