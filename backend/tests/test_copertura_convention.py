"""Guardia sulla misura della copertura — chiude MYL-59.

MYL-59 diceva: ogni consegna di questo progetto cita «SonarCloud Quality Gate
verde» come parte dell'evidenza, e su ogni PR quel gate riportava
`0.0% Coverage on New Code` **passando**. Il numero non descriveva una
copertura bassa: descriveva il fatto che a SonarCloud non arriva mai un report.
Misurato il 30/07 via API di SonarCloud, le condizioni che quel gate valuta
sono cinque — `new_reliability_rating`, `new_security_rating`,
`new_maintainability_rating`, `new_duplicated_lines_density`,
`new_security_hotspots_reviewed` — e **nessuna riguarda la copertura**. La
copertura reale, misurata lo stesso giorno, era 96.44% sul backend e 73.93% sul
frontend: la disciplina c'era, la misura no.

Perché una guardia e non solo la configurazione: un difetto di ASSENZA non
produce alcuna riga rossa. La configurazione della copertura sta in tre punti
diversi — `pyproject.toml`, `frontend/vitest.config.ts` e il workflow — e
toglierne uno non rompe nulla di visibile: la CI resta verde, i report smettono
di esistere o smettono di essere confrontati, e la squadra continua a citare un
gate che non misura più niente. È esattamente il modo in cui MYL-59 è nato ed è
sopravvissuto per settimane. Questo test è il costo di non rifarlo.

Le forme di silenzio che sorveglia, tutte riprodotte a mano il 30/07:

1. `--cov` che sparisce dallo step di test → nessun `coverage.xml`, e il job
   `copertura` non ha niente da confrontare.
2. Il pavimento globale usato come se fosse il cancello → togliendo
   `tests/test_calendario_sync.py` intero (81 test) il totale scende da 96.44%
   a 95.16%, cioè un pavimento a 93 **non se ne accorge**.
3. La normalizzazione dei percorsi lcov che sparisce → `diff-cover` stampa
   «No lines with coverage information in this diff» ed **esce 0** su una PR
   con un file TS nuovo e interamente scoperto: il cancello passa a vuoto.
4. `all: true` che sparisce da vitest → un componente che nessun test importa
   esce dalla misura invece di abbassarla.
5. `omit` che si popola in `[tool.coverage.run]` → il modo più rapido di
   alzare il numero senza scrivere un test.
"""

import pathlib
import tomllib

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
RADICE = BACKEND.parent
PYPROJECT = BACKEND / "pyproject.toml"
WORKFLOW = RADICE / ".github" / "workflows" / "ci.yml"
VITEST_CONFIG = RADICE / "frontend" / "vitest.config.ts"
PACKAGE_JSON = RADICE / "frontend" / "package.json"
GITIGNORE = RADICE / ".gitignore"

# Il pavimento globale non è il cancello, ma sotto questo valore non è più
# nemmeno un backstop: la misura reale al 30/07 era 96.44%.
PAVIMENTO_MINIMO_BACKEND = 90


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def vitest_config() -> str:
    return VITEST_CONFIG.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. La misura viene prodotta
# --------------------------------------------------------------------------


def test_lo_step_di_test_del_backend_chiede_la_copertura(workflow: str) -> None:
    assert "pytest --cov --cov-report=xml" in workflow, (
        "lo step di test del backend non chiede più `--cov --cov-report=xml`: "
        "senza `coverage.xml` il job `copertura` non ha nulla da confrontare e "
        "la CI resta verde senza misurare niente (MYL-59)"
    )


def test_lo_step_di_test_del_frontend_chiede_la_copertura(workflow: str) -> None:
    assert "npm run test:coverage" in workflow, (
        "lo step di test del frontend è tornato a `npm test`: senza "
        "`lcov.info` la metà frontend del cancello non esiste"
    )


def test_lo_script_di_copertura_del_frontend_esiste() -> None:
    import json

    script = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["scripts"]
    assert "test:coverage" in script, (
        "`test:coverage` è sparito da package.json: il workflow lo invoca e "
        "fallirebbe, ma la ragione sarebbe illeggibile"
    )
    assert "--coverage" in script["test:coverage"]


def test_i_report_di_copertura_non_sono_committabili() -> None:
    ignorati = GITIGNORE.read_text(encoding="utf-8")
    for voce in (".coverage", "coverage.xml", "coverage/"):
        assert voce in ignorati, (
            f"`{voce}` non è in .gitignore: un report committato resta indietro "
            "senza dirlo, e chi lo legge crede di guardare la misura di adesso"
        )


# --------------------------------------------------------------------------
# 2. La misura è onesta
# --------------------------------------------------------------------------


def test_la_copertura_del_backend_misura_tutto_app(pyproject: dict) -> None:
    run = pyproject["tool"]["coverage"]["run"]
    assert run["source"] == ["app"]
    assert run["branch"] is True, (
        "`branch = false` conta come coperto un `if` di cui si esercita un solo "
        "ramo: è il primo sconto che rende il numero più alto della realtà"
    )
    assert run["omit"] == [], (
        "`omit` non è più vuoto. Togliere un modulo dalla misura è il modo più "
        "rapido di alzare la copertura senza scrivere un test, e non lascia "
        "nessuna riga rossa: se un modulo va davvero escluso, la decisione è "
        "di chi rivede la PR, non di questa lista"
    )


def test_il_pavimento_globale_del_backend_esiste_e_non_e_stato_abbassato(
    pyproject: dict,
) -> None:
    fail_under = pyproject["tool"]["coverage"]["report"]["fail_under"]
    assert fail_under >= PAVIMENTO_MINIMO_BACKEND, (
        f"`fail_under` è scesa a {fail_under}: sotto "
        f"{PAVIMENTO_MINIMO_BACKEND} non è più un backstop, e la misura reale "
        "al 30/07 era 96.44%"
    )


def test_il_frontend_conta_i_file_che_nessun_test_importa(
    vitest_config: str,
) -> None:
    assert "all: true" in vitest_config, (
        "`all: true` è sparito dalla copertura vitest: un componente che "
        "nessun test importa SPARISCE dalla misura invece di abbassarla — il "
        "modo più silenzioso di avere una copertura finta"
    )
    assert 'provider: "v8"' in vitest_config
    assert '"lcovonly"' in vitest_config, (
        "il reporter `lcovonly` è sparito: è il formato che legge `diff-cover`, "
        "senza il quale la metà frontend del cancello non ha input"
    )
    assert "thresholds:" in vitest_config


# --------------------------------------------------------------------------
# 3. La misura morde — ed è il punto
# --------------------------------------------------------------------------


def test_il_cancello_sulla_copertura_del_diff_esiste(workflow: str) -> None:
    assert "diff-cover" in workflow, (
        "`diff-cover` è sparito dal workflow. Restano i pavimenti globali, che "
        "NON bastano: misurato il 30/07, togliere `test_calendario_sync.py` "
        "intero (81 test) porta il totale da 96.44% a 95.16% e un pavimento a "
        "93 non se ne accorge. Sulle righe nuove nessun altro test le copre "
        "per sbaglio: è lì che il cancello morde"
    )
    assert "--fail-under" in workflow, (
        "`diff-cover` gira senza `--fail-under`: stampa un numero ed esce 0, "
        "cioè è un report travestito da cancello"
    )


def test_diff_cover_riceve_percorsi_che_combaciano_col_diff(workflow: str) -> None:
    # `SF:` di lcov è relativo a `frontend/`, `git diff` parla in percorsi
    # relativi alla radice. Senza la normalizzazione i due insiemi non si
    # intersecano, `diff-cover` non trova righe misurabili ed esce 0 —
    # riprodotto il 30/07 su un file TS nuovo e interamente scoperto: passava.
    assert "s|^SF:|SF:frontend/|" in workflow, (
        "la normalizzazione dei percorsi lcov è sparita: `diff-cover` "
        "stamperebbe «No lines with coverage information in this diff» ed "
        "uscirebbe 0 su qualunque PR del frontend. Un cancello che passa a "
        "vuoto è peggio di un cancello assente, perché viene citato come "
        "evidenza"
    )


def test_esiste_la_guardia_contro_il_passaggio_a_vuoto(workflow: str) -> None:
    assert "No lines with coverage information" in workflow, (
        "è sparito il controllo che distingue «la PR non tocca codice "
        "misurato» da «il report non conosce il codice che la PR tocca». "
        "`diff-cover` esce 0 in entrambi i casi, e solo il secondo è un guasto"
    )


def test_le_soglie_del_diff_sono_dichiarate_nel_workflow(workflow: str) -> None:
    for chiave in ("SOGLIA_BACKEND", "SOGLIA_FRONTEND"):
        assert chiave in workflow, (
            f"`{chiave}` non è più dichiarata: le due soglie sono diverse per "
            "una ragione misurata (la copertura degli e2e Playwright non viene "
            "raccolta, quindi il frontend parte da 73.93%), e una soglia "
            "unica le renderebbe entrambe sbagliate"
        )


def test_il_cancello_gira_solo_sulle_pull_request(workflow: str) -> None:
    # Su un push a `main` non esiste un diff da sorvegliare: il job passerebbe
    # a vuoto e sarebbe indistinguibile da un job che ha misurato qualcosa.
    assert "if: github.event_name == 'pull_request'" in workflow
