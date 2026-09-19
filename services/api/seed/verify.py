"""Read-only inspection of a seeded business: a canonical snapshot (for exact comparison) and the
checks that prove each demo scenario is really present in the data.

Everything is read through the repository ports, so it works the same against memory, DynamoDB
Local and the deployed table. Nothing here writes.
"""

import hashlib
import json
from typing import Any

from app.domain.enums import (
    AuditAction,
    AuditEntityType,
    JobSource,
    JobStatus,
    ResolutionState,
    ServiceRequestStatus,
    Urgency,
)
from app.domain.repositories import Repositories

Check = tuple[str, bool, str]
_LIMIT = 500

_EXPECTED_AUDITS: dict[JobStatus, list[AuditAction]] = {
    JobStatus.NEW: [AuditAction.JOB_CREATED],
    JobStatus.ASSIGNED: [AuditAction.JOB_CREATED, AuditAction.JOB_ASSIGNED],
    JobStatus.SCHEDULED: [
        AuditAction.JOB_CREATED,
        AuditAction.JOB_ASSIGNED,
        AuditAction.JOB_STATUS_CHANGED,
    ],
    JobStatus.ON_THE_WAY: [
        AuditAction.JOB_CREATED,
        AuditAction.JOB_ASSIGNED,
        AuditAction.JOB_STATUS_CHANGED,
        AuditAction.JOB_STATUS_CHANGED,
    ],
    JobStatus.IN_PROGRESS: [
        AuditAction.JOB_CREATED,
        AuditAction.JOB_ASSIGNED,
        AuditAction.JOB_STATUS_CHANGED,
    ],
    JobStatus.COMPLETED: [
        AuditAction.JOB_CREATED,
        AuditAction.JOB_ASSIGNED,
        AuditAction.JOB_STATUS_CHANGED,
        AuditAction.JOB_COMPLETED,
    ],
    JobStatus.CANCELLED: [
        AuditAction.JOB_CREATED,
        AuditAction.JOB_ASSIGNED,
        AuditAction.JOB_STATUS_CHANGED,
    ],
}


def snapshot(repos: Repositories, business_id: str) -> dict[str, list[dict[str, Any]]]:
    """Every record of the business, as sorted plain data (audit trails included)."""

    def dump(models: list[Any], key: str) -> list[dict[str, Any]]:
        rows = [m.model_dump(mode="json") for m in models]
        return sorted(rows, key=lambda row: str(row[key]))

    customers = repos.customers.list(business_id, limit=_LIMIT)
    assets = [
        a for c in customers for a in repos.assets.list_by_customer(business_id, c.customer_id)
    ]
    technicians = repos.technicians.list(business_id)
    requests = repos.service_requests.list(business_id, limit=_LIMIT)
    jobs = repos.jobs.list(business_id, limit=_LIMIT)
    events = [
        e
        for a in assets
        for e in repos.service_events.list_by_asset(business_id, a.asset_id, limit=_LIMIT)
    ]
    audits = [
        audit
        for kind, entity_ids in (
            (AuditEntityType.TECHNICIAN, [t.technician_id for t in technicians]),
            (AuditEntityType.CUSTOMER, [c.customer_id for c in customers]),
            (AuditEntityType.ASSET, [a.asset_id for a in assets]),
            (AuditEntityType.SERVICE_REQUEST, [r.service_request_id for r in requests]),
            (AuditEntityType.JOB, [j.job_id for j in jobs]),
        )
        for entity_id in entity_ids
        for audit in repos.audits.list_for_entity(business_id, kind, entity_id)
    ]
    return {
        "businesses": dump([repos.businesses.get(business_id)], "business_id"),
        "technicians": dump(technicians, "technician_id"),
        "customers": dump(customers, "customer_id"),
        "assets": dump(assets, "asset_id"),
        "service_requests": dump(requests, "service_request_id"),
        "jobs": dump(jobs, "job_id"),
        "service_events": dump(events, "event_id"),
        "audits": dump(audits, "audit_id"),
    }


def _canonical(value: Any) -> Any:
    """Compare numbers by value: DynamoDB has one number type, so it stores ``0.0`` as ``0``."""
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def digest(data: dict[str, list[dict[str, Any]]]) -> str:
    """A stable fingerprint of a snapshot: equal datasets have equal digests, whichever
    persistence adapter they were stored in."""
    canonical = json.dumps(
        _canonical(data), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def counts(data: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {kind: len(rows) for kind, rows in data.items()}


def check_demo_data(repos: Repositories, business_id: str, manifest: dict[str, Any]) -> list[Check]:
    """Verify the dataset and each demo scenario against what is actually stored."""
    results: list[Check] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))

    ids = manifest
    customers = repos.customers.list(business_id, limit=_LIMIT)
    assets_by_customer = {
        c.customer_id: repos.assets.list_by_customer(business_id, c.customer_id) for c in customers
    }
    assets = [a for owned in assets_by_customer.values() for a in owned]
    technicians = repos.technicians.list(business_id)
    requests = repos.service_requests.list(business_id, limit=_LIMIT)
    jobs = repos.jobs.list(business_id, limit=_LIMIT)
    events = [
        e
        for a in assets
        for e in repos.service_events.list_by_asset(business_id, a.asset_id, limit=_LIMIT)
    ]

    # -- the dataset as a whole -------------------------------------------------------------------
    expected = {
        "technicians": (len(technicians), len(ids["technicians"])),
        "customers": (len(customers), len(ids["customers"])),
        "assets": (len(assets), len(ids["assets"])),
        "service requests": (len(requests), len(ids["service_requests"])),
        "jobs": (len(jobs), len(ids["jobs"])),
        "service events": (len(events), len(ids["events"])),
    }
    for kind, (found, wanted) in expected.items():
        check(f"{wanted} {kind}", found == wanted, f"found {found}")
    status_counts = {s.value: sum(1 for j in jobs if j.status is s) for s in JobStatus}
    wanted_status = {s.value: manifest["job_status_counts"].get(s.value, 0) for s in JobStatus}
    check("jobs in every status", status_counts == wanted_status, str(status_counts))

    # -- 1. repeat AC complaint with service history --------------------------------------------
    lg = ids["assets"]["ravi_lg_ac"]
    history = repos.service_events.list_by_asset(business_id, lg, limit=_LIMIT)
    check(
        "repeat AC: the LG AC has two recorded services, newest first",
        [e.event_id for e in history]
        == [ids["events"]["gas_refill_ravi_lg_ac"], ids["events"]["annual_service_ravi_lg_ac"]],
        f"{len(history)} events",
    )
    check(
        "repeat AC: its refill record states only what was recorded",
        bool(history)
        and history[0].work_performed == "Gas pressure checked and refrigerant refilled",
    )
    fridge_history = repos.service_events.list_by_asset(
        business_id, ids["assets"]["ravi_samsung_fridge"]
    )
    check("repeat AC: the fridge's history is separate", len(fridge_history) == 1)
    phone_hits = repos.customers.find_by_phone(business_id, "90000 20001")
    check(
        "repeat AC: the customer is found from their phone number",
        [c.customer_id for c in phone_hits] == [ids["customers"]["ravi_kumar"]],
    )

    # -- 2. multiple assets per customer --------------------------------------------------------
    owned = {key: len(assets_by_customer.get(cid, [])) for key, cid in ids["customers"].items()}
    check(
        "multiple assets: Meena 4, Ravi Kumar 2, Gopal 2",
        (owned.get("meena_iyer"), owned.get("ravi_kumar"), owned.get("gopal_reddy")) == (4, 2, 2),
        str(owned),
    )
    meena_acs = [
        a
        for a in assets_by_customer.get(ids["customers"]["meena_iyer"], [])
        if a.asset_type.value == "air_conditioner"
    ]
    check("multiple assets: Meena has two air conditioners (brand decides)", len(meena_acs) == 2)
    ravis = repos.customers.search_by_name(business_id, "ravi")
    check(
        "multiple assets: 'Ravi' matches two customers",
        len(ravis) == 2,
        str([c.name for c in ravis]),
    )

    # -- 3. new customer requiring review -------------------------------------------------------
    review = [r for r in requests if r.status is ServiceRequestStatus.NEEDS_REVIEW]
    check(
        "new customer: exactly one request awaits review",
        [r.service_request_id for r in review] == [ids["service_requests"]["new_customer_deepak"]],
    )
    if review:
        request = review[0]
        check(
            "new customer: customer and asset are NEW, and no job exists",
            request.customer_resolution.state is ResolutionState.NEW
            and request.asset_resolution.state is ResolutionState.NEW
            and request.job_id is None,
        )
    check(
        "new customer: their phone number is unknown to the business",
        repos.customers.find_by_phone(business_id, "90000 29999") == [],
    )

    # -- 4. safety-critical request -------------------------------------------------------------
    urgent = [j for j in jobs if j.urgency is Urgency.SAFETY_CRITICAL]
    check(
        "safety: exactly one safety-critical job, from intake, waiting unassigned",
        [j.job_id for j in urgent] == [ids["jobs"]["fridge_burning_smell_farhan"]]
        and urgent[0].source is JobSource.INTAKE
        and urgent[0].status is JobStatus.NEW
        and urgent[0].technician_id is None,
    )
    if urgent and urgent[0].service_request_id in {r.service_request_id for r in requests}:
        linked = repos.service_requests.get(business_id, urgent[0].service_request_id or "")
        flagged = bool((linked.extraction or {}).get("safety_concern"))
        check("safety: its request records the safety concern", flagged)
        check(
            "safety: the job holds the customer's report, not a diagnosis",
            urgent[0].description == "Refrigerator has a burning smell and sparks",
        )
    else:
        check("safety: its request records the safety concern", False, "request missing")

    # -- 5. technician and job lifecycle --------------------------------------------------------
    inactive = [t for t in technicians if not t.active]
    check(
        "lifecycle: one inactive technician, with no jobs",
        len(inactive) == 1 and all(j.technician_id != inactive[0].technician_id for j in jobs),
    )
    unassigned_but_needs_technician = [
        j for j in jobs if j.status not in (JobStatus.NEW,) and j.technician_id is None
    ]
    check("lifecycle: every job past NEW has a technician", not unassigned_but_needs_technician)

    # -- integrity across all records -----------------------------------------------------------
    request_by_id = {r.service_request_id: r for r in requests}
    linked_ok = all(
        j.service_request_id in request_by_id
        and request_by_id[j.service_request_id].status is ServiceRequestStatus.JOB_CREATED
        and request_by_id[j.service_request_id].job_id == j.job_id
        for j in jobs
    )
    check("integrity: every job is linked to the request it came from", linked_ok)

    bad_trails: list[str] = []
    for job in jobs:
        trail = [
            a.action
            for a in repos.audits.list_for_entity(business_id, AuditEntityType.JOB, job.job_id)
        ]
        if trail != _EXPECTED_AUDITS[job.status]:
            bad_trails.append(f"{job.job_id}: {[a.value for a in trail]}")
    check(
        "integrity: each job's audit trail matches its status",
        not bad_trails,
        "; ".join(bad_trails),
    )

    completed = [j for j in jobs if j.status is JobStatus.COMPLETED]
    event_by_job = {e.job_id: e for e in events}
    recorded = all(
        j.job_id in event_by_job and j.completed_at == event_by_job[j.job_id].timestamp
        for j in completed
    )
    check(
        "integrity: every completed job has exactly one service event, and no other job has one",
        recorded and len(events) == len(completed),
    )
    fictional = all((c.phone or "").startswith("+919000") for c in customers) and all(
        (t.phone or "").startswith("+919000") for t in technicians
    )
    check("privacy: every phone number is a fictional 90000 number", fictional)
    return results
