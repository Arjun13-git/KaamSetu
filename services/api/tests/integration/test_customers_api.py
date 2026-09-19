"""The walking-skeleton API path (create/get customer) against every persistence adapter, plus the
demo authentication mode that fronts it when deployed."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.enums import AuditAction, AuditEntityType
from app.domain.repositories import Repositories
from app.main import create_app
from tests.factories import NOW, OTHER_BUSINESS_ID, make_customer

TENANT = "bus_demo"
DEMO_KEY = "test-only-demo-key-0123456789abcdef-0123456789"
NEW_CUSTOMER = {"name": "Asha Rao", "phone": "98765 43210", "address": "12 MG Road, Bengaluru"}


def _dev_settings() -> Settings:
    return Settings(app_env="test", data_provider="memory", _env_file=None)  # type: ignore[call-arg]


def _demo_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "demo",
        "data_provider": "dynamodb",
        "aws_region": "us-east-1",
        "demo_api_key": DEMO_KEY,
        "_env_file": None,
    }
    return Settings(**{**values, **overrides})  # type: ignore[arg-type]


@pytest.fixture
def client(repos: Repositories) -> TestClient:
    return TestClient(create_app(_dev_settings(), repositories=repos, clock=lambda: NOW))


@pytest.fixture
def demo_client(repos: Repositories) -> TestClient:
    return TestClient(create_app(_demo_settings(), repositories=repos, clock=lambda: NOW))


class TestCustomers:
    def test_create_returns_the_customer_in_the_success_envelope(self, client: TestClient) -> None:
        response = client.post("/api/v1/customers", json=NEW_CUSTOMER)

        assert response.status_code == 201
        body = response.json()
        assert body["request_id"] == response.headers["X-Request-Id"]
        data = body["data"]
        assert data["customer_id"].startswith("cus_")
        assert data["name"] == "Asha Rao"
        assert data["phone"] == "+919876543210"
        assert data["created_at"].startswith("2026-09-19T10:00:00")
        assert "business_id" not in data

    def test_create_persists_under_the_actors_business_with_an_audit_record(
        self, client: TestClient, repos: Repositories
    ) -> None:
        response = client.post("/api/v1/customers", json=NEW_CUSTOMER)
        customer_id = response.json()["data"]["customer_id"]

        stored = repos.customers.get(TENANT, customer_id)
        assert stored.name == "Asha Rao" and stored.business_id == TENANT
        (audit,) = repos.audits.list_for_entity(TENANT, AuditEntityType.CUSTOMER, customer_id)
        assert audit.action is AuditAction.CUSTOMER_CREATED
        assert audit.actor_id == "usr_dev"
        assert audit.request_id == response.json()["request_id"]

    def test_get_returns_what_was_created(self, client: TestClient) -> None:
        created = client.post("/api/v1/customers", json=NEW_CUSTOMER).json()["data"]

        fetched = client.get(f"/api/v1/customers/{created['customer_id']}")

        assert fetched.status_code == 200
        assert fetched.json()["data"] == created

    def test_unknown_customer_is_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/customers/cus_doesnotexist")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_another_businesss_customer_is_indistinguishable_from_missing(
        self, client: TestClient, repos: Repositories
    ) -> None:
        foreign = make_customer(business_id=OTHER_BUSINESS_ID)
        repos.customers.create(foreign)

        response = client.get(f"/api/v1/customers/{foreign.customer_id}")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_a_body_naming_a_business_is_rejected_and_writes_nothing(
        self, client: TestClient, repos: Repositories
    ) -> None:
        response = client.post(
            "/api/v1/customers", json={**NEW_CUSTOMER, "business_id": OTHER_BUSINESS_ID}
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert repos.customers.list(OTHER_BUSINESS_ID) == []
        assert repos.customers.list(TENANT) == []

    def test_tenant_headers_and_query_hints_are_ignored(
        self, client: TestClient, repos: Repositories
    ) -> None:
        response = client.post(
            f"/api/v1/customers?business_id={OTHER_BUSINESS_ID}",
            json=NEW_CUSTOMER,
            headers={"X-Business-Id": OTHER_BUSINESS_ID, "X-Tenant-Id": OTHER_BUSINESS_ID},
        )

        assert response.status_code == 201
        assert len(repos.customers.list(TENANT)) == 1
        assert repos.customers.list(OTHER_BUSINESS_ID) == []

    def test_an_invalid_phone_is_rejected_without_echoing_it(
        self, client: TestClient, repos: Repositories
    ) -> None:
        response = client.post("/api/v1/customers", json={"name": "Asha", "phone": "12ab-secret"})

        assert response.status_code == 422
        assert "secret" not in response.text
        assert repos.customers.list(TENANT) == []

    @pytest.mark.parametrize("body", [{}, {"name": "   "}, {"name": "A", "unexpected": 1}])
    def test_invalid_bodies_are_rejected(self, client: TestClient, body: dict[str, object]) -> None:
        assert client.post("/api/v1/customers", json=body).status_code == 422

    def test_a_malformed_customer_id_is_rejected(self, client: TestClient) -> None:
        assert client.get("/api/v1/customers/not-a-customer-id").status_code == 422


class TestDemoAuthentication:
    def test_the_correct_key_authorizes_the_fixed_identity(
        self, demo_client: TestClient, repos: Repositories
    ) -> None:
        response = demo_client.post(
            "/api/v1/customers", json=NEW_CUSTOMER, headers={"X-Demo-Key": DEMO_KEY}
        )

        assert response.status_code == 201
        assert len(repos.customers.list(TENANT)) == 1

    def test_a_missing_and_a_wrong_key_are_rejected_identically(
        self, demo_client: TestClient, repos: Repositories
    ) -> None:
        missing = demo_client.post("/api/v1/customers", json=NEW_CUSTOMER)
        wrong = demo_client.post(
            "/api/v1/customers", json=NEW_CUSTOMER, headers={"X-Demo-Key": DEMO_KEY[:-1] + "!"}
        )
        empty = demo_client.get("/api/v1/customers/cus_x", headers={"X-Demo-Key": ""})

        for response in (missing, wrong, empty):
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "UNAUTHORIZED"
        assert missing.json()["error"] == wrong.json()["error"] == empty.json()["error"]
        assert repos.customers.list(TENANT) == []

    def test_the_key_never_appears_in_any_response(self, demo_client: TestClient) -> None:
        bad = demo_client.get("/api/v1/customers/cus_x", headers={"X-Demo-Key": "nope"})
        good = demo_client.post(
            "/api/v1/customers", json=NEW_CUSTOMER, headers={"X-Demo-Key": DEMO_KEY}
        )

        assert DEMO_KEY not in bad.text + good.text + str(good.headers)

    def test_the_key_grants_the_fixed_tenant_and_nothing_else(
        self, demo_client: TestClient, repos: Repositories
    ) -> None:
        demo_client.post(
            "/api/v1/customers",
            json=NEW_CUSTOMER,
            headers={"X-Demo-Key": DEMO_KEY, "X-Business-Id": OTHER_BUSINESS_ID},
        )

        assert len(repos.customers.list(TENANT)) == 1
        assert repos.customers.list(OTHER_BUSINESS_ID) == []

    def test_health_stays_open_and_docs_are_hidden(self, demo_client: TestClient) -> None:
        assert demo_client.get("/api/v1/health").status_code == 200
        assert demo_client.get("/docs").status_code == 404
        assert demo_client.get("/openapi.json").status_code == 404

    def test_a_key_does_nothing_in_production(self, repos: Repositories) -> None:
        production = _demo_settings(app_env="production")
        client = TestClient(create_app(production, repositories=repos))

        response = client.post(
            "/api/v1/customers", json=NEW_CUSTOMER, headers={"X-Demo-Key": DEMO_KEY}
        )

        assert response.status_code == 401
