"""The job lifecycle through the HTTP API, over every persistence adapter."""

from typing import Any

import pytest

from app.domain.enums import (
    AuditAction,
    AuditEntityType,
    JobStatus,
    ServiceRequestStatus,
    ServiceType,
)
from app.domain.job_workflow import create_job
from tests.api_support import TENANT, Api
from tests.factories import (
    NOW,
    OTHER_BUSINESS_ID,
    make_asset,
    make_ctx,
    make_customer,
    make_technician,
)

SLOT = {"start": "2026-09-20T11:30:00Z", "end": "2026-09-20T13:30:00Z"}


def _assign(api: Api, job_id: str, technician_id: str, *, expect: int = 200) -> dict[str, Any]:
    return api.call(
        "POST", f"/jobs/{job_id}/assign", {"technician_id": technician_id}, expect=expect
    )


def _transition(
    api: Api, job_id: str, to: str, *, expect: int = 200, **extra: Any
) -> dict[str, Any]:
    return api.call("POST", f"/jobs/{job_id}/transition", {"to_status": to, **extra}, expect=expect)


def _complete(api: Api, job_id: str, *, expect: int = 200, **body: Any) -> dict[str, Any]:
    payload = {"work_performed": "Cleaned filter", **body}
    return api.call("POST", f"/jobs/{job_id}/complete", payload, expect=expect)


def _error_code(api: Api, method: str, path: str, body: dict[str, Any], status: int) -> str:
    response = api.client.request(method, f"/api/v1{path}", json=body)
    assert response.status_code == status, response.text
    return str(response.json()["error"]["code"])


class TestCreate:
    def test_creates_a_new_unassigned_job_linked_to_a_service_request(self, api: Api) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"])

        job = api.job(customer["customer_id"], asset["asset_id"], urgency="high")

        assert job["job_id"].startswith("job_")
        assert job["status"] == "NEW" and job["technician_id"] is None
        assert job["source"] == "manual" and job["urgency"] == "high"
        stored = api.repos.service_requests.get(TENANT, job["service_request_id"])
        assert stored.status is ServiceRequestStatus.JOB_CREATED
        assert stored.job_id == job["job_id"]
        actions = [
            a.action
            for a in api.repos.audits.list_for_entity(TENANT, AuditEntityType.JOB, job["job_id"])
        ]
        assert actions == [AuditAction.JOB_CREATED]

    def test_the_asset_must_belong_to_the_customer(self, api: Api) -> None:
        first, second = api.customer(name="A"), api.customer(name="B")
        asset_of_second = api.asset(second["customer_id"])

        api.job(first["customer_id"], asset_of_second["asset_id"], expect=422)

        assert api.repos.jobs.list(TENANT) == []
        assert api.repos.service_requests.list(TENANT) == []

    def test_records_of_another_business_cannot_be_referenced(self, api: Api) -> None:
        foreign_customer = make_customer(business_id=OTHER_BUSINESS_ID)
        foreign_asset = make_asset(foreign_customer)
        api.repos.customers.create(foreign_customer)
        api.repos.assets.create(foreign_asset)
        own = api.customer()
        own_asset = api.asset(own["customer_id"])

        api.job(foreign_customer.customer_id, foreign_asset.asset_id, expect=404)
        api.job(own["customer_id"], foreign_asset.asset_id, expect=404)
        api.job(foreign_customer.customer_id, own_asset["asset_id"], expect=404)

        assert api.repos.jobs.list(TENANT) == [] and api.repos.jobs.list(OTHER_BUSINESS_ID) == []

    def test_a_body_cannot_set_status_technician_or_tenant(self, api: Api) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"])

        for extra in ({"status": "COMPLETED"}, {"technician_id": "tec_x"}, {"business_id": "b"}):
            api.job(customer["customer_id"], asset["asset_id"], expect=422, **extra)

        assert api.repos.jobs.list(TENANT) == []

    def test_repeating_a_request_with_the_same_key_returns_the_original_job(self, api: Api) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"])
        path = "/jobs"
        body = {
            "customer_id": customer["customer_id"],
            "asset_id": asset["asset_id"],
            "service_type": "repair",
            "description": "AC not cooling",
        }

        first = api.client.post(f"/api/v1{path}", json=body, headers={"Idempotency-Key": "k-1"})
        second = api.client.post(f"/api/v1{path}", json=body, headers={"Idempotency-Key": "k-1"})

        assert first.status_code == 201 and second.status_code == 200
        assert second.headers["Idempotent-Replay"] == "true"
        assert first.json()["data"] == second.json()["data"]
        assert len(api.repos.jobs.list(TENANT)) == 1
        assert len(api.repos.service_requests.list(TENANT)) == 1

    def test_a_key_cannot_be_reused_for_a_different_request(self, api: Api) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"])
        api.job(customer["customer_id"], asset["asset_id"], key="k-1")

        api.job(
            customer["customer_id"],
            asset["asset_id"],
            key="k-1",
            description="Something else entirely",
            expect=409,
        )

        assert len(api.repos.jobs.list(TENANT)) == 1

    def test_without_a_key_each_call_creates_a_job_and_bad_keys_are_rejected(
        self, api: Api
    ) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"])

        api.job(customer["customer_id"], asset["asset_id"])
        api.job(customer["customer_id"], asset["asset_id"])
        api.job(customer["customer_id"], asset["asset_id"], key="bad key!", expect=422)

        assert len(api.repos.jobs.list(TENANT)) == 2

    def test_a_retry_after_a_half_finished_attempt_completes_it_without_a_duplicate(
        self, api: Api
    ) -> None:
        """The request was stored but the process died before the job was linked."""
        from app.core.ids import IdPrefix, new_id
        from app.domain.enums import ResolutionState
        from app.domain.service_request import EntityResolution, ServiceRequest
        from tests.factories import NOW

        customer = api.customer()
        asset = api.asset(customer["customer_id"])
        api.repos.service_requests.create(
            ServiceRequest(
                service_request_id=new_id(IdPrefix.SERVICE_REQUEST),
                business_id=TENANT,
                raw_text="AC not cooling",
                customer_resolution=EntityResolution(
                    state=ResolutionState.EXISTING, entity_id=customer["customer_id"]
                ),
                asset_resolution=EntityResolution(
                    state=ResolutionState.EXISTING, entity_id=asset["asset_id"]
                ),
                idempotency_key="crashed-1",
                created_at=NOW,
                updated_at=NOW,
            )
        )

        job = api.job(customer["customer_id"], asset["asset_id"], key="crashed-1")

        assert job["status"] == "NEW"
        assert len(api.repos.jobs.list(TENANT)) == 1
        assert len(api.repos.service_requests.list(TENANT)) == 1


class TestReadAndAmend:
    def test_the_job_card_carries_what_a_technician_needs(self, api: Api) -> None:
        setup = api.in_progress_job()
        job_id = setup["job"]["job_id"]

        card = api.call("GET", f"/jobs/{job_id}", expect=200)

        assert card["job"]["status"] == "IN_PROGRESS"
        assert card["customer"]["customer_id"] == setup["customer"]["customer_id"]
        assert card["asset"]["asset_id"] == setup["asset"]["asset_id"]
        assert card["technician"]["technician_id"] == setup["technician"]["technician_id"]
        assert card["prior_service"] == []

    def test_a_job_of_another_business_is_unreachable_through_every_endpoint(
        self, api: Api
    ) -> None:
        foreign_ctx = make_ctx(OTHER_BUSINESS_ID)
        customer = make_customer(business_id=OTHER_BUSINESS_ID)
        asset = make_asset(customer)
        api.repos.customers.create(customer)
        api.repos.assets.create(asset)
        change = create_job(
            foreign_ctx,
            customer=customer,
            asset=asset,
            service_type=ServiceType.REPAIR,
            description="Someone else's job",
            now=NOW,
        )
        api.repos.jobs.create(change.job, change.audit)
        job_id = change.job.job_id
        own_technician = api.technician()["technician_id"]

        api.call("GET", f"/jobs/{job_id}", expect=404)
        api.call("PATCH", f"/jobs/{job_id}", {"urgency": "low"}, expect=404)
        api.call("POST", f"/jobs/{job_id}/assign", {"technician_id": own_technician}, expect=404)
        api.call("POST", f"/jobs/{job_id}/transition", {"to_status": "CANCELLED"}, expect=404)
        api.call("POST", f"/jobs/{job_id}/complete", {"work_performed": "x"}, expect=404)
        assert api.call("GET", "/jobs", expect=200) == []
        untouched = api.repos.jobs.get(OTHER_BUSINESS_ID, job_id)
        assert untouched.status is JobStatus.NEW and untouched.version == 1

    def test_list_filters_by_status_and_technician(self, api: Api) -> None:
        setup = api.in_progress_job()
        customer_id, asset_id = setup["customer"]["customer_id"], setup["asset"]["asset_id"]
        idle = api.job(customer_id, asset_id, description="Second call")

        everything = api.call("GET", "/jobs", expect=200)
        new = api.call("GET", "/jobs?status=NEW", expect=200)
        mine = api.call(
            "GET", f"/jobs?technician_id={setup['technician']['technician_id']}", expect=200
        )

        assert [j["job_id"] for j in everything] == [idle["job_id"], setup["job"]["job_id"]]
        assert [j["job_id"] for j in new] == [idle["job_id"]]
        assert [j["job_id"] for j in mine] == [setup["job"]["job_id"]]

    def test_patch_changes_only_description_urgency_and_preferred_slot(self, api: Api) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"])
        job = api.job(customer["customer_id"], asset["asset_id"])

        patched = api.call(
            "PATCH",
            f"/jobs/{job['job_id']}",
            {"urgency": "high", "preferred_slot": SLOT},
            expect=200,
        )

        assert patched["urgency"] == "high" and patched["description"] == job["description"]
        assert patched["preferred_slot"]["start"].startswith("2026-09-20T11:30")
        assert patched["status"] == "NEW" and patched["version"] == job["version"] + 1
        actions = [
            a.action
            for a in api.repos.audits.list_for_entity(TENANT, AuditEntityType.JOB, job["job_id"])
        ]
        assert actions[-1] is AuditAction.JOB_AMENDED

    @pytest.mark.parametrize(
        "body",
        [
            {"status": "COMPLETED"},
            {"status": "IN_PROGRESS"},
            {"technician_id": "tec_x"},
            {"scheduled_slot": SLOT},
            {"completed_at": "2026-09-20T11:30:00Z"},
            {"description": None},
            {},
        ],
    )
    def test_patch_cannot_change_status_technician_schedule_or_completion(
        self, api: Api, body: dict[str, Any]
    ) -> None:
        setup = api.in_progress_job()
        job_id = setup["job"]["job_id"]

        api.call("PATCH", f"/jobs/{job_id}", body, expect=422)

        assert api.repos.jobs.get(TENANT, job_id).status is JobStatus.IN_PROGRESS

    def test_a_closed_job_cannot_be_amended(self, api: Api) -> None:
        setup = api.in_progress_job()
        job_id = setup["job"]["job_id"]
        _transition(api, job_id, "CANCELLED")

        api.call("PATCH", f"/jobs/{job_id}", {"urgency": "low"}, expect=409)


class TestAssignment:
    def test_assigning_a_new_job_makes_it_assigned_and_is_audited(self, api: Api) -> None:
        customer = api.customer()
        job = api.job(customer["customer_id"], api.asset(customer["customer_id"])["asset_id"])
        technician = api.technician()

        assigned = _assign(api, job["job_id"], technician["technician_id"])

        assert assigned["status"] == "ASSIGNED"
        assert assigned["technician_id"] == technician["technician_id"]
        actions = [
            a.action
            for a in api.repos.audits.list_for_entity(TENANT, AuditEntityType.JOB, job["job_id"])
        ]
        assert actions == [AuditAction.JOB_CREATED, AuditAction.JOB_ASSIGNED]

    def test_reassignment_does_not_change_the_status(self, api: Api) -> None:
        customer = api.customer()
        job = api.job(customer["customer_id"], api.asset(customer["customer_id"])["asset_id"])
        first, second = api.technician(name="First"), api.technician(name="Second")
        _assign(api, job["job_id"], first["technician_id"])
        _transition(api, job["job_id"], "SCHEDULED", scheduled_slot=SLOT)

        reassigned = _assign(api, job["job_id"], second["technician_id"])

        assert reassigned["status"] == "SCHEDULED"
        assert reassigned["technician_id"] == second["technician_id"]

    def test_only_active_technicians_of_this_business_can_be_assigned(self, api: Api) -> None:
        customer = api.customer()
        job = api.job(customer["customer_id"], api.asset(customer["customer_id"])["asset_id"])
        inactive = make_technician(business_id=TENANT, active=False)
        foreign = make_technician(business_id=OTHER_BUSINESS_ID)
        api.repos.technicians.create(inactive)
        api.repos.technicians.create(foreign)

        _assign(api, job["job_id"], inactive.technician_id, expect=422)
        _assign(api, job["job_id"], foreign.technician_id, expect=404)
        _assign(api, job["job_id"], "tec_doesnotexist", expect=404)

        assert api.repos.jobs.get(TENANT, job["job_id"]).technician_id is None

    def test_assigning_the_same_technician_again_or_once_work_started_is_rejected(
        self, api: Api
    ) -> None:
        setup = api.in_progress_job()
        job_id = setup["job"]["job_id"]
        other = api.technician(name="Other")

        _assign(api, job_id, other["technician_id"], expect=409)  # IN_PROGRESS

        customer_id = setup["customer"]["customer_id"]
        new_job = api.job(customer_id, setup["asset"]["asset_id"])
        _assign(api, new_job["job_id"], other["technician_id"])
        _assign(api, new_job["job_id"], other["technician_id"], expect=422)


class TestTransitions:
    def _assigned(self, api: Api) -> str:
        customer = api.customer()
        job = api.job(customer["customer_id"], api.asset(customer["customer_id"])["asset_id"])
        _assign(api, job["job_id"], api.technician()["technician_id"])
        return str(job["job_id"])

    def test_progression_can_skip_scheduled_and_on_the_way(self, api: Api) -> None:
        job_id = self._assigned(api)

        started = _transition(api, job_id, "IN_PROGRESS")

        assert started["status"] == "IN_PROGRESS"

    def test_the_full_progression_is_allowed_and_audited(self, api: Api) -> None:
        job_id = self._assigned(api)

        scheduled = _transition(api, job_id, "SCHEDULED", scheduled_slot=SLOT)
        _transition(api, job_id, "ON_THE_WAY")
        _transition(api, job_id, "IN_PROGRESS")

        assert scheduled["scheduled_slot"]["end"].startswith("2026-09-20T13:30")
        changes = [
            (a.metadata["from"], a.metadata["to"])
            for a in api.repos.audits.list_for_entity(TENANT, AuditEntityType.JOB, job_id)
            if a.action is AuditAction.JOB_STATUS_CHANGED
        ]
        assert changes == [
            ("ASSIGNED", "SCHEDULED"),
            ("SCHEDULED", "ON_THE_WAY"),
            ("ON_THE_WAY", "IN_PROGRESS"),
        ]

    def test_scheduling_needs_a_slot_and_a_slot_needs_scheduling(self, api: Api) -> None:
        job_id = self._assigned(api)

        _transition(api, job_id, "SCHEDULED", expect=422)
        _transition(api, job_id, "ON_THE_WAY", expect=422, scheduled_slot=SLOT)

    @pytest.mark.parametrize("target", ["COMPLETED", "ASSIGNED", "NEW"])
    def test_illegal_targets_are_refused_with_a_state_error(self, api: Api, target: str) -> None:
        job_id = self._assigned(api)

        code = _error_code(api, "POST", f"/jobs/{job_id}/transition", {"to_status": target}, 409)

        assert code == "INVALID_STATE_TRANSITION"
        assert api.repos.jobs.get(TENANT, job_id).status is JobStatus.ASSIGNED

    def test_a_new_job_cannot_skip_assignment_and_progress_is_forward_only(self, api: Api) -> None:
        customer = api.customer()
        job = api.job(customer["customer_id"], api.asset(customer["customer_id"])["asset_id"])
        _transition(api, job["job_id"], "IN_PROGRESS", expect=409)

        job_id = self._assigned(api)
        _transition(api, job_id, "IN_PROGRESS")
        _transition(api, job_id, "ON_THE_WAY", expect=409)

    def test_cancellation_is_terminal(self, api: Api) -> None:
        job_id = self._assigned(api)

        cancelled = _transition(api, job_id, "CANCELLED")
        _transition(api, job_id, "IN_PROGRESS", expect=409)

        assert cancelled["status"] == "CANCELLED"
        _complete(api, job_id, expect=409)


class TestCompletion:
    def test_completion_stores_job_event_and_audit_together(self, api: Api) -> None:
        setup = api.in_progress_job()
        job_id = setup["job"]["job_id"]

        result = _complete(
            api,
            job_id,
            technician_notes="Customer advised to monitor cooling",
            parts_used=["filter"],
            observed_symptoms=["not cooling"],
        )

        assert result["job"]["status"] == "COMPLETED" and result["job"]["completed_at"]
        event = result["service_event"]
        assert event["job_id"] == job_id
        assert event["asset_id"] == setup["asset"]["asset_id"]
        assert event["technician_id"] == setup["technician"]["technician_id"]
        assert event["parts_used"] == ["filter"]
        assert event["summary"] == "Reported: AC not cooling | Work performed: Cleaned filter"
        stored_event = api.repos.service_events.get(TENANT, event["event_id"])
        assert stored_event.job_id == job_id
        audits = api.repos.audits.list_for_entity(TENANT, AuditEntityType.JOB, job_id)
        completed = [a for a in audits if a.action is AuditAction.JOB_COMPLETED]
        assert [a.metadata["service_event_id"] for a in completed] == [event["event_id"]]

    @pytest.mark.parametrize("stop_at", ["NEW", "ASSIGNED", "SCHEDULED", "CANCELLED"])
    def test_only_an_in_progress_job_can_be_completed(self, api: Api, stop_at: str) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"])
        job = api.job(customer["customer_id"], asset["asset_id"])
        if stop_at != "NEW":
            _assign(api, job["job_id"], api.technician()["technician_id"])
        if stop_at == "SCHEDULED":
            _transition(api, job["job_id"], "SCHEDULED", scheduled_slot=SLOT)
        if stop_at == "CANCELLED":
            _transition(api, job["job_id"], "CANCELLED")

        code = _error_code(
            api, "POST", f"/jobs/{job['job_id']}/complete", {"work_performed": "Fixed"}, 409
        )

        assert code == "INVALID_STATE_TRANSITION"
        assert api.repos.service_events.list_by_asset(TENANT, asset["asset_id"]) == []

    def test_a_job_cannot_be_completed_twice(self, api: Api) -> None:
        setup = api.in_progress_job()
        job_id = setup["job"]["job_id"]
        _complete(api, job_id)

        _complete(api, job_id, expect=409)

        events = api.repos.service_events.list_by_asset(TENANT, setup["asset"]["asset_id"])
        assert len(events) == 1

    def test_attachments_are_refused_until_they_exist_and_nothing_is_written(
        self, api: Api
    ) -> None:
        setup = api.in_progress_job()
        job_id = setup["job"]["job_id"]

        _complete(api, job_id, expect=422, attachment_ids=["att_notreal"])

        assert api.repos.jobs.get(TENANT, job_id).status is JobStatus.IN_PROGRESS
        assert api.repos.service_events.list_by_asset(TENANT, setup["asset"]["asset_id"]) == []

    def test_work_performed_is_required_and_unknown_fields_are_refused(self, api: Api) -> None:
        job_id = api.in_progress_job()["job"]["job_id"]

        api.call("POST", f"/jobs/{job_id}/complete", {}, expect=422)
        api.call("POST", f"/jobs/{job_id}/complete", {"work_performed": " "}, expect=422)
        _complete(api, job_id, expect=422, status="COMPLETED", business_id="bus_x")

    def test_completion_is_the_only_route_to_completed(self, api: Api) -> None:
        job_id = api.in_progress_job()["job"]["job_id"]

        api.call("POST", f"/jobs/{job_id}/transition", {"to_status": "COMPLETED"}, expect=409)
        api.call("PATCH", f"/jobs/{job_id}", {"status": "COMPLETED"}, expect=422)
        assert api.repos.jobs.get(TENANT, job_id).status is JobStatus.IN_PROGRESS

        _complete(api, job_id)
        assert api.repos.jobs.get(TENANT, job_id).status is JobStatus.COMPLETED


class TestHistory:
    def _finish(self, api: Api, customer_id: str, asset_id: str, technician_id: str, work: str):
        job = api.job(customer_id, asset_id, description=f"Problem: {work}")
        _assign(api, job["job_id"], technician_id)
        _transition(api, job["job_id"], "IN_PROGRESS")
        return _complete(api, job["job_id"], work_performed=work)

    def test_asset_history_lists_recorded_service_newest_first(self, api: Api) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"])
        other_asset = api.asset(customer["customer_id"], brand="Samsung")
        technician = api.technician()
        first = self._finish(
            api,
            customer["customer_id"],
            asset["asset_id"],
            technician["technician_id"],
            "Filter cleaned",
        )
        second = self._finish(
            api,
            customer["customer_id"],
            asset["asset_id"],
            technician["technician_id"],
            "Gas refilled",
        )
        self._finish(
            api,
            customer["customer_id"],
            other_asset["asset_id"],
            technician["technician_id"],
            "Unrelated",
        )

        history = api.call("GET", f"/assets/{asset['asset_id']}/history", expect=200)

        assert [e["event_id"] for e in history["service_events"]] == [
            second["service_event"]["event_id"],
            first["service_event"]["event_id"],
        ]
        assert len(history["jobs"]) == 2
        assert history["asset"]["asset_id"] == asset["asset_id"]
        assert [e["work_performed"] for e in history["service_events"]] == [
            "Gas refilled",
            "Filter cleaned",
        ]

    def test_customer_history_spans_their_assets(self, api: Api) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"])
        other_asset = api.asset(customer["customer_id"], brand="Samsung")
        technician = api.technician()
        self._finish(
            api, customer["customer_id"], asset["asset_id"], technician["technician_id"], "A"
        )
        self._finish(
            api, customer["customer_id"], other_asset["asset_id"], technician["technician_id"], "B"
        )

        history = api.call("GET", f"/customers/{customer['customer_id']}/history", expect=200)

        assert {a["asset_id"] for a in history["assets"]} == {
            asset["asset_id"],
            other_asset["asset_id"],
        }
        assert len(history["service_events"]) == 2 and len(history["jobs"]) == 2

    def test_the_job_card_shows_previous_service_but_not_the_jobs_own(self, api: Api) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"])
        technician = api.technician()
        previous = self._finish(
            api,
            customer["customer_id"],
            asset["asset_id"],
            technician["technician_id"],
            "Gas refilled",
        )
        repeat = api.job(
            customer["customer_id"], asset["asset_id"], description="AC again not cooling"
        )

        card = api.call("GET", f"/jobs/{repeat['job_id']}", expect=200)

        assert [e["event_id"] for e in card["prior_service"]] == [
            previous["service_event"]["event_id"]
        ]
        assert card["prior_service"][0]["work_performed"] == "Gas refilled"

    def test_history_of_another_business_is_not_reachable(self, api: Api) -> None:
        foreign_customer = make_customer(business_id=OTHER_BUSINESS_ID)
        foreign_asset = make_asset(foreign_customer)
        api.repos.customers.create(foreign_customer)
        api.repos.assets.create(foreign_asset)

        api.call("GET", f"/assets/{foreign_asset.asset_id}/history", expect=404)
        api.call("GET", f"/customers/{foreign_customer.customer_id}/history", expect=404)
