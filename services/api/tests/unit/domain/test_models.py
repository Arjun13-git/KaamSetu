from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.core.ids import IdPrefix, new_id
from app.domain.enums import (
    JobSource,
    JobStatus,
    ResolutionState,
    ServiceRequestStatus,
)
from app.domain.job import TimeSlot
from app.domain.service_request import EntityResolution, MatchCandidate
from tests.factories import (
    LATER,
    NOW,
    make_asset,
    make_business,
    make_customer,
    make_job,
    make_service_request,
    make_technician,
)


def test_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        make_customer(created_at=datetime(2026, 9, 19, 10, 0))


def test_offset_timestamps_are_normalized_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    customer = make_customer(created_at=datetime(2026, 9, 19, 15, 30, tzinfo=ist), updated_at=LATER)

    assert customer.created_at == NOW
    assert customer.created_at.tzinfo is UTC


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_customer(loyalty_tier="gold")


def test_records_are_immutable_and_evolve_revalidates() -> None:
    customer = make_customer()

    with pytest.raises(ValidationError):
        customer.name = "Someone Else"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        customer.evolve(phone="not a phone")
    assert customer.evolve(name="Ravi K").name == "Ravi K"


def test_phone_is_normalized_and_optional() -> None:
    assert make_customer(phone="98765 43210").phone == "+919876543210"
    assert make_customer().phone is None


def test_ids_of_the_wrong_kind_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_customer(customer_id=new_id(IdPrefix.ASSET))


def test_unknown_asset_details_stay_unknown() -> None:
    asset = make_asset(brand=None)

    assert asset.model is None
    assert asset.serial_number is None
    assert asset.warranty_until is None


def test_business_requires_a_real_timezone() -> None:
    with pytest.raises(ValidationError, match="unknown timezone"):
        make_business(timezone="Mars/Olympus")


def test_technician_defaults_to_active() -> None:
    assert make_technician().active is True


def test_time_slot_end_must_follow_start() -> None:
    with pytest.raises(ValidationError):
        TimeSlot(start=LATER, end=NOW)
    assert TimeSlot(start=NOW).end is None


class TestJobInvariants:
    def test_new_job_has_no_technician(self) -> None:
        with pytest.raises(ValidationError, match="NEW job cannot have a technician"):
            make_job(technician_id=new_id(IdPrefix.TECHNICIAN))

    @pytest.mark.parametrize(
        "status",
        [
            JobStatus.ASSIGNED,
            JobStatus.ON_THE_WAY,
            JobStatus.IN_PROGRESS,
        ],
    )
    def test_working_statuses_require_a_technician(self, status: JobStatus) -> None:
        with pytest.raises(ValidationError, match="requires a technician"):
            make_job(status=status)

    def test_scheduled_requires_a_slot(self) -> None:
        with pytest.raises(ValidationError, match="scheduled slot"):
            make_job(status=JobStatus.SCHEDULED, technician_id=new_id(IdPrefix.TECHNICIAN))

    def test_completed_at_is_set_iff_completed(self) -> None:
        technician_id = new_id(IdPrefix.TECHNICIAN)
        with pytest.raises(ValidationError, match="completed_at"):
            make_job(status=JobStatus.COMPLETED, technician_id=technician_id)
        with pytest.raises(ValidationError, match="completed_at"):
            make_job(completed_at=LATER)
        done = make_job(status=JobStatus.COMPLETED, technician_id=technician_id, completed_at=LATER)
        assert done.completed_at == LATER

    def test_intake_job_must_reference_its_request(self) -> None:
        with pytest.raises(ValidationError, match="service request"):
            make_job(source=JobSource.INTAKE)

    def test_cancelled_job_may_lack_a_technician(self) -> None:
        assert make_job(status=JobStatus.CANCELLED).technician_id is None


class TestServiceRequest:
    def test_starts_received_and_unresolved(self) -> None:
        request = make_service_request()

        assert request.status is ServiceRequestStatus.RECEIVED
        assert request.customer_resolution.state is ResolutionState.UNRESOLVED
        assert request.asset_resolution.state is ResolutionState.UNRESOLVED
        assert request.job_id is None

    def test_job_id_is_set_iff_job_created(self) -> None:
        job_id = new_id(IdPrefix.JOB)
        with pytest.raises(ValidationError, match="job_id"):
            make_service_request(status=ServiceRequestStatus.JOB_CREATED)
        with pytest.raises(ValidationError, match="job_id"):
            make_service_request(job_id=job_id)
        linked = make_service_request(status=ServiceRequestStatus.JOB_CREATED, job_id=job_id)
        assert linked.job_id == job_id

    def test_existing_resolution_needs_an_entity(self) -> None:
        with pytest.raises(ValidationError, match="requires an entity_id"):
            EntityResolution(state=ResolutionState.EXISTING)

    def test_ambiguous_resolution_needs_candidates_and_never_picks_one(self) -> None:
        candidates = [
            MatchCandidate(entity_id="cus_a", match_score=0.8, reasons=["name matches"]),
            MatchCandidate(entity_id="cus_b", match_score=0.78),
        ]
        ambiguous = EntityResolution(state=ResolutionState.AMBIGUOUS, candidates=candidates)
        assert ambiguous.entity_id is None

        with pytest.raises(ValidationError, match="at least two"):
            EntityResolution(state=ResolutionState.AMBIGUOUS, candidates=candidates[:1])
        with pytest.raises(ValidationError, match="cannot carry"):
            EntityResolution(
                state=ResolutionState.AMBIGUOUS, entity_id="cus_a", candidates=candidates
            )

    def test_resolved_entity_ids_must_be_the_right_kind(self) -> None:
        wrong_kind = EntityResolution(state=ResolutionState.EXISTING, entity_id="ast_123")
        with pytest.raises(ValidationError):
            make_service_request(customer_resolution=wrong_kind)

    def test_match_score_is_a_probability(self) -> None:
        with pytest.raises(ValidationError):
            MatchCandidate(entity_id="cus_a", match_score=1.5)

    def test_idempotency_key_is_restricted_to_safe_characters(self) -> None:
        assert make_service_request(idempotency_key="web-2026:09.19_a").idempotency_key
        with pytest.raises(ValidationError):
            make_service_request(idempotency_key="has space")

    def test_raw_text_is_required(self) -> None:
        with pytest.raises(ValidationError):
            make_service_request(raw_text="   ")
