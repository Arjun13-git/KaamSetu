"""Behaviour specific to the DynamoDB adapter: item layout, key design and error translation."""

import logging
from collections.abc import Iterator
from typing import Any

import pytest
from moto import mock_aws

from app.core.errors import StorageError
from app.domain.enums import JobStatus, ServiceType
from app.domain.job_workflow import (
    JobCompletion,
    assign_job,
    complete_job,
    create_job,
    transition_job,
)
from app.providers.persistence.dynamodb.client import build_resource
from app.providers.persistence.dynamodb.repositories import build_dynamodb_repositories
from app.providers.persistence.dynamodb.table import create_table
from tests.factories import (
    BUSINESS_ID,
    NOW,
    OTHER_BUSINESS_ID,
    make_asset,
    make_ctx,
    make_customer,
    make_service_request,
    make_technician,
)

TABLE = "kaamsetu-adapter-test"


@pytest.fixture
def dynamo() -> Iterator[tuple[Any, Any]]:
    with mock_aws():
        resource = build_resource(region="ap-south-1", profile=None, endpoint_url=None)
        create_table(resource, TABLE)
        yield resource, build_dynamodb_repositories(resource, TABLE)


def _all_items(resource: Any) -> list[dict[str, Any]]:
    return resource.Table(TABLE).scan()["Items"]


def test_every_item_lives_in_its_own_tenant_partition(dynamo: tuple[Any, Any]) -> None:
    resource, repos = dynamo
    ctx = make_ctx()
    customer = make_customer(phone="9876543210")
    asset = make_asset(customer, serial_number="SN-1")
    technician = make_technician()
    other = make_customer(business_id=OTHER_BUSINESS_ID)
    for repo, record in (
        (repos.customers, customer),
        (repos.assets, asset),
        (repos.technicians, technician),
        (repos.customers, other),
    ):
        repo.create(record)
    change = create_job(
        ctx,
        customer=customer,
        asset=asset,
        service_type=ServiceType.REPAIR,
        description="AC not cooling",
        now=NOW,
    )
    repos.jobs.create(change.job, change.audit)
    request = make_service_request(idempotency_key="abc")
    repos.service_requests.create(request)

    items = _all_items(resource)

    assert {item["PK"] for item in items} == {
        f"BUSINESS#{BUSINESS_ID}",
        f"BUSINESS#{OTHER_BUSINESS_ID}",
    }
    for item in items:
        tenant_id = item["PK"].removeprefix("BUSINESS#")
        if item["SK"].startswith("IDEMPOTENCY#"):
            assert item["service_request_id"] == request.service_request_id
        else:
            assert item["business_id"] == tenant_id
        for index_key in ("GSI1PK", "GSI2PK", "GSI3PK"):
            if index_key in item:
                assert item[index_key].startswith(f"BUSINESS#{tenant_id}#")


def test_items_are_stored_as_readable_native_attributes(dynamo: tuple[Any, Any]) -> None:
    resource, repos = dynamo
    request = make_service_request(extraction={"confidence": 0.86, "brand": "LG", "model": None})
    repos.service_requests.create(request)

    item = resource.Table(TABLE).get_item(
        Key={"PK": f"BUSINESS#{BUSINESS_ID}", "SK": f"SERVICEREQUEST#{request.service_request_id}"}
    )["Item"]

    assert item["raw_text"] == request.raw_text
    assert item["status"] == "RECEIVED"
    assert item["extraction"]["brand"] == "LG" and item["extraction"]["model"] is None
    assert (
        repos.service_requests.get(BUSINESS_ID, request.service_request_id).extraction["confidence"]
        == 0.86
    )


def test_secondary_index_keys_are_sparse(dynamo: tuple[Any, Any]) -> None:
    resource, repos = dynamo
    without_phone = make_customer()
    repos.customers.create(without_phone)

    item = resource.Table(TABLE).get_item(
        Key={"PK": f"BUSINESS#{BUSINESS_ID}", "SK": f"CUSTOMER#{without_phone.customer_id}"}
    )["Item"]

    assert "GSI1PK" not in item


def test_completing_a_job_adds_an_indexed_event_and_an_audit_record(
    dynamo: tuple[Any, Any],
) -> None:
    resource, repos = dynamo
    ctx = make_ctx()
    customer, technician = make_customer(), make_technician()
    asset = make_asset(customer)
    for repo, record in (
        (repos.customers, customer),
        (repos.assets, asset),
        (repos.technicians, technician),
    ):
        repo.create(record)
    change = create_job(
        ctx,
        customer=customer,
        asset=asset,
        service_type=ServiceType.REPAIR,
        description="AC not cooling",
        now=NOW,
    )
    repos.jobs.create(change.job, change.audit)
    assigned = assign_job(ctx, change.job, technician, NOW)
    repos.jobs.update(assigned.job, assigned.audit)
    started = transition_job(ctx, assigned.job, JobStatus.IN_PROGRESS, NOW)
    repos.jobs.update(started.job, started.audit)
    before = len(_all_items(resource))

    result = complete_job(ctx, started.job, JobCompletion(work_performed="Cleaned filter"), NOW)
    repos.jobs.complete(result.job, result.event, result.audit)

    assert len(_all_items(resource)) == before + 2  # service event + audit; the job is replaced
    event_item = next(i for i in _all_items(resource) if i["SK"].startswith("EVENT#"))
    assert event_item["GSI3PK"] == f"BUSINESS#{BUSINESS_ID}#ASSET#{asset.asset_id}"


def test_store_failures_become_a_generic_storage_error_without_internals(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with mock_aws():
        resource = build_resource(region="ap-south-1", profile=None, endpoint_url=None)
        repos = build_dynamodb_repositories(resource, "table-that-was-never-created")

        with caplog.at_level(logging.ERROR), pytest.raises(StorageError) as caught:
            repos.customers.get(BUSINESS_ID, "cus_missing")

    assert "table-that-was-never-created" not in caught.value.message
    assert "ResourceNotFound" not in caught.value.message
    assert any("DynamoDB operation failed" in record.message for record in caplog.records)
