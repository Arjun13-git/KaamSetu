"""ServiceRequest reads and confirm-to-job (the manual path a person takes when AI cannot help)."""

from typing import Any

from app.domain.enums import JobSource, ResolutionState, ServiceRequestStatus
from app.domain.service_request import EntityResolution, MatchCandidate, ServiceRequest
from tests.api_support import TENANT, Api
from tests.factories import OTHER_BUSINESS_ID, make_asset, make_customer, make_service_request

SLOT = {"start": "2026-09-20T11:30:00Z"}


def _stored(api: Api, **overrides: Any) -> ServiceRequest:
    request = make_service_request(business_id=TENANT, **overrides)
    api.repos.service_requests.create(request)
    return request


def _confirm(api: Api, request_id: str, body: dict[str, Any], *, expect: int) -> dict[str, Any]:
    return api.call("POST", f"/service-requests/{request_id}/job", body, expect=expect)


class TestReading:
    def test_get_returns_the_preserved_request_without_tenant_details(self, api: Api) -> None:
        request = _stored(api, raw_text="Bhaiya LG AC thanda nahi kar raha")

        found = api.call("GET", f"/service-requests/{request.service_request_id}", expect=200)

        assert found["raw_text"] == "Bhaiya LG AC thanda nahi kar raha"
        assert found["status"] == "RECEIVED"
        assert found["customer_resolution"]["state"] == "unresolved"
        assert "business_id" not in found and "idempotency_key" not in found

    def test_list_filters_by_status_and_is_scoped_to_the_business(self, api: Api) -> None:
        waiting = _stored(api, status=ServiceRequestStatus.NEEDS_REVIEW)
        _stored(api, status=ServiceRequestStatus.EXTRACTION_FAILED, failure_reason="AI_UNAVAILABLE")
        api.repos.service_requests.create(make_service_request(business_id=OTHER_BUSINESS_ID))

        everything = api.call("GET", "/service-requests", expect=200)
        review = api.call("GET", "/service-requests?status=NEEDS_REVIEW", expect=200)

        assert len(everything) == 2
        assert [r["service_request_id"] for r in review] == [waiting.service_request_id]

    def test_a_request_of_another_business_is_not_found(self, api: Api) -> None:
        foreign = make_service_request(business_id=OTHER_BUSINESS_ID)
        api.repos.service_requests.create(foreign)

        api.call("GET", f"/service-requests/{foreign.service_request_id}", expect=404)
        _confirm(
            api,
            foreign.service_request_id,
            {"customer_id": "cus_x", "asset_id": "ast_x"},
            expect=404,
        )


class TestConfirmJob:
    def _customer_and_asset(self, api: Api) -> tuple[str, str]:
        customer = api.customer()
        return customer["customer_id"], api.asset(customer["customer_id"])["asset_id"]

    def test_a_person_can_turn_a_failed_request_into_a_job(self, api: Api) -> None:
        customer_id, asset_id = self._customer_and_asset(api)
        request = _stored(
            api,
            raw_text="AC not cooling since yesterday",
            status=ServiceRequestStatus.EXTRACTION_FAILED,
            failure_reason="AI_UNAVAILABLE",
        )

        job = _confirm(
            api,
            request.service_request_id,
            {"customer_id": customer_id, "asset_id": asset_id, "service_type": "repair"},
            expect=201,
        )

        assert job["description"] == "AC not cooling since yesterday"  # the customer's own words
        assert job["service_type"] == "repair" and job["status"] == "NEW"
        assert job["source"] == JobSource.MANUAL.value
        assert job["service_request_id"] == request.service_request_id
        stored = api.repos.service_requests.get(TENANT, request.service_request_id)
        assert stored.status is ServiceRequestStatus.JOB_CREATED and stored.job_id == job["job_id"]
        assert stored.customer_resolution.state is ResolutionState.EXISTING
        assert stored.customer_resolution.entity_id == customer_id

    def test_evidence_shown_to_the_person_is_kept_when_they_decide(self, api: Api) -> None:
        customer_id, asset_id = self._customer_and_asset(api)
        candidates = [
            MatchCandidate(entity_id=customer_id, match_score=0.5, reasons=["name contains Ravi"]),
            MatchCandidate(entity_id="cus_other", match_score=0.5, reasons=["name contains Ravi"]),
        ]
        request = _stored(
            api,
            status=ServiceRequestStatus.NEEDS_REVIEW,
            customer_resolution=EntityResolution(
                state=ResolutionState.AMBIGUOUS, candidates=candidates
            ),
        )

        _confirm(
            api,
            request.service_request_id,
            {"customer_id": customer_id, "asset_id": asset_id},
            expect=201,
        )

        stored = api.repos.service_requests.get(TENANT, request.service_request_id)
        assert stored.customer_resolution.state is ResolutionState.EXISTING
        assert [c.entity_id for c in stored.customer_resolution.candidates] == [
            customer_id,
            "cus_other",
        ]

    def test_confirming_again_returns_the_same_job_and_creates_nothing(self, api: Api) -> None:
        customer_id, asset_id = self._customer_and_asset(api)
        request = _stored(api)
        body = {"customer_id": customer_id, "asset_id": asset_id}

        first = api.client.post(
            f"/api/v1/service-requests/{request.service_request_id}/job", json=body
        )
        second = api.client.post(
            f"/api/v1/service-requests/{request.service_request_id}/job", json=body
        )

        assert (first.status_code, second.status_code) == (201, 200)
        assert first.json()["data"]["job_id"] == second.json()["data"]["job_id"]
        assert len(api.repos.jobs.list(TENANT)) == 1

    def test_a_dismissed_request_cannot_start_a_job(self, api: Api) -> None:
        customer_id, asset_id = self._customer_and_asset(api)
        request = _stored(api, status=ServiceRequestStatus.DISMISSED)

        _confirm(
            api,
            request.service_request_id,
            {"customer_id": customer_id, "asset_id": asset_id},
            expect=409,
        )

        assert api.repos.jobs.list(TENANT) == []

    def test_the_chosen_records_must_exist_in_this_business_and_belong_together(
        self, api: Api
    ) -> None:
        customer_id, asset_id = self._customer_and_asset(api)
        other = api.customer(name="Someone Else")
        foreign_customer = make_customer(business_id=OTHER_BUSINESS_ID)
        foreign_asset = make_asset(foreign_customer)
        api.repos.customers.create(foreign_customer)
        api.repos.assets.create(foreign_asset)
        request = _stored(api)
        path = request.service_request_id

        _confirm(
            api,
            path,
            {"customer_id": foreign_customer.customer_id, "asset_id": asset_id},
            expect=404,
        )
        _confirm(
            api, path, {"customer_id": customer_id, "asset_id": foreign_asset.asset_id}, expect=404
        )
        _confirm(api, path, {"customer_id": other["customer_id"], "asset_id": asset_id}, expect=422)

        assert api.repos.jobs.list(TENANT) == []
        stored = api.repos.service_requests.get(TENANT, request.service_request_id)
        assert stored.status is ServiceRequestStatus.RECEIVED

    def test_overrides_are_used_and_a_long_request_needs_a_description(self, api: Api) -> None:
        customer_id, asset_id = self._customer_and_asset(api)
        long_request = _stored(api, raw_text="x" * 2500)
        short_request = _stored(api, raw_text="short")

        _confirm(
            api,
            long_request.service_request_id,
            {"customer_id": customer_id, "asset_id": asset_id},
            expect=422,
        )
        job = _confirm(
            api,
            short_request.service_request_id,
            {
                "customer_id": customer_id,
                "asset_id": asset_id,
                "description": "Reviewed wording",
                "urgency": "high",
                "preferred_slot": SLOT,
            },
            expect=201,
        )

        assert job["description"] == "Reviewed wording" and job["urgency"] == "high"
        assert job["preferred_slot"]["start"].startswith("2026-09-20T11:30")

    def test_the_body_cannot_carry_status_or_tenant_fields(self, api: Api) -> None:
        customer_id, asset_id = self._customer_and_asset(api)
        request = _stored(api)

        for extra in (
            {"status": "COMPLETED"},
            {"business_id": "bus_x"},
            {"technician_id": "tec_x"},
        ):
            _confirm(
                api,
                request.service_request_id,
                {"customer_id": customer_id, "asset_id": asset_id, **extra},
                expect=422,
            )
