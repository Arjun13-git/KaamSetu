"""Idempotent, resumable application of a dataset plan.

A plan is an ordered list of writes that is built entirely in memory, so it is identical on every
run. Applying it never duplicates anything and can resume after a crash, because each write first
checks whether it has already been applied: creates by existence, updates by the stored version.
The writes themselves are the production repository operations (including the atomic
job-from-request and completion writes), never anything special-cased for seeding.
"""

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import ConflictError, DuplicateRequestError, NotFoundError
from app.domain.audit import AuditEvent
from app.domain.job import Job
from app.domain.repositories import Repositories
from app.domain.service_event import ServiceEvent
from app.domain.service_request import ServiceRequest


@dataclass(frozen=True, slots=True)
class Op:
    kind: str
    apply: Callable[[Repositories], bool]  # True if it wrote, False if already applied


@dataclass
class Tally:
    created: Counter[str] = field(default_factory=Counter)
    existing: Counter[str] = field(default_factory=Counter)

    @property
    def total_created(self) -> int:
        return sum(self.created.values())

    @property
    def total_existing(self) -> int:
        return sum(self.existing.values())


def apply_plan(ops: Iterable[Op], repos: Repositories) -> Tally:
    tally = Tally()
    for op in ops:
        (tally.created if op.apply(repos) else tally.existing)[op.kind] += 1
    return tally


def create_record(kind: str, repository: str, record: Any) -> Op:
    """Create a record unless it already exists."""

    def run(repos: Repositories) -> bool:
        try:
            getattr(repos, repository).create(record)
        except (ConflictError, DuplicateRequestError):
            return False
        return True

    return Op(kind, run)


def append_audit(audit: AuditEvent) -> Op:
    def run(repos: Repositories) -> bool:
        try:
            repos.audits.append(audit)
        except ConflictError:
            return False
        return True

    return Op("audit", run)


def update_request(request: ServiceRequest) -> Op:
    """Move a request to ``request.version`` unless it is already there or beyond."""

    def run(repos: Repositories) -> bool:
        stored = repos.service_requests.get(request.business_id, request.service_request_id)
        if stored.version >= request.version:
            return False
        repos.service_requests.update(request)
        return True

    return Op("service_request_update", run)


def create_job_from_request(job: Job, linked: ServiceRequest, audit: AuditEvent) -> Op:
    """The atomic write that creates a job, links its request and audits it."""

    def run(repos: Repositories) -> bool:
        try:
            repos.jobs.get(job.business_id, job.job_id)
        except NotFoundError:
            repos.jobs.create_for_request(job, linked, audit)
            return True
        return False

    return Op("job", run)


def advance_job(job: Job, audit: AuditEvent) -> Op:
    """Move a job to ``job.version`` (an assignment, transition) unless already there."""

    def run(repos: Repositories) -> bool:
        stored = repos.jobs.get(job.business_id, job.job_id)
        if stored.version >= job.version:
            return False
        repos.jobs.update(job, audit)
        return True

    return Op("job_update", run)


def complete_job(job: Job, event: ServiceEvent, audit: AuditEvent) -> Op:
    """The atomic completion write: job, service event and audit together."""

    def run(repos: Repositories) -> bool:
        stored = repos.jobs.get(job.business_id, job.job_id)
        if stored.version >= job.version:
            return False
        repos.jobs.complete(job, event, audit)
        return True

    return Op("service_event", run)
