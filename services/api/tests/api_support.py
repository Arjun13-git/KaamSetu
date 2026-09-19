"""Helpers for driving the HTTP API in tests."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.repositories import Repositories
from app.main import create_app
from tests.factories import NOW

TENANT = "bus_demo"


class TickingClock:
    """A deterministic clock that advances one second per reading, so timestamps are strictly
    increasing across a workflow."""

    def __init__(self, start: datetime = NOW) -> None:
        self._now = start

    def __call__(self) -> datetime:
        self._now += timedelta(seconds=1)
        return self._now


def dev_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"app_env": "test", "data_provider": "memory", "_env_file": None}
    return Settings(**{**values, **overrides})  # type: ignore[arg-type]


@dataclass
class Api:
    client: TestClient
    repos: Repositories

    def call(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        expect: int,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        response = self.client.request(method, f"/api/v1{path}", json=body, headers=headers)
        assert response.status_code == expect, (
            f"{method} {path} -> {response.status_code}, expected {expect}: {response.text}"
        )
        parsed: dict[str, Any] = response.json()
        return parsed["data"] if "data" in parsed else parsed

    def customer(self, **overrides: Any) -> dict[str, Any]:
        body = {"name": "Ravi Kumar", "phone": "90000 20001", **overrides}
        return self.call("POST", "/customers", body, expect=201)

    def asset(self, customer_id: str, **overrides: Any) -> dict[str, Any]:
        body = {"asset_type": "air_conditioner", "brand": "LG", **overrides}
        return self.call("POST", f"/customers/{customer_id}/assets", body, expect=201)

    def technician(self, **overrides: Any) -> dict[str, Any]:
        body = {"name": "Imran Sheikh", "skills": ["air_conditioner"], **overrides}
        return self.call("POST", "/technicians", body, expect=201)

    def job(
        self,
        customer_id: str,
        asset_id: str,
        *,
        key: str | None = None,
        expect: int = 201,
        **overrides: Any,
    ) -> dict[str, Any]:
        body = {
            "customer_id": customer_id,
            "asset_id": asset_id,
            "service_type": "repair",
            "description": "AC not cooling",
            **overrides,
        }
        headers = {"Idempotency-Key": key} if key else None
        return self.call("POST", "/jobs", body, expect=expect, headers=headers)

    def in_progress_job(self) -> dict[str, Any]:
        """A job taken through the real endpoints to IN_PROGRESS, with everything it refers to."""
        customer = self.customer()
        asset = self.asset(customer["customer_id"])
        technician = self.technician()
        job = self.job(customer["customer_id"], asset["asset_id"])
        job_id = job["job_id"]
        self.call(
            "POST",
            f"/jobs/{job_id}/assign",
            {"technician_id": technician["technician_id"]},
            expect=200,
        )
        started = self.call(
            "POST", f"/jobs/{job_id}/transition", {"to_status": "IN_PROGRESS"}, expect=200
        )
        return {"job": started, "customer": customer, "asset": asset, "technician": technician}


def build_api(repos: Repositories, *, settings: Settings | None = None, **app_kwargs: Any) -> Api:
    app_kwargs.setdefault("clock", TickingClock())
    app = create_app(settings or dev_settings(), repositories=repos, **app_kwargs)
    return Api(TestClient(app), repos)
