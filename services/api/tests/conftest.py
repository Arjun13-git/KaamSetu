from collections.abc import Iterator

import pytest

from app.domain.repositories import Repositories
from app.providers.persistence.memory import build_in_memory_repositories


@pytest.fixture(autouse=True)
def _isolate_from_real_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never reach a real AWS account or read a developer's profile/.env."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)


@pytest.fixture(params=["memory"])
def repos(request: pytest.FixtureRequest) -> Iterator[Repositories]:
    """Every persistence adapter, so one contract suite holds all of them to the same rules."""
    if request.param == "memory":
        yield build_in_memory_repositories()
    else:  # pragma: no cover - guarded by params
        raise AssertionError(f"unknown adapter {request.param}")
