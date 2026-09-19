"""The Lambda entry point, driven with API Gateway HTTP API (payload v2) events against a mocked
DynamoDB table: the walking skeleton without leaving the machine."""

import importlib
import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from moto import mock_aws
from pydantic import ValidationError

from app.providers.persistence.dynamodb.client import build_resource
from app.providers.persistence.dynamodb.table import create_table

TABLE = "kaamsetu-lambda-test"
DEMO_KEY = "lambda-test-only-key-0123456789abcdef-01234567"
Invoke = Callable[..., dict[str, Any]]


def _event(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    host = "abc123.execute-api.us-east-1.amazonaws.com"
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": host, "content-type": "application/json", **(headers or {})},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "abc123",
            "domainName": host,
            "domainPrefix": "abc123",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.9",
                "userAgent": "pytest",
            },
            "requestId": "request-1",
            "routeKey": "$default",
            "stage": "$default",
            "time": "19/Sep/2026:10:00:00 +0000",
            "timeEpoch": 1789812000000,
        },
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def _import_handler() -> ModuleType:
    sys.modules.pop("app.lambda_handler", None)
    return importlib.import_module("app.lambda_handler")


@pytest.fixture
def deployed_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Environment as the SAM template configures it. Runs from an empty directory so a
    developer's local .env file cannot leak into the settings."""
    monkeypatch.chdir(tmp_path)
    for name, value in {
        "APP_ENV": "demo",
        "DATA_PROVIDER": "dynamodb",
        "DYNAMODB_TABLE": TABLE,
        "AWS_REGION": "us-east-1",
        "DEMO_API_KEY": DEMO_KEY,
        "LOG_LEVEL": "INFO",
    }.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def invoke(deployed_env: None) -> Iterator[Invoke]:
    with mock_aws():
        resource = build_resource(region="us-east-1", profile=None, endpoint_url=None)
        create_table(resource, TABLE)
        module = _import_handler()
        context = SimpleNamespace(aws_request_id="request-1")

        def call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
            response: dict[str, Any] = module.handler(_event(method, path, **kwargs), context)
            return response

        call.table = resource.Table(TABLE)  # type: ignore[attr-defined]
        yield call
    sys.modules.pop("app.lambda_handler", None)


def _json(response: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(response["body"])
    return parsed


def test_health_is_served_through_api_gateway_without_a_key(invoke: Invoke) -> None:
    response = invoke("GET", "/api/v1/health")

    assert response["statusCode"] == 200
    assert _json(response)["data"]["status"] == "ok"
    assert response["headers"]["x-request-id"].startswith("req_")


def test_a_customer_written_through_lambda_is_read_back_from_dynamodb(invoke: Invoke) -> None:
    key = {"x-demo-key": DEMO_KEY}

    created = invoke(
        "POST", "/api/v1/customers", headers=key, body={"name": "Asha Rao", "phone": "9876543210"}
    )
    customer_id = _json(created)["data"]["customer_id"]
    fetched = invoke("GET", f"/api/v1/customers/{customer_id}", headers=key)

    assert created["statusCode"] == 201
    assert fetched["statusCode"] == 200
    assert _json(fetched)["data"]["phone"] == "+919876543210"
    stored = invoke.table.get_item(  # type: ignore[attr-defined]
        Key={"PK": "BUSINESS#bus_demo", "SK": f"CUSTOMER#{customer_id}"}
    )["Item"]
    assert stored["business_id"] == "bus_demo"
    assert stored["name"] == "Asha Rao"


def test_requests_without_the_key_never_reach_the_data(invoke: Invoke) -> None:
    denied = invoke("POST", "/api/v1/customers", body={"name": "Intruder"})
    wrong = invoke(
        "POST", "/api/v1/customers", headers={"x-demo-key": "wrong"}, body={"name": "Intruder"}
    )

    assert denied["statusCode"] == wrong["statusCode"] == 401
    assert _json(denied)["error"]["code"] == "UNAUTHORIZED"
    assert invoke.table.scan()["Items"] == []  # type: ignore[attr-defined]


def test_a_client_supplied_tenant_cannot_redirect_the_write(invoke: Invoke) -> None:
    response = invoke(
        "POST",
        "/api/v1/customers",
        headers={"x-demo-key": DEMO_KEY, "x-business-id": "bus_other"},
        body={"name": "Asha Rao"},
    )

    assert response["statusCode"] == 201
    partitions = {item["PK"] for item in invoke.table.scan()["Items"]}  # type: ignore[attr-defined]
    assert partitions == {"BUSINESS#bus_demo"}


def test_a_misconfigured_deployment_refuses_to_start(
    deployed_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEMO_API_KEY")

    with pytest.raises(ValidationError, match="DEMO_API_KEY"):
        _import_handler()
    sys.modules.pop("app.lambda_handler", None)
