"""Exact service history: what was recorded, in order, for a customer or an asset. Nothing here
interprets or summarizes it into a diagnosis."""

from dataclasses import dataclass

from app.core.context import RequestContext
from app.core.errors import NotFoundError
from app.domain.asset import Asset
from app.domain.customer import Customer
from app.domain.job import Job
from app.domain.repositories import Repositories
from app.domain.service_event import ServiceEvent
from app.domain.technician import Technician


@dataclass(frozen=True, slots=True)
class AssetHistory:
    asset: Asset
    jobs: list[Job]
    events: list[ServiceEvent]


@dataclass(frozen=True, slots=True)
class CustomerHistory:
    customer: Customer
    assets: list[Asset]
    jobs: list[Job]
    events: list[ServiceEvent]


@dataclass(frozen=True, slots=True)
class JobCard:
    job: Job
    customer: Customer
    asset: Asset
    technician: Technician | None
    prior_events: list[ServiceEvent]


def asset_history(
    ctx: RequestContext, repos: Repositories, asset_id: str, limit: int
) -> AssetHistory:
    asset = repos.assets.get(ctx.business_id, asset_id)
    return AssetHistory(
        asset=asset,
        jobs=repos.jobs.list_by_asset(ctx.business_id, asset_id, limit=limit),
        events=repos.service_events.list_by_asset(ctx.business_id, asset_id, limit=limit),
    )


def customer_history(
    ctx: RequestContext, repos: Repositories, customer_id: str, limit: int
) -> CustomerHistory:
    customer = repos.customers.get(ctx.business_id, customer_id)
    return CustomerHistory(
        customer=customer,
        assets=repos.assets.list_by_customer(ctx.business_id, customer_id),
        jobs=repos.jobs.list_by_customer(ctx.business_id, customer_id, limit=limit),
        events=repos.service_events.list_by_customer(ctx.business_id, customer_id, limit=limit),
    )


def prior_service(
    ctx: RequestContext,
    repos: Repositories,
    asset_id: str,
    *,
    exclude_job_id: str | None = None,
    limit: int = 5,
) -> list[ServiceEvent]:
    """Most recent recorded service for an asset, newest first."""
    events = repos.service_events.list_by_asset(ctx.business_id, asset_id, limit=limit + 1)
    return [e for e in events if e.job_id != exclude_job_id][:limit]


def job_card(
    ctx: RequestContext, repos: Repositories, job_id: str, history_limit: int = 5
) -> JobCard:
    job = repos.jobs.get(ctx.business_id, job_id)
    technician = None
    if job.technician_id is not None:
        try:
            technician = repos.technicians.get(ctx.business_id, job.technician_id)
        except NotFoundError:
            technician = None
    return JobCard(
        job=job,
        customer=repos.customers.get(ctx.business_id, job.customer_id),
        asset=repos.assets.get(ctx.business_id, job.asset_id),
        technician=technician,
        prior_events=prior_service(
            ctx, repos, job.asset_id, exclude_job_id=job.job_id, limit=history_limit
        ),
    )
