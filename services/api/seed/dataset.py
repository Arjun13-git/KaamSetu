"""The KaamSetu demo dataset, built entirely in memory.

Everything here is fictional: names, phone numbers (``90000 xxxxx``), addresses and messages.
Every record goes through the same domain workflow the API uses (create, assign, transition,
complete, the ServiceRequest-to-job link), so the data obeys every invariant by construction. Times
are offsets from one fixed ``as_of`` instant and ids come from ``readable_ids``, so the plan is
identical on every run.

Five demo scenarios are built in (see ``SCENARIOS``):

1. a repeat AC complaint with recorded service history
2. a customer with several assets (two of them air conditioners)
3. a new customer whose request needs review
4. a safety-critical request
5. technician and job lifecycle across every job status
"""

import datetime as dt
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.ai.schemas import (
    AssetMention,
    Confidence,
    IntakeExtraction,
    Intent,
    ProblemMention,
    Source,
    StoredExtraction,
    TimePreference,
)
from app.core.context import Actor, RequestContext
from app.domain.asset import Asset
from app.domain.audit import AuditEvent, build_audit
from app.domain.business import Business
from app.domain.customer import Customer
from app.domain.enums import (
    AssetType,
    AuditAction,
    AuditEntityType,
    JobSource,
    JobStatus,
    ResolutionState,
    ServiceRequestStatus,
    ServiceType,
    Urgency,
)
from app.domain.job import TimeSlot
from app.domain.job_workflow import (
    JobCompletion,
    assign_job,
    complete_job,
    create_job,
    transition_job,
)
from app.domain.service_request import EntityResolution, MatchCandidate, ServiceRequest
from app.domain.technician import Technician
from seed.determinism import readable_ids
from seed.plan import (
    Op,
    advance_job,
    append_audit,
    create_job_from_request,
    create_record,
    update_request,
)
from seed.plan import (
    complete_job as complete_job_op,
)

DEFAULT_AS_OF = datetime(2026, 9, 19, 10, 0, tzinfo=dt.UTC)
BUSINESS_TIMEZONE = "Asia/Kolkata"
_LOCAL = ZoneInfo(BUSINESS_TIMEZONE)

# Steps a job goes through to reach each status (assignment is always first).
_PATH: dict[JobStatus, tuple[str, ...]] = {
    JobStatus.NEW: (),
    JobStatus.ASSIGNED: ("assign",),
    JobStatus.SCHEDULED: ("assign", "schedule"),
    JobStatus.ON_THE_WAY: ("assign", "schedule", "on_the_way"),
    JobStatus.IN_PROGRESS: ("assign", "start"),
    JobStatus.COMPLETED: ("assign", "start", "finish"),
    JobStatus.CANCELLED: ("assign", "cancel"),
}


@dataclass(frozen=True, slots=True)
class Plan:
    ops: list[Op]
    manifest: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _Intake:
    """A ServiceRequest that came through AI intake. The extraction is a hand-written fixture, and
    is labelled as one (``model_id="seed-fixture"``): no model produced it."""

    raw_text: str
    extraction: dict[str, Any]


SCENARIOS: dict[str, dict[str, Any]] = {
    "repeat_ac_complaint": {
        "title": "A repeat AC complaint surfaces what was done last time",
        "records": {"customer": "ravi_kumar", "asset": "ravi_lg_ac"},
        "history": ["annual_service_ravi_lg_ac", "gas_refill_ravi_lg_ac"],
        "try": {
            "phone": "90000 20001",
            "message": "Bhaiya LG AC phir se thanda nahi kar raha. Kal 5 ke baad aa sakte ho?",
            "expect": "job created; prior service shows the annual service and the gas refill "
            "of the LG AC only (not the fridge)",
        },
    },
    "multiple_assets": {
        "title": "One customer, several appliances: never guess which",
        "records": {
            "customer": "meena_iyer",
            "assets": "4 (LG AC, Samsung AC, Kent RO, IFB washer)",
        },
        "try": [
            {
                "phone": "90000 20003",
                "message": "AC thanda nahi kar raha",
                "expect": "asset ambiguous (two ACs): review, no automatic job",
            },
            {
                "phone": "90000 20003",
                "message": "LG AC not cooling properly",
                "expect": "the brand selects the LG AC: job created",
            },
        ],
        "also": "'Ravi' matches two customers (Ravi Kumar, Ravi Verma): a name alone stays "
        "ambiguous",
    },
    "new_customer_review": {
        "title": "An unknown customer waits for a person",
        "records": {"service_request": "new_customer_deepak"},
        "try": {
            "phone": "90000 29999",
            "message": "Namaste, mera naam Deepak hai. Mere Godrej fridge ka compressor start "
            "nahi ho raha. Indiranagar mein hoon. Kal aa sakte ho?",
            "expect": "customer NEW, asset NEW: needs review, no job (already seeded as a request)",
        },
    },
    "safety_critical": {
        "title": "Dangerous wording is flagged and never diagnosed",
        "records": {"customer": "farhan_qureshi", "job": "fridge_burning_smell_farhan"},
        "try": {
            "phone": "90000 20004",
            "message": "Fridge se chingari nikal rahi hai aur jalne ki smell aa rahi hai",
            "expect": "a second job on the fridge, urgency safety_critical, safety_concern "
            "true, description is the customer's report only",
        },
    },
    "job_lifecycle": {
        "title": "Every job status, across technicians",
        "records": {
            "NEW": ["ro_flow_low_meena", "fridge_burning_smell_farhan"],
            "ASSIGNED": ["printer_not_printing_gopal"],
            "SCHEDULED": ["washer_drum_lakshmi"],
            "ON_THE_WAY": ["samsung_ac_hall_meena"],
            "IN_PROGRESS": ["laptop_restarts_gopal"],
            "COMPLETED": "6 (the service history)",
            "CANCELLED": ["tv_no_display_nisha"],
        },
        "also": "Anil Deshpande is inactive: assigning him is refused",
    },
}


class _Builder:
    def __init__(self, business_id: str, actor_id: str, as_of: datetime) -> None:
        self.business_id = business_id
        self.ctx = RequestContext(Actor(business_id=business_id, actor_id=actor_id), "req_seed")
        self.as_of = as_of
        self.ops: list[Op] = []
        self.technicians: dict[str, Technician] = {}
        self.customers: dict[str, Customer] = {}
        self.assets: dict[str, Asset] = {}
        self.ids: dict[str, dict[str, str]] = {
            k: {}
            for k in ("technicians", "customers", "assets", "service_requests", "jobs", "events")
        }
        self.job_status_counts: Counter[str] = Counter()

    # -- time -----------------------------------------------------------------------------------
    def ago(self, **delta: float) -> datetime:
        return self.as_of - timedelta(**delta)

    def local(self, day: int, hour: int, minute: int = 0) -> datetime:
        """A wall-clock time in the business's timezone, ``day`` days from the as-of date."""
        today = self.as_of.astimezone(_LOCAL).date()
        return datetime.combine(today + timedelta(days=day), dt.time(hour, minute), tzinfo=_LOCAL)

    # -- directory records ----------------------------------------------------------------------
    def _audit(
        self, label: str, at: datetime, action: AuditAction, kind: AuditEntityType, eid: str
    ) -> AuditEvent:
        with readable_ids(label):
            return build_audit(self.ctx, at, action, kind, eid)

    def business(self) -> None:
        at = self.ago(days=400)
        business = Business(
            business_id=self.business_id,
            name="Sharma Cooling & Appliance Care",
            timezone=BUSINESS_TIMEZONE,
            default_language="en",
            created_at=at,
            updated_at=at,
        )
        self.ops.append(create_record("business", "businesses", business))

    def technician(
        self, key: str, name: str, phone: str, skills: list[str], *, active: bool = True
    ) -> None:
        at = self.ago(days=390)
        technician = Technician(
            technician_id=f"tec_demo_{key}",
            business_id=self.business_id,
            name=name,
            phone=phone,
            skills=skills,
            active=active,
            created_at=at,
            updated_at=at,
        )
        self.technicians[key] = technician
        self.ids["technicians"][key] = technician.technician_id
        self.ops.append(create_record("technician", "technicians", technician))
        self.ops.append(
            append_audit(
                self._audit(
                    f"audit_technician_{key}",
                    at,
                    AuditAction.TECHNICIAN_CREATED,
                    AuditEntityType.TECHNICIAN,
                    technician.technician_id,
                )
            )
        )

    def customer(self, key: str, name: str, phone: str, address: str, language: str) -> None:
        at = self.ago(days=380)
        customer = Customer(
            customer_id=f"cus_demo_{key}",
            business_id=self.business_id,
            name=name,
            phone=phone,
            address=address,
            preferred_language=language,
            created_at=at,
            updated_at=at,
        )
        self.customers[key] = customer
        self.ids["customers"][key] = customer.customer_id
        self.ops.append(create_record("customer", "customers", customer))
        self.ops.append(
            append_audit(
                self._audit(
                    f"audit_customer_{key}",
                    at,
                    AuditAction.CUSTOMER_CREATED,
                    AuditEntityType.CUSTOMER,
                    customer.customer_id,
                )
            )
        )

    def asset(
        self,
        key: str,
        owner: str,
        asset_type: AssetType,
        brand: str,
        location: str,
        **known: Any,
    ) -> None:
        """Details not passed in ``known`` (model, serial, warranty) stay unknown."""
        at = self.ago(days=375)
        asset = Asset(
            asset_id=f"ast_demo_{key}",
            business_id=self.business_id,
            customer_id=self.customers[owner].customer_id,
            asset_type=asset_type,
            brand=brand,
            location=location,
            created_at=at,
            updated_at=at,
            **known,
        )
        self.assets[key] = asset
        self.ids["assets"][key] = asset.asset_id
        self.ops.append(create_record("asset", "assets", asset))
        self.ops.append(
            append_audit(
                self._audit(
                    f"audit_asset_{key}",
                    at,
                    AuditAction.ASSET_CREATED,
                    AuditEntityType.ASSET,
                    asset.asset_id,
                )
            )
        )

    # -- requests and jobs ----------------------------------------------------------------------
    def story(
        self,
        key: str,
        *,
        customer: str,
        asset: str,
        description: str,
        created: datetime,
        end: JobStatus,
        technician: str | None = None,
        service_type: ServiceType = ServiceType.REPAIR,
        urgency: Urgency = Urgency.NORMAL,
        at: dict[str, datetime] | None = None,
        slot: TimeSlot | None = None,
        completion: JobCompletion | None = None,
        intake: _Intake | None = None,
    ) -> None:
        """One job with its ServiceRequest, taken through the real workflow up to ``end``."""
        person, item = self.customers[customer], self.assets[asset]
        request_id = f"srq_demo_{key}"
        steps = at or {}

        with readable_ids(key):
            change = create_job(
                self.ctx,
                customer=person,
                asset=item,
                service_type=service_type,
                description=description,
                now=created,
                urgency=urgency,
                source=JobSource.INTAKE if intake else JobSource.MANUAL,
                service_request_id=request_id,
            )
            job = change.job
            request_audit = build_audit(
                self.ctx,
                created,
                AuditAction.SERVICE_REQUEST_CREATED,
                AuditEntityType.SERVICE_REQUEST,
                request_id,
            )

            # The request, exactly as the API would have stored it.
            if intake is None:
                request = ServiceRequest(
                    service_request_id=request_id,
                    business_id=self.business_id,
                    raw_text=description,
                    customer_resolution=EntityResolution(
                        state=ResolutionState.EXISTING, entity_id=person.customer_id
                    ),
                    asset_resolution=EntityResolution(
                        state=ResolutionState.EXISTING, entity_id=item.asset_id
                    ),
                    created_at=created,
                    updated_at=created,
                )
                self.ops += [
                    create_record("service_request", "service_requests", request),
                    append_audit(request_audit),
                ]
            else:
                received = ServiceRequest(
                    service_request_id=request_id,
                    business_id=self.business_id,
                    raw_text=intake.raw_text,
                    created_at=created,
                    updated_at=created,
                )
                request = received.evolve(
                    status=ServiceRequestStatus.NEEDS_REVIEW,
                    extraction=intake.extraction,
                    customer_resolution=EntityResolution(
                        state=ResolutionState.EXISTING,
                        entity_id=person.customer_id,
                        candidates=[
                            MatchCandidate(
                                entity_id=person.customer_id,
                                match_score=0.95,
                                reasons=["phone number matches"],
                            )
                        ],
                    ),
                    asset_resolution=EntityResolution(
                        state=ResolutionState.EXISTING,
                        entity_id=item.asset_id,
                        candidates=[
                            MatchCandidate(
                                entity_id=item.asset_id,
                                match_score=0.9,
                                reasons=["type matches, brand matches"],
                            )
                        ],
                    ),
                    version=2,
                )
                self.ops += [
                    create_record("service_request", "service_requests", received),
                    append_audit(request_audit),
                    update_request(request),
                ]

            linked = request.evolve(
                status=ServiceRequestStatus.JOB_CREATED,
                job_id=job.job_id,
                version=request.version + 1,
                updated_at=created,
            )
            self.ops.append(create_job_from_request(job, linked, change.audit))

            for step in _PATH[end]:
                when = steps[step]
                if step == "assign":
                    assert technician is not None
                    move = assign_job(self.ctx, job, self.technicians[technician], when)
                elif step == "schedule":
                    move = transition_job(
                        self.ctx, job, JobStatus.SCHEDULED, when, scheduled_slot=slot
                    )
                elif step == "on_the_way":
                    move = transition_job(self.ctx, job, JobStatus.ON_THE_WAY, when)
                elif step == "start":
                    move = transition_job(self.ctx, job, JobStatus.IN_PROGRESS, when)
                elif step == "cancel":
                    move = transition_job(self.ctx, job, JobStatus.CANCELLED, when)
                else:  # finish
                    assert completion is not None
                    done = complete_job(self.ctx, job, completion, when)
                    self.ops.append(complete_job_op(done.job, done.event, done.audit))
                    self.ids["events"][key] = done.event.event_id
                    job = done.job
                    continue
                self.ops.append(advance_job(move.job, move.audit))
                job = move.job

        assert job.status is end
        self.ids["jobs"][key] = job.job_id
        self.ids["service_requests"][key] = request_id
        self.job_status_counts[end.value] += 1

    def review_request(
        self, key: str, *, raw_text: str, extraction: dict[str, Any], created: datetime
    ) -> None:
        """A request from someone not yet a customer: understood, but waiting for a person."""
        request_id = f"srq_demo_{key}"
        received = ServiceRequest(
            service_request_id=request_id,
            business_id=self.business_id,
            raw_text=raw_text,
            created_at=created,
            updated_at=created,
        )
        reviewed = received.evolve(
            status=ServiceRequestStatus.NEEDS_REVIEW,
            extraction=extraction,
            customer_resolution=EntityResolution(state=ResolutionState.NEW),
            asset_resolution=EntityResolution(state=ResolutionState.NEW),
            version=2,
        )
        self.ops += [
            create_record("service_request", "service_requests", received),
            append_audit(
                self._audit(
                    f"audit_request_{key}",
                    created,
                    AuditAction.SERVICE_REQUEST_CREATED,
                    AuditEntityType.SERVICE_REQUEST,
                    request_id,
                )
            ),
            update_request(reviewed),
        ]
        self.ids["service_requests"][key] = request_id


def _fixture(
    *,
    asset: AssetMention,
    description: str,
    symptoms: list[str],
    urgency: Urgency | None,
    confidence: Confidence,
    missing: list[str],
    customer_reference: str | None = None,
    time_preference: TimePreference | None = None,
    safety: bool = False,
) -> dict[str, Any]:
    """A stored extraction written by hand and labelled as a fixture, not model output."""
    stored = StoredExtraction(
        prompt_version="seed-fixture",
        model_id="seed-fixture",
        data=IntakeExtraction(
            intent=Intent.SERVICE_REQUEST,
            service_type=ServiceType.REPAIR,
            customer_reference=customer_reference,
            asset=asset,
            problem=ProblemMention(description=description, urgency=urgency, symptoms=symptoms),
            time_preference=time_preference or TimePreference(),
            confidence=confidence,
            missing_information=missing,
            sources={
                "asset.type": Source.EXPLICIT_TEXT,
                "asset.brand": Source.EXPLICIT_TEXT,
                "problem.description": Source.EXPLICIT_TEXT,
            },
        ),
        safety_concern=safety,
    )
    return stored.model_dump(mode="json")


def build_demo_plan(business_id: str, actor_id: str, as_of: datetime = DEFAULT_AS_OF) -> Plan:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    b = _Builder(business_id, actor_id, as_of.astimezone(dt.UTC))
    b.business()

    # -- people ---------------------------------------------------------------------------------
    b.technician("imran", "Imran Sheikh", "90000 10001", ["air_conditioner", "refrigerator"])
    b.technician(
        "suresh", "Suresh Patil", "90000 10002", ["washing_machine", "water_purifier", "electrical"]
    )
    b.technician(
        "kavitha",
        "Kavitha Nair",
        "90000 10003",
        ["air_conditioner", "television", "computer", "printer"],
    )
    b.technician("anil", "Anil Deshpande", "90000 10004", ["plumbing"], active=False)

    b.customer(
        "ravi_kumar",
        "Ravi Kumar",
        "90000 20001",
        "Flat 4B, Lake View Apartments, Indiranagar, Bengaluru",
        "hi",
    )
    b.customer(
        "ravi_verma", "Ravi Verma", "90000 20002", "12, 5th Cross, Jayanagar, Bengaluru", "en"
    )
    b.customer(
        "meena_iyer", "Meena Iyer", "90000 20003", "7, Temple Street, Malleshwaram, Bengaluru", "en"
    )
    b.customer(
        "farhan_qureshi",
        "Farhan Qureshi",
        "90000 20004",
        "301, Green Court, HSR Layout, Bengaluru",
        "hi",
    )
    b.customer(
        "lakshmi_prasad",
        "Lakshmi Prasad",
        "90000 20005",
        "45, 2nd Main, Basavanagudi, Bengaluru",
        "kn",
    )
    b.customer(
        "gopal_reddy",
        "Gopal Reddy",
        "90000 20006",
        "Plot 18, Whitefield Main Road, Bengaluru",
        "en",
    )
    b.customer(
        "nisha_bhat", "Nisha Bhat", "90000 20007", "9, Church Road, Koramangala, Bengaluru", "en"
    )

    # -- appliances (model, serial and warranty stay unknown unless stated) -----------------------
    ac, fridge = AssetType.AIR_CONDITIONER, AssetType.REFRIGERATOR
    b.asset("ravi_lg_ac", "ravi_kumar", ac, "LG", "Bedroom")
    b.asset("ravi_samsung_fridge", "ravi_kumar", fridge, "Samsung", "Kitchen")
    b.asset("verma_voltas_ac", "ravi_verma", ac, "Voltas", "Living room")
    b.asset("meena_lg_ac", "meena_iyer", ac, "LG", "Master bedroom")
    b.asset("meena_samsung_ac", "meena_iyer", ac, "Samsung", "Hall")
    b.asset(
        "meena_kent_ro",
        "meena_iyer",
        AssetType.WATER_PURIFIER,
        "Kent",
        "Kitchen",
        serial_number="KENT-RO-77120",
        purchase_date=dt.date(2024, 3, 10),
    )
    b.asset("meena_ifb_washer", "meena_iyer", AssetType.WASHING_MACHINE, "IFB", "Utility area")
    b.asset("farhan_samsung_fridge", "farhan_qureshi", fridge, "Samsung", "Kitchen")
    b.asset("lakshmi_washer", "lakshmi_prasad", AssetType.WASHING_MACHINE, "Bosch", "Utility area")
    b.asset("gopal_printer", "gopal_reddy", AssetType.PRINTER, "HP", "Home office")
    b.asset("gopal_laptop", "gopal_reddy", AssetType.COMPUTER, "Dell", "Home office")
    b.asset("nisha_tv", "nisha_bhat", AssetType.TELEVISION, "Sony", "Living room")

    # -- recorded service history (all COMPLETED) --------------------------------------------------
    def history(key: str, days_ago: int, **story: Any) -> None:
        created = b.ago(days=days_ago)
        b.story(
            key,
            created=created,
            end=JobStatus.COMPLETED,
            at={
                "assign": created + timedelta(minutes=15),
                "start": created + timedelta(days=1),
                "finish": created + timedelta(days=1, minutes=90),
            },
            **story,
        )

    history(
        "annual_service_ravi_lg_ac",
        210,
        customer="ravi_kumar",
        asset="ravi_lg_ac",
        technician="imran",
        service_type=ServiceType.MAINTENANCE,
        description="Annual AC service",
        completion=JobCompletion(
            work_performed="Filter cleaned and indoor coil washed",
            technician_notes="Unit was in normal working order after service",
        ),
    )
    history(
        "gas_refill_ravi_lg_ac",
        45,
        customer="ravi_kumar",
        asset="ravi_lg_ac",
        technician="imran",
        description="AC not cooling",
        completion=JobCompletion(
            work_performed="Gas pressure checked and refrigerant refilled",
            technician_notes="Customer advised to watch cooling over the next few weeks",
            parts_used=["refrigerant gas"],
            observed_symptoms=["not cooling"],
        ),
    )
    history(
        "gasket_ravi_samsung_fridge",
        120,
        customer="ravi_kumar",
        asset="ravi_samsung_fridge",
        technician="imran",
        description="Fridge door not sealing properly",
        completion=JobCompletion(
            work_performed="Door gasket replaced",
            parts_used=["door gasket"],
            observed_symptoms=["door not sealing"],
        ),
    )
    history(
        "drain_verma_voltas_ac",
        30,
        customer="ravi_verma",
        asset="verma_voltas_ac",
        technician="imran",
        description="Water leaking from indoor unit",
        completion=JobCompletion(
            work_performed="Drain pipe cleared", observed_symptoms=["water leaking"]
        ),
    )
    history(
        "filters_meena_kent_ro",
        90,
        customer="meena_iyer",
        asset="meena_kent_ro",
        technician="suresh",
        service_type=ServiceType.MAINTENANCE,
        description="Filter set due for replacement",
        completion=JobCompletion(
            work_performed="Sediment and carbon filters replaced",
            parts_used=["sediment filter", "carbon filter"],
        ),
    )
    history(
        "rattle_meena_lg_ac",
        60,
        customer="meena_iyer",
        asset="meena_lg_ac",
        technician="kavitha",
        description="AC making a rattling noise",
        completion=JobCompletion(
            work_performed="Fan blade tightened",
            technician_notes="Recheck if the noise returns",
            observed_symptoms=["rattling noise"],
            follow_up_required=True,
        ),
    )

    # -- job lifecycle: one open job in every status ---------------------------------------------
    b.story(
        "ro_flow_low_meena",
        customer="meena_iyer",
        asset="meena_kent_ro",
        description="Water purifier flow is low",
        created=b.ago(hours=2),
        end=JobStatus.NEW,
    )
    b.story(
        "printer_not_printing_gopal",
        customer="gopal_reddy",
        asset="gopal_printer",
        description="Printer not printing",
        created=b.ago(hours=3),
        end=JobStatus.ASSIGNED,
        technician="kavitha",
        at={"assign": b.ago(hours=2, minutes=30)},
    )
    b.story(
        "washer_drum_lakshmi",
        customer="lakshmi_prasad",
        asset="lakshmi_washer",
        description="Washing machine drum not spinning",
        created=b.ago(hours=5),
        end=JobStatus.SCHEDULED,
        technician="suresh",
        at={"assign": b.ago(hours=4, minutes=45), "schedule": b.ago(hours=4, minutes=30)},
        slot=TimeSlot(start=b.local(1, 11), end=b.local(1, 13)),
    )
    b.story(
        "samsung_ac_hall_meena",
        customer="meena_iyer",
        asset="meena_samsung_ac",
        description="AC not cooling in the hall",
        created=b.ago(hours=4),
        end=JobStatus.ON_THE_WAY,
        technician="imran",
        at={
            "assign": b.ago(hours=3, minutes=45),
            "schedule": b.ago(hours=3, minutes=30),
            "on_the_way": b.ago(minutes=20),
        },
        slot=TimeSlot(start=b.local(0, 15), end=b.local(0, 17)),
    )
    b.story(
        "laptop_restarts_gopal",
        customer="gopal_reddy",
        asset="gopal_laptop",
        description="Computer restarts randomly",
        created=b.ago(days=1),
        end=JobStatus.IN_PROGRESS,
        technician="kavitha",
        at={"assign": b.ago(days=1) + timedelta(minutes=20), "start": b.ago(hours=1)},
    )
    b.story(
        "tv_no_display_nisha",
        customer="nisha_bhat",
        asset="nisha_tv",
        description="TV shows no display",
        created=b.ago(days=2),
        end=JobStatus.CANCELLED,
        technician="kavitha",
        at={
            "assign": b.ago(days=2) + timedelta(minutes=30),
            "cancel": b.ago(days=2) + timedelta(hours=3),
        },
    )

    # -- safety-critical request: came through intake, awaiting a person -------------------------
    b.story(
        "fridge_burning_smell_farhan",
        customer="farhan_qureshi",
        asset="farhan_samsung_fridge",
        description="Refrigerator has a burning smell and sparks",
        created=b.ago(minutes=40),
        end=JobStatus.NEW,
        urgency=Urgency.SAFETY_CRITICAL,
        intake=_Intake(
            raw_text="Fridge se jalne ki smell aa rahi hai aur chingari bhi nikli. "
            "Please jaldi aa jao",
            extraction=_fixture(
                asset=AssetMention(type=fridge, brand="Samsung", model=None),
                description="Refrigerator has a burning smell and sparks",
                symptoms=["burning smell", "sparks"],
                urgency=Urgency.SAFETY_CRITICAL,
                confidence=Confidence(overall=0.92, asset=0.9, problem=0.95, schedule=0.0),
                missing=["asset.model", "time_preference"],
                safety=True,
            ),
        ),
    )

    # -- new customer: a request that needs review ------------------------------------------------
    b.review_request(
        "new_customer_deepak",
        raw_text="Namaste, mera naam Deepak hai. Mere Godrej fridge ka compressor start nahi ho "
        "raha. Indiranagar mein hoon. Kal aa sakte ho?",
        created=b.ago(minutes=25),
        extraction=_fixture(
            asset=AssetMention(type=fridge, brand="Godrej", model=None),
            description="Refrigerator compressor is not starting",
            symptoms=["compressor not starting"],
            urgency=None,
            customer_reference="Deepak",
            time_preference=TimePreference(date=b.local(1, 0).date()),
            confidence=Confidence(overall=0.88, asset=0.9, problem=0.9, schedule=0.5),
            missing=["asset.model", "time_preference"],
        ),
    )

    manifest: dict[str, Any] = {
        **b.ids,
        "job_status_counts": dict(b.job_status_counts),
        "scenarios": SCENARIOS,
    }
    return Plan(ops=b.ops, manifest=manifest)
