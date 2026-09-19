import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from moto import mock_aws

from app.domain.repositories import Repositories
from app.providers.persistence.dynamodb.client import build_resource
from app.providers.persistence.dynamodb.repositories import build_dynamodb_repositories
from app.providers.persistence.dynamodb.table import create_table
from app.providers.persistence.memory import build_in_memory_repositories
from tests.api_support import Api, build_api

TEST_TABLE = "kaamsetu-test"


@pytest.fixture(autouse=True)
def _isolate_from_real_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never reach a real AWS account or read a developer's profile/.env."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)


# Set DYNAMODB_LOCAL_ENDPOINT (e.g. http://localhost:8000) to also run the contract suite against a
# real DynamoDB engine instead of only the moto mock.
_LOCAL_ENDPOINT = os.environ.get("DYNAMODB_LOCAL_ENDPOINT")
_ADAPTERS = ["memory", "dynamodb", *(["dynamodb-local"] if _LOCAL_ENDPOINT else [])]


@pytest.fixture(params=_ADAPTERS)
def repos(request: pytest.FixtureRequest) -> Iterator[Repositories]:
    """Every persistence adapter, so one contract suite holds all of them to the same rules."""
    if request.param == "memory":
        yield build_in_memory_repositories()
    elif request.param == "dynamodb":
        with mock_aws():
            resource = build_resource(region="ap-south-1", profile=None, endpoint_url=None)
            create_table(resource, TEST_TABLE)
            yield build_dynamodb_repositories(resource, TEST_TABLE)
    else:
        resource = build_resource(region="ap-south-1", profile=None, endpoint_url=_LOCAL_ENDPOINT)
        table_name = f"{TEST_TABLE}-{uuid4().hex[:12]}"
        create_table(resource, table_name)
        try:
            yield build_dynamodb_repositories(resource, table_name)
        finally:
            resource.Table(table_name).delete()


@pytest.fixture
def api(repos: Repositories) -> Api:
    """The HTTP API over every persistence adapter, acting as the fixed development identity."""
    return build_api(repos)
