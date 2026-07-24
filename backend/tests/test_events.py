"""Test del catalogo unico eventi/job (AD-17).

Nomi `<entita>.<fatto_passato>`, payload con soli identificatori e il fatto,
catalogo versionato con registrazione esplicita.
"""

import uuid

import pytest

from app.core.events import (
    CATALOG_VERSION,
    Catalog,
    DuplicateTypeError,
    InvalidTypeNameError,
    PayloadValidationError,
    UnknownTypeError,
    catalog,
)


@pytest.fixture
def local_catalog() -> Catalog:
    return Catalog()


class TestEventRegistration:
    def test_registra_e_risolve_un_tipo_evento(self, local_catalog: Catalog) -> None:
        local_catalog.register_event(
            "struttura.archiviata", payload_keys=("struttura_id", "host_id")
        )
        tipo = local_catalog.event("struttura.archiviata")
        assert tipo.name == "struttura.archiviata"
        assert tipo.payload_keys == frozenset({"struttura_id", "host_id"})

    def test_nome_senza_fatto_passato_rifiutato(self, local_catalog: Catalog) -> None:
        with pytest.raises(InvalidTypeNameError):
            local_catalog.register_event("struttura", payload_keys=("id",))

    def test_nome_non_snake_case_rifiutato(self, local_catalog: Catalog) -> None:
        with pytest.raises(InvalidTypeNameError):
            local_catalog.register_event("Struttura.Creata", payload_keys=("id",))

    def test_doppia_registrazione_rifiutata(self, local_catalog: Catalog) -> None:
        local_catalog.register_event("struttura.creata", payload_keys=("struttura_id",))
        with pytest.raises(DuplicateTypeError):
            local_catalog.register_event(
                "struttura.creata", payload_keys=("struttura_id",)
            )

    def test_tipo_sconosciuto_solleva_errore(self, local_catalog: Catalog) -> None:
        with pytest.raises(UnknownTypeError):
            local_catalog.event("prenotazione.inventata")


class TestJobRegistration:
    def test_registra_e_risolve_un_tipo_job(self, local_catalog: Catalog) -> None:
        local_catalog.register_job("sync.tick", payload_keys=("feed_id",))
        assert local_catalog.job("sync.tick").name == "sync.tick"

    def test_job_sconosciuto_solleva_errore(self, local_catalog: Catalog) -> None:
        with pytest.raises(UnknownTypeError):
            local_catalog.job("job.inventato")


class TestPayloadValidation:
    """Il payload porta SOLO identificatori e il fatto, mai snapshot di stato."""

    @pytest.fixture
    def catalogo_con_evento(self, local_catalog: Catalog) -> Catalog:
        local_catalog.register_event(
            "struttura.creata", payload_keys=("struttura_id", "host_id")
        )
        return local_catalog

    def test_payload_valido(self, catalogo_con_evento: Catalog) -> None:
        catalogo_con_evento.validate_event_payload(
            "struttura.creata",
            {"struttura_id": str(uuid.uuid4()), "host_id": str(uuid.uuid4())},
        )

    def test_chiave_mancante_rifiutata(self, catalogo_con_evento: Catalog) -> None:
        with pytest.raises(PayloadValidationError):
            catalogo_con_evento.validate_event_payload(
                "struttura.creata", {"struttura_id": "x"}
            )

    def test_chiave_extra_rifiutata(self, catalogo_con_evento: Catalog) -> None:
        with pytest.raises(PayloadValidationError):
            catalogo_con_evento.validate_event_payload(
                "struttura.creata",
                {"struttura_id": "x", "host_id": "y", "stato": "attiva"},
            )

    def test_snapshot_annidato_rifiutato(self, catalogo_con_evento: Catalog) -> None:
        # Un dict annidato è uno snapshot di stato, non un identificatore.
        with pytest.raises(PayloadValidationError):
            catalogo_con_evento.validate_event_payload(
                "struttura.creata",
                {"struttura_id": "x", "host_id": {"nome": "Mario"}},
            )


class TestProductionCatalog:
    def test_il_catalogo_e_versionato(self) -> None:
        assert isinstance(CATALOG_VERSION, int)
        assert CATALOG_VERSION >= 1

    def test_ogni_nome_registrato_rispetta_la_convenzione(self) -> None:
        for name in catalog.event_names():
            entita, _, fatto = name.partition(".")
            assert entita and fatto, name
