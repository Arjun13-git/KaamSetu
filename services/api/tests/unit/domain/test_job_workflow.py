from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.core.errors import (
    ConflictError,
    DomainValidationError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.domain.asset import Asset
from app.domain.customer import Customer
from app.domain.enums import (
    AuditAction,
    JobSource,
    JobStatus,
    ServiceType,
    Urgency,
)
from app.domain.job import Job, TimeSlot
from app.domain.job_workflow import (
    JobAmendment,
    JobCompletion,
    amend_job,
    assign_job,
    complete_job,
    create_job,
    transition_job,
)
from app.domain.technician import Technician
from tests.factories import (
    LATER,
    NOW,
    OTHER_BUSINESS_ID,
    make_asset,
    make_ctx,
    make_customer,
    make_technician,
)

CTX = make_ctx()


def _new_job() -> tuple[Customer, Asset, Job]:
    customer = make_customer()
    asset = make_asset(customer)
    change = create_job(
        CTX,
        customer=customer,
        asset=asset,
        service_type=ServiceType.REPAIR,
        description="AC not cooling",
        now=NOW,
    )
    return customer, asset, change.job


def _job_in(status: JobStatus, technician: Technician | None = None) -> Job:
    """Walk a job through the real workflow to ``status`` (never COMPLETED)."""
    _, _, job = _new_job()
    technician = technician or make_technician()
    slot = TimeSlot(start=LATER)
    path = {
        JobStatus.NEW: [],
        JobStatus.ASSIGNED: [],
        JobStatus.SCHEDULED: [JobStatus.SCHEDULED],
        JobStatus.ON_THE_WAY: [JobStatus.ON_THE_WAY],
        JobStatus.IN_PROGRESS: [JobStatus.IN_PROGRESS],
        JobStatus.CANCELLED: [JobStatus.CANCELLED],
    }[status]
    if status is not JobStatus.NEW:
        job = assign_job(CTX, job, technician, NOW).job
    for step in path:
        job = transition_job(
            CTX, job, step, NOW, scheduled_slot=slot if step is JobStatus.SCHEDULED else None
        ).job
    return job


class TestCreateJob:
    def test_creates_a_new_unassigned_job(self) -> None:
        _, _, job = _new_job()

        assert job.status is JobStatus.NEW
        assert job.technician_id is None
        assert job.version == 1
        assert job.source is JobSource.MANUAL
        assert job.urgency is Urgency.NORMAL

    def test_audit_record_describes_the_creation_without_free_text(self) -> None:
        customer = make_customer()
        asset = make_asset(customer)
        change = create_job(
            CTX,
            customer=customer,
            asset=asset,
            service_type=ServiceType.REPAIR,
            description="Sensitive customer wording",
            now=NOW,
        )

        assert change.audit.action is AuditAction.JOB_CREATED
        assert change.audit.entity_id == change.job.job_id
        assert change.audit.actor_id == CTX.actor_id
        assert change.audit.request_id == CTX.request_id
        assert "Sensitive" not in str(change.audit.metadata)

    def test_asset_must_belong_to_the_customer(self) -> None:
        with pytest.raises(DomainValidationError, match="does not belong"):
            create_job(
                CTX,
                customer=make_customer(),
                asset=make_asset(make_customer()),
                service_type=ServiceType.REPAIR,
                description="x",
                now=NOW,
            )

    def test_other_business_records_look_like_missing_records(self) -> None:
        foreign_customer = make_customer(business_id=OTHER_BUSINESS_ID)
        foreign_asset = make_asset(foreign_customer)
        with pytest.raises(NotFoundError):
            create_job(
                CTX,
                customer=foreign_customer,
                asset=foreign_asset,
                service_type=ServiceType.REPAIR,
                description="x",
                now=NOW,
            )

    def test_intake_jobs_must_reference_a_request(self) -> None:
        customer = make_customer()
        with pytest.raises(ValidationError):
            create_job(
                CTX,
                customer=customer,
                asset=make_asset(customer),
                service_type=ServiceType.REPAIR,
                description="x",
                now=NOW,
                source=JobSource.INTAKE,
            )


class TestAssign:
    def test_assigning_a_new_job_makes_it_assigned(self) -> None:
        _, _, job = _new_job()
        technician = make_technician()

        change = assign_job(CTX, job, technician, LATER)

        assert change.job.status is JobStatus.ASSIGNED
        assert change.job.technician_id == technician.technician_id
        assert change.job.version == job.version + 1
        assert change.audit.action is AuditAction.JOB_ASSIGNED

    @pytest.mark.parametrize(
        "status", [JobStatus.ASSIGNED, JobStatus.SCHEDULED, JobStatus.ON_THE_WAY]
    )
    def test_reassignment_keeps_the_status(self, status: JobStatus) -> None:
        job = _job_in(status)
        replacement = make_technician(name="Second Tech")

        change = assign_job(CTX, job, replacement, LATER)

        assert change.job.status is status
        assert change.job.technician_id == replacement.technician_id
        assert change.audit.metadata["previous_technician_id"] == job.technician_id

    @pytest.mark.parametrize("status", [JobStatus.IN_PROGRESS, JobStatus.CANCELLED])
    def test_cannot_assign_once_work_started_or_cancelled(self, status: JobStatus) -> None:
        with pytest.raises(InvalidStateTransitionError):
            assign_job(CTX, _job_in(status), make_technician(), LATER)

    def test_inactive_technician_is_rejected(self) -> None:
        _, _, job = _new_job()
        with pytest.raises(DomainValidationError, match="not active"):
            assign_job(CTX, job, make_technician(active=False), LATER)

    def test_technician_from_another_business_is_rejected(self) -> None:
        _, _, job = _new_job()
        with pytest.raises(NotFoundError):
            assign_job(CTX, job, make_technician(business_id=OTHER_BUSINESS_ID), LATER)

    def test_assigning_the_same_technician_again_is_rejected(self) -> None:
        technician = make_technician()
        job = _job_in(JobStatus.ASSIGNED, technician)
        with pytest.raises(DomainValidationError, match="already assigned"):
            assign_job(CTX, job, technician, LATER)


class TestTransition:
    def test_progresses_forward_and_audits_each_step(self) -> None:
        job = _job_in(JobStatus.ASSIGNED)

        change = transition_job(CTX, job, JobStatus.ON_THE_WAY, LATER)

        assert change.job.status is JobStatus.ON_THE_WAY
        assert change.audit.action is AuditAction.JOB_STATUS_CHANGED
        assert change.audit.metadata == {"from": "ASSIGNED", "to": "ON_THE_WAY"}

    def test_scheduling_requires_and_records_a_slot(self) -> None:
        job = _job_in(JobStatus.ASSIGNED)
        with pytest.raises(DomainValidationError, match="scheduled slot"):
            transition_job(CTX, job, JobStatus.SCHEDULED, LATER)

        slot = TimeSlot(start=LATER, end=LATER + timedelta(hours=2))
        change = transition_job(CTX, job, JobStatus.SCHEDULED, LATER, scheduled_slot=slot)
        assert change.job.scheduled_slot == slot

    def test_a_slot_is_only_accepted_when_scheduling(self) -> None:
        job = _job_in(JobStatus.ASSIGNED)
        with pytest.raises(DomainValidationError):
            transition_job(
                CTX, job, JobStatus.ON_THE_WAY, LATER, scheduled_slot=TimeSlot(start=LATER)
            )

    def test_completed_cannot_be_requested_as_a_transition(self) -> None:
        job = _job_in(JobStatus.IN_PROGRESS)
        with pytest.raises(InvalidStateTransitionError, match="job completion"):
            transition_job(CTX, job, JobStatus.COMPLETED, LATER)

    def test_assigned_cannot_be_requested_as_a_transition(self) -> None:
        _, _, job = _new_job()
        with pytest.raises(InvalidStateTransitionError, match="assigning a technician"):
            transition_job(CTX, job, JobStatus.ASSIGNED, LATER)

    def test_backward_and_terminal_moves_are_rejected(self) -> None:
        with pytest.raises(InvalidStateTransitionError):
            transition_job(CTX, _job_in(JobStatus.IN_PROGRESS), JobStatus.ON_THE_WAY, LATER)
        with pytest.raises(InvalidStateTransitionError):
            transition_job(CTX, _job_in(JobStatus.CANCELLED), JobStatus.IN_PROGRESS, LATER)

    @pytest.mark.parametrize(
        "status",
        [
            JobStatus.NEW,
            JobStatus.ASSIGNED,
            JobStatus.SCHEDULED,
            JobStatus.ON_THE_WAY,
            JobStatus.IN_PROGRESS,
        ],
    )
    def test_any_pre_completion_job_can_be_cancelled(self, status: JobStatus) -> None:
        change = transition_job(CTX, _job_in(status), JobStatus.CANCELLED, LATER)

        assert change.job.status is JobStatus.CANCELLED

    def test_other_business_job_is_not_found(self) -> None:
        job = _job_in(JobStatus.ASSIGNED)
        with pytest.raises(NotFoundError):
            transition_job(make_ctx(OTHER_BUSINESS_ID), job, JobStatus.ON_THE_WAY, LATER)


class TestAmend:
    def test_changes_only_the_supplied_fields(self) -> None:
        job = _job_in(JobStatus.ASSIGNED)

        change = amend_job(CTX, job, JobAmendment(urgency=Urgency.HIGH), LATER)

        assert change.job.urgency is Urgency.HIGH
        assert change.job.description == job.description
        assert change.job.status is job.status
        assert change.audit.metadata == {"fields": "urgency"}

    def test_cannot_set_status_or_technician(self) -> None:
        with pytest.raises(ValidationError):
            JobAmendment.model_validate({"status": "COMPLETED"})
        with pytest.raises(ValidationError):
            JobAmendment.model_validate({"technician_id": "tec_x"})

    def test_required_fields_cannot_be_cleared(self) -> None:
        with pytest.raises(ValidationError, match="cannot be cleared"):
            JobAmendment.model_validate({"description": None})

    def test_empty_amendment_is_rejected(self) -> None:
        with pytest.raises(DomainValidationError, match="No changes"):
            amend_job(CTX, _job_in(JobStatus.ASSIGNED), JobAmendment(), LATER)

    @pytest.mark.parametrize("status", [JobStatus.CANCELLED])
    def test_terminal_jobs_cannot_be_amended(self, status: JobStatus) -> None:
        with pytest.raises(ConflictError):
            amend_job(CTX, _job_in(status), JobAmendment(urgency=Urgency.LOW), LATER)


class TestComplete:
    def _completion(self) -> JobCompletion:
        return JobCompletion(
            work_performed="Cleaned filter and checked gas pressure",
            technician_notes="Customer advised to monitor cooling",
            parts_used=["filter"],
            follow_up_required=False,
        )

    def test_completion_yields_job_event_and_audit_together(self) -> None:
        job = _job_in(JobStatus.IN_PROGRESS)

        result = complete_job(CTX, job, self._completion(), LATER)

        assert result.job.status is JobStatus.COMPLETED
        assert result.job.completed_at == LATER
        assert result.job.version == job.version + 1
        assert result.event.job_id == job.job_id
        assert result.event.asset_id == job.asset_id
        assert result.event.customer_id == job.customer_id
        assert result.event.technician_id == job.technician_id
        assert result.event.timestamp == LATER
        assert result.event.parts_used == ["filter"]
        assert result.audit.action is AuditAction.JOB_COMPLETED
        assert result.audit.metadata == {"service_event_id": result.event.event_id}

    def test_summary_restates_recorded_facts_only(self) -> None:
        result = complete_job(CTX, _job_in(JobStatus.IN_PROGRESS), self._completion(), LATER)

        assert result.event.summary == (
            "Reported: AC not cooling | Work performed: Cleaned filter and checked gas pressure"
        )

    @pytest.mark.parametrize(
        "status",
        [
            JobStatus.NEW,
            JobStatus.ASSIGNED,
            JobStatus.SCHEDULED,
            JobStatus.ON_THE_WAY,
            JobStatus.CANCELLED,
        ],
    )
    def test_only_an_in_progress_job_can_be_completed(self, status: JobStatus) -> None:
        with pytest.raises(InvalidStateTransitionError, match="IN_PROGRESS"):
            complete_job(CTX, _job_in(status), self._completion(), LATER)

    def test_a_completed_job_cannot_be_completed_again(self) -> None:
        completed = complete_job(CTX, _job_in(JobStatus.IN_PROGRESS), self._completion(), LATER)

        with pytest.raises(InvalidStateTransitionError):
            complete_job(CTX, completed.job, self._completion(), LATER)

    def test_other_business_job_is_not_found(self) -> None:
        with pytest.raises(NotFoundError):
            complete_job(
                make_ctx(OTHER_BUSINESS_ID),
                _job_in(JobStatus.IN_PROGRESS),
                self._completion(),
                LATER,
            )

    def test_work_performed_is_required(self) -> None:
        with pytest.raises(ValidationError):
            JobCompletion(work_performed="  ")

    def test_completed_is_never_reachable_by_any_other_workflow_function(self) -> None:
        job = _job_in(JobStatus.IN_PROGRESS)
        with pytest.raises(InvalidStateTransitionError):
            transition_job(CTX, job, JobStatus.COMPLETED, LATER)
        with pytest.raises(ValidationError):
            JobAmendment.model_validate({"status": JobStatus.COMPLETED})
        assert complete_job(CTX, job, self._completion(), LATER).job.status is JobStatus.COMPLETED
