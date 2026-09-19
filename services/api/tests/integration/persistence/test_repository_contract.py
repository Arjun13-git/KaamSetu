"""Behavioural contract every persistence adapter must satisfy (see ``tests/conftest.py``)."""

from datetime import datetime, timedelta

import pytest

from app.core.errors import (
    ConflictError,
    DomainValidationError,
    DuplicateRequestError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.core.ids import IdPrefix, new_id
from app.domain.asset import Asset
from app.domain.audit import AuditEvent
from app.domain.customer import Customer
from app.domain.enums import (
    AuditAction,
    AuditEntityType,
    JobSource,
    JobStatus,
    ServiceRequestStatus,
    ServiceType,
)
from app.domain.job import Job
from app.domain.job_workflow import (
    CompletionResult,
    JobCompletion,
    assign_job,
    complete_job,
    create_job,
    transition_job,
)
from app.domain.repositories import Repositories
from app.domain.technician import Technician
from tests.factories import (
    BUSINESS_ID,
    NOW,
    OTHER_BUSINESS_ID,
    make_asset,
    make_business,
    make_ctx,
    make_customer,
    make_service_request,
    make_technician,
)

CTX = make_ctx()
OTHER_CTX = make_ctx(OTHER_BUSINESS_ID)


def minutes(n: int) -> datetime:
    return NOW + timedelta(minutes=n)


def _audit(entity_id: str = "job_x", **overrides) -> AuditEvent:
    fields = {
        "audit_id": new_id(IdPrefix.AUDIT),
        "business_id": BUSINESS_ID,
        "actor_id": "usr_test",
        "action": AuditAction.CUSTOMER_CREATED,
        "entity_type": AuditEntityType.CUSTOMER,
        "entity_id": entity_id,
        "timestamp": NOW,
        "request_id": "req_test0001",
    }
    return AuditEvent(**{**fields, **overrides})


def _customer_with_asset(repos: Repositories, **customer_overrides) -> tuple[Customer, Asset]:
    customer = make_customer(**customer_overrides)
    asset = make_asset(customer)
    repos.customers.create(customer)
    repos.assets.create(asset)
    return customer, asset


def _technician(repos: Repositories, **overrides) -> Technician:
    technician = make_technician(**overrides)
    repos.technicians.create(technician)
    return technician


def _new_job(repos: Repositories, customer: Customer, asset: Asset, at: int = 0) -> Job:
    change = create_job(
        CTX,
        customer=customer,
        asset=asset,
        service_type=ServiceType.REPAIR,
        description="AC not cooling",
        now=minutes(at),
    )
    repos.jobs.create(change.job, change.audit)
    return change.job


def _advance(repos: Repositories, job: Job, technician: Technician, *steps: JobStatus) -> Job:
    """Drive a job through the real workflow and persist each step."""
    now = job.created_at
    change = assign_job(CTX, job, technician, now)
    repos.jobs.update(change.job, change.audit)
    job = change.job
    for step in steps:
        change = transition_job(CTX, job, step, now)
        repos.jobs.update(change.job, change.audit)
        job = change.job
    return job


def _in_progress_job(repos: Repositories, at: int = 0) -> tuple[Customer, Asset, Technician, Job]:
    customer, asset = _customer_with_asset(repos)
    technician = _technician(repos)
    job = _advance(repos, _new_job(repos, customer, asset, at), technician, JobStatus.IN_PROGRESS)
    return customer, asset, technician, job


def _completion(job: Job, at: int = 60) -> CompletionResult:
    return complete_job(
        CTX, job, JobCompletion(work_performed="Cleaned filter", parts_used=["filter"]), minutes(at)
    )


class TestBusinessesAndTenancy:
    def test_business_round_trip_and_isolation(self, repos: Repositories) -> None:
        business = make_business()
        repos.businesses.create(business)

        assert repos.businesses.get(BUSINESS_ID) == business
        with pytest.raises(NotFoundError):
            repos.businesses.get(OTHER_BUSINESS_ID)
        with pytest.raises(ConflictError):
            repos.businesses.create(business)

    def test_records_of_another_business_are_invisible_everywhere(
        self, repos: Repositories
    ) -> None:
        customer, asset, technician, job = _in_progress_job(repos)
        result = _completion(job)
        repos.jobs.complete(result.job, result.event, result.audit)
        request = make_service_request()
        repos.service_requests.create(request)

        with pytest.raises(NotFoundError):
            repos.customers.get(OTHER_BUSINESS_ID, customer.customer_id)
        with pytest.raises(NotFoundError):
            repos.assets.get(OTHER_BUSINESS_ID, asset.asset_id)
        with pytest.raises(NotFoundError):
            repos.technicians.get(OTHER_BUSINESS_ID, technician.technician_id)
        with pytest.raises(NotFoundError):
            repos.jobs.get(OTHER_BUSINESS_ID, job.job_id)
        with pytest.raises(NotFoundError):
            repos.service_events.get(OTHER_BUSINESS_ID, result.event.event_id)
        with pytest.raises(NotFoundError):
            repos.service_requests.get(OTHER_BUSINESS_ID, request.service_request_id)
        assert repos.customers.list(OTHER_BUSINESS_ID) == []
        assert repos.assets.list_by_customer(OTHER_BUSINESS_ID, customer.customer_id) == []
        assert repos.technicians.list(OTHER_BUSINESS_ID) == []
        assert repos.jobs.list(OTHER_BUSINESS_ID) == []
        assert repos.jobs.list_by_asset(OTHER_BUSINESS_ID, asset.asset_id) == []
        assert repos.jobs.list_by_customer(OTHER_BUSINESS_ID, customer.customer_id) == []
        assert repos.service_events.list_by_asset(OTHER_BUSINESS_ID, asset.asset_id) == []
        assert repos.service_events.list_by_customer(OTHER_BUSINESS_ID, customer.customer_id) == []
        assert repos.service_requests.list(OTHER_BUSINESS_ID) == []
        assert (
            repos.audits.list_for_entity(OTHER_BUSINESS_ID, AuditEntityType.JOB, job.job_id) == []
        )

    def test_lookups_never_cross_businesses(self, repos: Repositories) -> None:
        repos.customers.create(make_customer(phone="9876543210", name="Ravi Kumar"))
        repos.assets.create(make_asset(make_customer(), serial_number="SN-1"))

        assert repos.customers.find_by_phone(OTHER_BUSINESS_ID, "9876543210") == []
        assert repos.customers.search_by_name(OTHER_BUSINESS_ID, "ravi") == []
        assert repos.assets.find_by_serial(OTHER_BUSINESS_ID, "SN-1") == []

    def test_same_id_in_two_businesses_does_not_collide(self, repos: Repositories) -> None:
        shared_id = new_id(IdPrefix.CUSTOMER)
        repos.customers.create(make_customer(customer_id=shared_id, name="Tenant A"))
        repos.customers.create(
            make_customer(customer_id=shared_id, business_id=OTHER_BUSINESS_ID, name="Tenant B")
        )

        assert repos.customers.get(BUSINESS_ID, shared_id).name == "Tenant A"
        assert repos.customers.get(OTHER_BUSINESS_ID, shared_id).name == "Tenant B"


class TestCustomers:
    def test_round_trip_and_duplicate_create(self, repos: Repositories) -> None:
        customer = make_customer(phone="98765 43210", address="12 MG Road")
        repos.customers.create(customer)

        assert repos.customers.get(BUSINESS_ID, customer.customer_id) == customer
        with pytest.raises(ConflictError):
            repos.customers.create(customer)

    def test_get_missing_customer(self, repos: Repositories) -> None:
        with pytest.raises(NotFoundError):
            repos.customers.get(BUSINESS_ID, new_id(IdPrefix.CUSTOMER))

    def test_find_by_phone_returns_all_sharing_customers_after_normalization(
        self, repos: Repositories
    ) -> None:
        first = make_customer(name="Asha Rao", phone="+91 98765 43210")
        second = make_customer(name="Bharat Rao", phone="09876543210")
        other = make_customer(name="Chitra", phone="9123456789")
        for customer in (first, second, other):
            repos.customers.create(customer)

        found = repos.customers.find_by_phone(BUSINESS_ID, "98765-43210")

        assert [c.name for c in found] == ["Asha Rao", "Bharat Rao"]
        assert repos.customers.find_by_phone(BUSINESS_ID, "not a number") == []

    def test_customers_without_a_phone_are_never_matched_by_phone(
        self, repos: Repositories
    ) -> None:
        repos.customers.create(make_customer())

        assert repos.customers.find_by_phone(BUSINESS_ID, "9876543210") == []

    def test_search_by_name_is_a_case_insensitive_substring_match(
        self, repos: Repositories
    ) -> None:
        for name in ("Ravi Kumar", "Ravi Verma", "Sunita Devi"):
            repos.customers.create(make_customer(name=name))

        assert [c.name for c in repos.customers.search_by_name(BUSINESS_ID, "  RAVI ")] == [
            "Ravi Kumar",
            "Ravi Verma",
        ]
        assert [c.name for c in repos.customers.search_by_name(BUSINESS_ID, "nita")] == [
            "Sunita Devi"
        ]
        assert repos.customers.search_by_name(BUSINESS_ID, "   ") == []

    def test_list_is_ordered_by_name_and_limited(self, repos: Repositories) -> None:
        for name in ("Charu", "Asha", "Bharat"):
            repos.customers.create(make_customer(name=name))

        assert [c.name for c in repos.customers.list(BUSINESS_ID)] == ["Asha", "Bharat", "Charu"]
        assert len(repos.customers.list(BUSINESS_ID, limit=2)) == 2

    def test_returned_records_do_not_alias_stored_state(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)
        fetched = repos.assets.get(BUSINESS_ID, asset.asset_id)
        fetched.metadata["tampered"] = "yes"

        assert repos.assets.get(BUSINESS_ID, asset.asset_id).metadata == {}


class TestAssets:
    def test_round_trip_preserves_unknowns(self, repos: Repositories) -> None:
        customer = make_customer()
        repos.customers.create(customer)
        asset = make_asset(customer, brand=None, metadata={"tonnage": "1.5"})
        repos.assets.create(asset)

        stored = repos.assets.get(BUSINESS_ID, asset.asset_id)

        assert stored == asset
        assert stored.brand is None and stored.model is None and stored.serial_number is None
        with pytest.raises(ConflictError):
            repos.assets.create(asset)

    def test_list_by_customer_is_scoped_and_oldest_first(self, repos: Repositories) -> None:
        owner, other_owner = make_customer(), make_customer(name="Someone Else")
        older = make_asset(owner, created_at=minutes(0), updated_at=minutes(0))
        newer = make_asset(owner, created_at=minutes(5), updated_at=minutes(5))
        unrelated = make_asset(other_owner)
        for asset in (newer, older, unrelated):
            repos.assets.create(asset)

        listed = repos.assets.list_by_customer(BUSINESS_ID, owner.customer_id)

        assert [a.asset_id for a in listed] == [older.asset_id, newer.asset_id]

    def test_find_by_serial_ignores_case_spaces_and_hyphens(self, repos: Repositories) -> None:
        customer = make_customer()
        with_serial = make_asset(customer, serial_number="ab-12 34")
        repos.assets.create(with_serial)
        repos.assets.create(make_asset(customer))

        found = repos.assets.find_by_serial(BUSINESS_ID, "AB1234")

        assert [a.asset_id for a in found] == [with_serial.asset_id]
        assert repos.assets.find_by_serial(BUSINESS_ID, " ") == []


class TestTechnicians:
    def test_round_trip_and_active_filter(self, repos: Repositories) -> None:
        active = make_technician(name="Bela")
        inactive = make_technician(name="Anil", active=False)
        repos.technicians.create(active)
        repos.technicians.create(inactive)

        assert repos.technicians.get(BUSINESS_ID, active.technician_id) == active
        assert [t.name for t in repos.technicians.list(BUSINESS_ID)] == ["Anil", "Bela"]
        assert [t.name for t in repos.technicians.list(BUSINESS_ID, active_only=True)] == ["Bela"]
        with pytest.raises(ConflictError):
            repos.technicians.create(active)


class TestServiceRequests:
    def test_round_trip_preserves_the_original_request_and_extraction(
        self, repos: Repositories
    ) -> None:
        request = make_service_request(
            raw_text="Bhaiya LG AC thanda nahi kar raha",
            extraction={"asset": {"brand": "LG", "model": None}, "confidence": 0.86},
        )
        repos.service_requests.create(request)

        stored = repos.service_requests.get(BUSINESS_ID, request.service_request_id)

        assert stored == request
        assert stored.extraction == {"asset": {"brand": "LG", "model": None}, "confidence": 0.86}
        with pytest.raises(ConflictError):
            repos.service_requests.create(request)

    def test_idempotency_key_is_unique_within_a_business_only(self, repos: Repositories) -> None:
        first = make_service_request(idempotency_key="key-1")
        repos.service_requests.create(first)

        with pytest.raises(DuplicateRequestError):
            repos.service_requests.create(make_service_request(idempotency_key="key-1"))
        repos.service_requests.create(
            make_service_request(business_id=OTHER_BUSINESS_ID, idempotency_key="key-1")
        )

        found = repos.service_requests.get_by_idempotency_key(BUSINESS_ID, "key-1")
        assert found is not None and found.service_request_id == first.service_request_id
        assert repos.service_requests.get_by_idempotency_key(BUSINESS_ID, "unknown") is None

    def test_a_rejected_duplicate_leaves_no_partial_record(self, repos: Repositories) -> None:
        repos.service_requests.create(make_service_request(idempotency_key="key-1"))
        duplicate = make_service_request(idempotency_key="key-1")

        with pytest.raises(DuplicateRequestError):
            repos.service_requests.create(duplicate)

        with pytest.raises(NotFoundError):
            repos.service_requests.get(BUSINESS_ID, duplicate.service_request_id)

    def test_update_is_versioned(self, repos: Repositories) -> None:
        request = make_service_request()
        repos.service_requests.create(request)
        reviewed = request.evolve(
            status=ServiceRequestStatus.NEEDS_REVIEW, version=2, updated_at=minutes(1)
        )

        repos.service_requests.update(reviewed)

        assert repos.service_requests.get(BUSINESS_ID, request.service_request_id) == reviewed
        with pytest.raises(ConflictError):
            repos.service_requests.update(reviewed)  # stale: same version again
        with pytest.raises(ConflictError):
            repos.service_requests.update(request.evolve(version=5))  # skipped versions

    def test_update_of_a_missing_request(self, repos: Repositories) -> None:
        with pytest.raises(NotFoundError):
            repos.service_requests.update(make_service_request(version=2))

    def test_update_cannot_link_a_job(self, repos: Repositories) -> None:
        request = make_service_request()
        repos.service_requests.create(request)
        linked = request.evolve(
            status=ServiceRequestStatus.JOB_CREATED, job_id=new_id(IdPrefix.JOB), version=2
        )

        with pytest.raises(InvalidStateTransitionError):
            repos.service_requests.update(linked)

    def test_dismissed_requests_are_closed(self, repos: Repositories) -> None:
        request = make_service_request()
        repos.service_requests.create(request)
        dismissed = request.evolve(status=ServiceRequestStatus.DISMISSED, version=2)
        repos.service_requests.update(dismissed)

        with pytest.raises(ConflictError):
            repos.service_requests.update(
                dismissed.evolve(version=3, status=ServiceRequestStatus.NEEDS_REVIEW)
            )

    def test_list_filters_by_status_newest_first(self, repos: Repositories) -> None:
        old = make_service_request(created_at=minutes(0), updated_at=minutes(0))
        new = make_service_request(created_at=minutes(9), updated_at=minutes(9))
        failed = make_service_request(
            created_at=minutes(5),
            updated_at=minutes(5),
            status=ServiceRequestStatus.EXTRACTION_FAILED,
            failure_reason="AI_UNAVAILABLE",
        )
        for request in (old, new, failed):
            repos.service_requests.create(request)

        everything = repos.service_requests.list(BUSINESS_ID)
        only_failed = repos.service_requests.list(
            BUSINESS_ID, status=ServiceRequestStatus.EXTRACTION_FAILED
        )

        assert [r.service_request_id for r in everything] == [
            new.service_request_id,
            failed.service_request_id,
            old.service_request_id,
        ]
        assert [r.service_request_id for r in only_failed] == [failed.service_request_id]


class TestJobs:
    def test_create_writes_the_job_and_its_audit_together(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)

        job = _new_job(repos, customer, asset)

        assert repos.jobs.get(BUSINESS_ID, job.job_id) == job
        audits = repos.audits.list_for_entity(BUSINESS_ID, AuditEntityType.JOB, job.job_id)
        assert [a.action for a in audits] == [AuditAction.JOB_CREATED]

    def test_create_requires_a_new_job_and_rejects_duplicates(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)
        technician = _technician(repos)
        change = create_job(
            CTX,
            customer=customer,
            asset=asset,
            service_type=ServiceType.REPAIR,
            description="x",
            now=NOW,
        )
        repos.jobs.create(change.job, change.audit)
        assigned = assign_job(CTX, change.job, technician, NOW)

        with pytest.raises(ConflictError):
            repos.jobs.create(change.job, _audit(entity_id=change.job.job_id))
        with pytest.raises(DomainValidationError):
            repos.jobs.create(assigned.job, assigned.audit)

    def test_update_is_versioned_and_audited(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)
        technician = _technician(repos)
        job = _new_job(repos, customer, asset)
        change = assign_job(CTX, job, technician, minutes(1))

        repos.jobs.update(change.job, change.audit)

        assert repos.jobs.get(BUSINESS_ID, job.job_id) == change.job
        actions = [
            a.action
            for a in repos.audits.list_for_entity(BUSINESS_ID, AuditEntityType.JOB, job.job_id)
        ]
        assert actions == [AuditAction.JOB_CREATED, AuditAction.JOB_ASSIGNED]

    def test_a_stale_update_is_rejected_and_writes_nothing(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)
        first, second = _technician(repos), _technician(repos, name="Second")
        job = _new_job(repos, customer, asset)
        winner = assign_job(CTX, job, first, minutes(1))
        loser = assign_job(CTX, job, second, minutes(2))
        repos.jobs.update(winner.job, winner.audit)

        with pytest.raises(ConflictError):
            repos.jobs.update(loser.job, loser.audit)

        assert repos.jobs.get(BUSINESS_ID, job.job_id).technician_id == first.technician_id
        audits = repos.audits.list_for_entity(BUSINESS_ID, AuditEntityType.JOB, job.job_id)
        assert loser.audit.audit_id not in {a.audit_id for a in audits}

    def test_update_of_a_missing_job(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)
        technician = _technician(repos)
        never_stored = create_job(
            CTX,
            customer=customer,
            asset=asset,
            service_type=ServiceType.REPAIR,
            description="x",
            now=NOW,
        ).job
        change = assign_job(CTX, never_stored, technician, NOW)

        with pytest.raises(NotFoundError):
            repos.jobs.update(change.job, change.audit)

    def test_update_cannot_write_a_completed_job(self, repos: Repositories) -> None:
        _, _, _, job = _in_progress_job(repos)
        completed = _completion(job)

        with pytest.raises(InvalidStateTransitionError):
            repos.jobs.update(completed.job, completed.audit)

        assert repos.jobs.get(BUSINESS_ID, job.job_id).status is JobStatus.IN_PROGRESS

    def test_a_cancelled_job_is_frozen(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)
        job = _new_job(repos, customer, asset)
        cancelled = transition_job(CTX, job, JobStatus.CANCELLED, minutes(1))
        repos.jobs.update(cancelled.job, cancelled.audit)
        technician = _technician(repos)
        # A writer holding the pre-cancellation copy tries to carry on.
        late = assign_job(CTX, job, technician, minutes(2))

        with pytest.raises(ConflictError):
            repos.jobs.update(late.job.evolve(version=3), late.audit)

    def test_listing_filters_and_orders_newest_first(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)
        technician = _technician(repos)
        oldest = _new_job(repos, customer, asset, at=0)
        middle = _new_job(repos, customer, asset, at=10)
        newest = _new_job(repos, customer, asset, at=20)
        _advance(repos, middle, technician)

        assert [j.job_id for j in repos.jobs.list(BUSINESS_ID)] == [
            newest.job_id,
            middle.job_id,
            oldest.job_id,
        ]
        assert [j.job_id for j in repos.jobs.list(BUSINESS_ID, status=JobStatus.NEW)] == [
            newest.job_id,
            oldest.job_id,
        ]
        assert [
            j.job_id for j in repos.jobs.list(BUSINESS_ID, technician_id=technician.technician_id)
        ] == [middle.job_id]
        assert [j.job_id for j in repos.jobs.list(BUSINESS_ID, limit=1)] == [newest.job_id]
        assert [j.job_id for j in repos.jobs.list_by_asset(BUSINESS_ID, asset.asset_id)] == [
            newest.job_id,
            middle.job_id,
            oldest.job_id,
        ]
        assert [
            j.job_id for j in repos.jobs.list_by_customer(BUSINESS_ID, customer.customer_id)
        ] == [newest.job_id, middle.job_id, oldest.job_id]

    def test_listing_by_asset_excludes_other_assets(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)
        other_asset = make_asset(customer, brand="Samsung")
        repos.assets.create(other_asset)
        mine = _new_job(repos, customer, asset)
        _new_job(repos, customer, other_asset)

        assert [j.job_id for j in repos.jobs.list_by_asset(BUSINESS_ID, asset.asset_id)] == [
            mine.job_id
        ]


class TestCreateForRequest:
    def _prepared(self, repos: Repositories):
        customer, asset = _customer_with_asset(repos)
        request = make_service_request()
        repos.service_requests.create(request)
        job = create_job(
            CTX,
            customer=customer,
            asset=asset,
            service_type=ServiceType.REPAIR,
            description="AC not cooling",
            now=minutes(1),
            source=JobSource.INTAKE,
            service_request_id=request.service_request_id,
        )
        linked = request.evolve(
            status=ServiceRequestStatus.JOB_CREATED,
            job_id=job.job.job_id,
            version=2,
            updated_at=minutes(1),
        )
        return request, job, linked

    def test_creates_the_job_links_the_request_and_audits_atomically(
        self, repos: Repositories
    ) -> None:
        request, change, linked = self._prepared(repos)

        repos.jobs.create_for_request(change.job, linked, change.audit)

        assert repos.jobs.get(BUSINESS_ID, change.job.job_id) == change.job
        stored = repos.service_requests.get(BUSINESS_ID, request.service_request_id)
        assert stored.status is ServiceRequestStatus.JOB_CREATED
        assert stored.job_id == change.job.job_id
        assert repos.audits.list_for_entity(BUSINESS_ID, AuditEntityType.JOB, change.job.job_id)

    def test_a_retry_cannot_create_a_second_job(self, repos: Repositories) -> None:
        request, change, linked = self._prepared(repos)
        repos.jobs.create_for_request(change.job, linked, change.audit)
        customer = repos.customers.get(BUSINESS_ID, change.job.customer_id)
        asset = repos.assets.get(BUSINESS_ID, change.job.asset_id)
        retry = create_job(
            CTX,
            customer=customer,
            asset=asset,
            service_type=ServiceType.REPAIR,
            description="AC not cooling",
            now=minutes(2),
            source=JobSource.INTAKE,
            service_request_id=request.service_request_id,
        )
        retry_link = linked.evolve(job_id=retry.job.job_id, version=3)

        with pytest.raises(ConflictError):
            repos.jobs.create_for_request(retry.job, retry_link, retry.audit)

        assert [j.job_id for j in repos.jobs.list(BUSINESS_ID)] == [change.job.job_id]
        stored = repos.service_requests.get(BUSINESS_ID, request.service_request_id)
        assert stored.job_id == change.job.job_id

    def test_a_failure_part_way_writes_nothing(self, repos: Repositories) -> None:
        request, change, linked = self._prepared(repos)
        repos.audits.append(_audit(audit_id=change.audit.audit_id))  # collides with the job audit

        with pytest.raises(ConflictError):
            repos.jobs.create_for_request(change.job, linked, change.audit)

        with pytest.raises(NotFoundError):
            repos.jobs.get(BUSINESS_ID, change.job.job_id)
        stored = repos.service_requests.get(BUSINESS_ID, request.service_request_id)
        assert stored.status is ServiceRequestStatus.RECEIVED and stored.job_id is None

    def test_a_stale_request_version_is_rejected(self, repos: Repositories) -> None:
        request, change, linked = self._prepared(repos)
        repos.service_requests.update(
            request.evolve(status=ServiceRequestStatus.NEEDS_REVIEW, version=2)
        )

        with pytest.raises(ConflictError):
            repos.jobs.create_for_request(change.job, linked, change.audit)

        with pytest.raises(NotFoundError):
            repos.jobs.get(BUSINESS_ID, change.job.job_id)

    def test_inconsistent_links_are_rejected(self, repos: Repositories) -> None:
        _, change, linked = self._prepared(repos)

        with pytest.raises(DomainValidationError):
            repos.jobs.create_for_request(
                change.job, linked.evolve(job_id=new_id(IdPrefix.JOB)), change.audit
            )


class TestCompletion:
    def test_writes_job_event_and_audit_together(self, repos: Repositories) -> None:
        customer, asset, technician, job = _in_progress_job(repos)
        result = _completion(job)

        repos.jobs.complete(result.job, result.event, result.audit)

        stored = repos.jobs.get(BUSINESS_ID, job.job_id)
        assert stored.status is JobStatus.COMPLETED and stored.completed_at == minutes(60)
        assert repos.service_events.get(BUSINESS_ID, result.event.event_id) == result.event
        actions = [
            a.action
            for a in repos.audits.list_for_entity(BUSINESS_ID, AuditEntityType.JOB, job.job_id)
        ]
        assert AuditAction.JOB_COMPLETED in actions

    def test_completed_work_becomes_service_memory_for_the_asset_and_customer(
        self, repos: Repositories
    ) -> None:
        customer, asset = _customer_with_asset(repos)
        technician = _technician(repos)
        events = []
        for at in (0, 100, 200):
            job = _advance(
                repos, _new_job(repos, customer, asset, at=at), technician, JobStatus.IN_PROGRESS
            )
            result = _completion(job, at=at + 60)
            repos.jobs.complete(result.job, result.event, result.audit)
            events.append(result.event)

        by_asset = repos.service_events.list_by_asset(BUSINESS_ID, asset.asset_id)
        by_customer = repos.service_events.list_by_customer(BUSINESS_ID, customer.customer_id)

        expected = [e.event_id for e in reversed(events)]
        assert [e.event_id for e in by_asset] == expected
        assert [e.event_id for e in by_customer] == expected
        assert len(repos.service_events.list_by_asset(BUSINESS_ID, asset.asset_id, limit=1)) == 1

    def test_history_is_scoped_to_the_asset(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)
        other_asset = make_asset(customer, brand="Samsung")
        repos.assets.create(other_asset)
        technician = _technician(repos)
        job = _advance(
            repos, _new_job(repos, customer, other_asset), technician, JobStatus.IN_PROGRESS
        )
        result = _completion(job)
        repos.jobs.complete(result.job, result.event, result.audit)

        assert repos.service_events.list_by_asset(BUSINESS_ID, asset.asset_id) == []
        assert len(repos.service_events.list_by_asset(BUSINESS_ID, other_asset.asset_id)) == 1

    def test_a_failure_part_way_leaves_the_job_in_progress_with_no_event(
        self, repos: Repositories
    ) -> None:
        _, asset, _, job = _in_progress_job(repos)
        result = _completion(job)
        repos.audits.append(_audit(audit_id=result.audit.audit_id))  # collides with the job audit

        with pytest.raises(ConflictError):
            repos.jobs.complete(result.job, result.event, result.audit)

        assert repos.jobs.get(BUSINESS_ID, job.job_id).status is JobStatus.IN_PROGRESS
        assert repos.service_events.list_by_asset(BUSINESS_ID, asset.asset_id) == []
        with pytest.raises(NotFoundError):
            repos.service_events.get(BUSINESS_ID, result.event.event_id)

    def test_a_job_cannot_be_completed_twice(self, repos: Repositories) -> None:
        _, asset, _, job = _in_progress_job(repos)
        first = _completion(job)
        repos.jobs.complete(first.job, first.event, first.audit)
        second = _completion(job, at=90)

        with pytest.raises(ConflictError):
            repos.jobs.complete(second.job, second.event, second.audit)

        assert len(repos.service_events.list_by_asset(BUSINESS_ID, asset.asset_id)) == 1

    def test_a_stale_completion_is_rejected(self, repos: Repositories) -> None:
        _, asset, _, job = _in_progress_job(repos)
        result = _completion(job)
        cancelled = transition_job(CTX, job, JobStatus.CANCELLED, minutes(30))
        repos.jobs.update(cancelled.job, cancelled.audit)

        with pytest.raises(ConflictError):
            repos.jobs.complete(result.job, result.event, result.audit)

        assert repos.jobs.get(BUSINESS_ID, job.job_id).status is JobStatus.CANCELLED
        assert repos.service_events.list_by_asset(BUSINESS_ID, asset.asset_id) == []

    def test_only_an_in_progress_job_can_be_completed(self, repos: Repositories) -> None:
        customer, asset = _customer_with_asset(repos)
        technician = _technician(repos)
        job = _advance(repos, _new_job(repos, customer, asset), technician)  # ASSIGNED
        forged = _completion(_advance_in_memory_to_in_progress(job))

        with pytest.raises(ConflictError):
            repos.jobs.complete(forged.job, forged.event, forged.audit)

        assert repos.jobs.get(BUSINESS_ID, job.job_id).status is JobStatus.ASSIGNED

    def test_inconsistent_completions_are_rejected(self, repos: Repositories) -> None:
        _, _, _, job = _in_progress_job(repos)
        result = _completion(job)
        wrong_event = result.event.evolve(job_id=new_id(IdPrefix.JOB))

        with pytest.raises(DomainValidationError):
            repos.jobs.complete(result.job, wrong_event, result.audit)
        with pytest.raises(DomainValidationError):
            repos.jobs.complete(job, result.event, result.audit)  # job not COMPLETED


def _advance_in_memory_to_in_progress(job: Job) -> Job:
    """A copy of ``job`` claiming IN_PROGRESS, without persisting it (simulates a forged caller)."""
    return job.evolve(status=JobStatus.IN_PROGRESS)


class TestAudit:
    def test_append_and_list_for_entity_oldest_first(self, repos: Repositories) -> None:
        customer_id = new_id(IdPrefix.CUSTOMER)
        later = _audit(entity_id=customer_id, timestamp=minutes(5))
        earlier = _audit(entity_id=customer_id, timestamp=minutes(1))
        repos.audits.append(later)
        repos.audits.append(earlier)
        repos.audits.append(_audit(entity_id=new_id(IdPrefix.CUSTOMER)))

        listed = repos.audits.list_for_entity(BUSINESS_ID, AuditEntityType.CUSTOMER, customer_id)

        assert [a.audit_id for a in listed] == [earlier.audit_id, later.audit_id]
        with pytest.raises(ConflictError):
            repos.audits.append(earlier)
