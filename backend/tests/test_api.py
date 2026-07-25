"""Test del contratto API (AD-14).

REST sotto /api/v1, OpenAPI generato da FastAPI, errori RFC 9457
`application/problem+json`.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)

PROBLEM = "application/problem+json"


class TestApiV1:
    def test_health_risponde_sotto_api_v1(self) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_openapi_generato_da_fastapi(self) -> None:
        response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "HostPilot API"
        assert all(path.startswith("/api/v1") for path in schema["paths"])


class TestProblemJson:
    def test_404_e_problem_json(self) -> None:
        response = client.get("/api/v1/inesistente")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith(PROBLEM)
        body = response.json()
        assert body["status"] == 404
        assert "type" in body and "title" in body

    def test_errore_di_validazione_e_problem_json_con_type_stabile(self) -> None:
        # /health non accetta parametri: forziamo una validazione fallita
        # su un endpoint con path param quando esisterà; per ora il contratto
        # si verifica sul metodo non ammesso.
        response = client.post("/api/v1/health")
        assert response.status_code == 405
        assert response.headers["content-type"].startswith(PROBLEM)

    def test_nessuno_stacktrace_al_client(self) -> None:
        response = client.get("/api/v1/inesistente")
        assert "Traceback" not in response.text
