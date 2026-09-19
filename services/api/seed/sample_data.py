"""Synthetic demo data. Every name, phone number and address is fictional.

The dataset is built through the real domain workflow, so seeded history obeys the same invariants
as production data. Two customers share the first name "Ravi" to exercise ambiguous-customer
handling, and the LG air conditioner has prior service events so a repeat complaint has history.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.context import Actor, RequestContext
from app.core.errors import NotFoundError
from app.core.ids import IdPrefix
from app.domain.asset import Asset
from app.domain.audit import build_audit
from app.domain.business import Business
from app.domain.customer import Customer
from app.domain.enums import (
    AssetType,
    AuditAction,
    AuditEntityType,
    JobStatus,
    ServiceType,
    Urgency,
)
from app.domain.job_workflow import (
    JobCompletion,
    assign_job,
    complete_job,
    create_job,
    transition_job,
)
from app.domain.repositories import Repositories
from app.domain.technician import Technician


@dataclass(frozen=True, slots=True)
class SeedResult:
    created: bool
    ids: dict[str, str]


def _id(prefix: IdPrefix, name: str) -> str:
    return f"{prefix.value}_demo_{name}"


def load_demo_data(
    repos: Repositories, *, business_id: str, actor_id: str, now: datetime
) -> SeedResult:
    """Insert the demo business and its history. Safe to run twice: an existing business is left
    untouched."""
    ids = {
        "business": business_id,
        "technician_imran": _id(IdPrefix.TECHNICIAN, "imran"),
        "technician_suresh": _id(IdPrefix.TECHNICIAN, "suresh"),
        "customer_ravi_kumar": _id(IdPrefix.CUSTOMER, "ravi_kumar"),
        "customer_ravi_verma": _id(IdPrefix.CUSTOMER, "ravi_verma"),
        "customer_meena_iyer": _id(IdPrefix.CUSTOMER, "meena_iyer"),
        "asset_lg_ac": _id(IdPrefix.ASSET, "lg_ac"),
        "asset_samsung_fridge": _id(IdPrefix.ASSET, "samsung_fridge"),
        "asset_voltas_ac": _id(IdPrefix.ASSET, "voltas_ac"),
        "asset_kent_ro": _id(IdPrefix.ASSET, "kent_ro"),
    }
    try:
        repos.businesses.get(business_id)
        return SeedResult(created=False, ids=ids)
    except NotFoundError:
        pass

    ctx = RequestContext(Actor(business_id=business_id, actor_id=actor_id), "req_seed")
    long_ago = now - timedelta(days=400)

    repos.businesses.create(
        Business(
            business_id=business_id,
            name="Sharma Cooling & Appliance Care",
            timezone="Asia/Kolkata",
            default_language="en",
            created_at=long_ago,
            updated_at=long_ago,
        )
    )

    def audit(action: AuditAction, entity_type: AuditEntityType, entity_id: str) -> None:
        repos.audits.append(build_audit(ctx, long_ago, action, entity_type, entity_id))

    technicians = {
        "technician_imran": Technician(
            technician_id=ids["technician_imran"],
            business_id=business_id,
            name="Imran Sheikh",
            phone="90000 10001",
            skills=["air_conditioner", "refrigerator"],
            created_at=long_ago,
            updated_at=long_ago,
        ),
        "technician_suresh": Technician(
            technician_id=ids["technician_suresh"],
            business_id=business_id,
            name="Suresh Patil",
            phone="90000 10002",
            skills=["washing_machine", "water_purifier", "electrical"],
            created_at=long_ago,
            updated_at=long_ago,
        ),
    }
    for technician in technicians.values():
        repos.technicians.create(technician)
        audit(AuditAction.TECHNICIAN_CREATED, AuditEntityType.TECHNICIAN, technician.technician_id)

    customers = {
        "customer_ravi_kumar": Customer(
            customer_id=ids["customer_ravi_kumar"],
            business_id=business_id,
            name="Ravi Kumar",
            phone="90000 20001",
            address="Flat 4B, Lake View Apartments, Indiranagar, Bengaluru",
            preferred_language="hi",
            created_at=long_ago,
            updated_at=long_ago,
        ),
        "customer_ravi_verma": Customer(
            customer_id=ids["customer_ravi_verma"],
            business_id=business_id,
            name="Ravi Verma",
            phone="90000 20002",
            address="12, 5th Cross, Jayanagar, Bengaluru",
            preferred_language="en",
            created_at=long_ago,
            updated_at=long_ago,
        ),
        "customer_meena_iyer": Customer(
            customer_id=ids["customer_meena_iyer"],
            business_id=business_id,
            name="Meena Iyer",
            phone="90000 20003",
            address="7, Temple Street, Malleshwaram, Bengaluru",
            preferred_language="en",
            created_at=long_ago,
            updated_at=long_ago,
        ),
    }
    for customer in customers.values():
        repos.customers.create(customer)
        audit(AuditAction.CUSTOMER_CREATED, AuditEntityType.CUSTOMER, customer.customer_id)

    def asset(key: str, owner: str, asset_type: AssetType, brand: str, location: str) -> Asset:
        return Asset(
            asset_id=ids[key],
            business_id=business_id,
            customer_id=ids[owner],
            asset_type=asset_type,
            brand=brand,
            location=location,
            created_at=long_ago,
            updated_at=long_ago,
        )

    assets = {
        "asset_lg_ac": asset(
            "asset_lg_ac", "customer_ravi_kumar", AssetType.AIR_CONDITIONER, "LG", "Bedroom"
        ),
        "asset_samsung_fridge": asset(
            "asset_samsung_fridge",
            "customer_ravi_kumar",
            AssetType.REFRIGERATOR,
            "Samsung",
            "Kitchen",
        ),
        "asset_voltas_ac": asset(
            "asset_voltas_ac",
            "customer_ravi_verma",
            AssetType.AIR_CONDITIONER,
            "Voltas",
            "Living room",
        ),
        "asset_kent_ro": asset(
            "asset_kent_ro", "customer_meena_iyer", AssetType.WATER_PURIFIER, "Kent", "Kitchen"
        ),
    }
    for item in assets.values():
        repos.assets.create(item)
        audit(AuditAction.ASSET_CREATED, AuditEntityType.ASSET, item.asset_id)

    def completed_job(
        customer: str,
        item: str,
        technician: str,
        *,
        service_type: ServiceType,
        description: str,
        days_ago: int,
        completion: JobCompletion,
    ) -> None:
        created = now - timedelta(days=days_ago)
        change = create_job(
            ctx,
            customer=customers[customer],
            asset=assets[item],
            service_type=service_type,
            description=description,
            now=created,
        )
        repos.jobs.create(change.job, change.audit)
        job = change.job
        assigned = assign_job(ctx, job, technicians[technician], created + timedelta(minutes=15))
        repos.jobs.update(assigned.job, assigned.audit)
        started = transition_job(
            ctx, assigned.job, JobStatus.IN_PROGRESS, created + timedelta(days=1)
        )
        repos.jobs.update(started.job, started.audit)
        result = complete_job(ctx, started.job, completion, created + timedelta(days=1, minutes=90))
        repos.jobs.complete(result.job, result.event, result.audit)

    completed_job(
        "customer_ravi_kumar",
        "asset_lg_ac",
        "technician_imran",
        service_type=ServiceType.MAINTENANCE,
        description="Annual AC service",
        days_ago=210,
        completion=JobCompletion(
            work_performed="Filter cleaned and indoor coil washed",
            technician_notes="Unit was in normal working order after service",
        ),
    )
    completed_job(
        "customer_ravi_kumar",
        "asset_lg_ac",
        "technician_imran",
        service_type=ServiceType.REPAIR,
        description="AC not cooling",
        days_ago=45,
        completion=JobCompletion(
            work_performed="Gas pressure checked and refrigerant refilled",
            technician_notes="Customer advised to watch cooling over the next few weeks",
            parts_used=["refrigerant gas"],
            observed_symptoms=["not cooling"],
        ),
    )
    completed_job(
        "customer_ravi_verma",
        "asset_voltas_ac",
        "technician_imran",
        service_type=ServiceType.REPAIR,
        description="Water leaking from indoor unit",
        days_ago=30,
        completion=JobCompletion(
            work_performed="Drain pipe cleared",
            observed_symptoms=["water leaking"],
        ),
    )

    open_job = create_job(
        ctx,
        customer=customers["customer_meena_iyer"],
        asset=assets["asset_kent_ro"],
        service_type=ServiceType.REPAIR,
        description="Water purifier flow is low",
        urgency=Urgency.NORMAL,
        now=now - timedelta(hours=2),
    )
    repos.jobs.create(open_job.job, open_job.audit)

    return SeedResult(created=True, ids=ids)
