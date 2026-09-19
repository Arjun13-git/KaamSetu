import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app import __version__
from app.api.deps import RequestContextDep
from app.core.config import Settings
from app.core.errors import ConflictError, InvalidStateTransitionError
from app.main import create_app

router = APIRouter()


class _Body(BaseModel):
    count: int


@router.get("/whoami")
def whoami(ctx: RequestContextDep) -> dict[str, str]:
    return {
        "business_id": ctx.business_id,
        "actor_id": ctx.actor_id,
        "request_id": ctx.request_id,
    }


@router.get("/conflict")
def conflict() -> None:
    raise ConflictError("Already exists", details={"field": "phone"})


@router.get("/illegal")
def illegal() -> None:
    raise InvalidStateTransitionError("A COMPLETED job cannot move to IN_PROGRESS")


@router.get("/boom")
def boom() -> None:
    raise RuntimeError("secret-internal-detail: table kaamsetu-prod at 10.0.0.5")


@router.post("/validate")
def validate(body: _Body) -> dict[str, int]:
    return {"count": body.count}


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"app_env": "test", "data_provider": "memory", "_env_file": None}
    return Settings(**{**values, **overrides})  # type: ignore[arg-type]


@pytest.fixture
def app() -> FastAPI:
    application = create_app(_settings())
    application.include_router(router, prefix="/api/v1/_test")
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestHealth:
    def test_health_is_wrapped_in_the_success_envelope(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["data"] == {"status": "ok", "version": __version__}
        assert body["request_id"].startswith("req_")
        assert response.headers["X-Request-Id"] == body["request_id"]

    def test_a_well_formed_request_id_is_honoured(self, client: TestClient) -> None:
        response = client.get("/api/v1/health", headers={"X-Request-Id": "req_from_caller_1"})

        assert response.json()["request_id"] == "req_from_caller_1"

    @pytest.mark.parametrize("supplied", ["not-a-request-id", "req_bad id", "req_" + "x" * 200])
    def test_a_malformed_request_id_is_replaced(self, client: TestClient, supplied: str) -> None:
        response = client.get("/api/v1/health", headers={"X-Request-Id": supplied})

        request_id = response.json()["request_id"]
        assert request_id != supplied and request_id.startswith("req_")


class TestErrorEnvelope:
    def test_unknown_route_is_a_structured_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/nothing-here")

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "NOT_FOUND"
        assert body["request_id"] == response.headers["X-Request-Id"]

    def test_domain_errors_map_to_their_code_status_and_details(self, client: TestClient) -> None:
        conflict = client.get("/api/v1/_test/conflict")
        illegal = client.get("/api/v1/_test/illegal")

        assert conflict.status_code == 409
        assert conflict.json()["error"] == {
            "code": "CONFLICT",
            "message": "Already exists",
            "details": {"field": "phone"},
        }
        assert illegal.status_code == 409
        assert illegal.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    def test_validation_errors_do_not_echo_submitted_values(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/_test/validate", json={"count": "customer-phone-9876543210"}
        )

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert error["details"]["fields"][0]["loc"] == ["body", "count"]
        assert "9876543210" not in response.text

    def test_unexpected_errors_reveal_nothing_internal(self, client: TestClient) -> None:
        response = client.get("/api/v1/_test/boom")

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "secret-internal-detail" not in response.text
        assert "kaamsetu-prod" not in response.text
        assert "Traceback" not in response.text
        assert response.headers["X-Request-Id"] == response.json()["request_id"]


class TestActor:
    def test_development_actor_comes_from_server_configuration(self) -> None:
        settings = _settings(dev_business_id="bus_configured", dev_actor_id="usr_configured")
        application = create_app(settings)
        application.include_router(router, prefix="/api/v1/_test")

        body = TestClient(application).get("/api/v1/_test/whoami").json()

        assert body["business_id"] == "bus_configured"
        assert body["actor_id"] == "usr_configured"

    def test_client_supplied_tenant_hints_are_ignored(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/_test/whoami?business_id=bus_evil&actor_id=usr_evil",
            headers={
                "X-Business-Id": "bus_evil",
                "X-Tenant-Id": "bus_evil",
                "X-Actor-Id": "usr_evil",
            },
        )

        assert response.json()["business_id"] == "bus_demo"
        assert response.json()["actor_id"] == "usr_dev"

    def test_production_refuses_the_development_actor(self) -> None:
        settings = _settings(
            app_env="production", data_provider="dynamodb", aws_region="ap-south-1"
        )
        application = create_app(settings)
        application.include_router(router, prefix="/api/v1/_test")

        response = TestClient(application).get(
            "/api/v1/_test/whoami", headers={"X-Business-Id": "bus_demo"}
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_api_docs_are_not_exposed_in_production() -> None:
    settings = _settings(app_env="production", data_provider="dynamodb", aws_region="ap-south-1")

    client = TestClient(create_app(settings))

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert TestClient(create_app(_settings())).get("/openapi.json").status_code == 200
