from app.domain.enums import AuditEntityType, JobStatus
from app.domain.repositories import Repositories
from seed.sample_data import load_demo_data
from tests.factories import NOW

BUSINESS = "bus_demo"
ACTOR = "usr_dev"


def _load(repos: Repositories):
    return load_demo_data(repos, business_id=BUSINESS, actor_id=ACTOR, now=NOW)


def test_seed_creates_a_coherent_business(repos: Repositories) -> None:
    result = _load(repos)

    assert result.created
    assert repos.businesses.get(BUSINESS).timezone == "Asia/Kolkata"
    assert len(repos.technicians.list(BUSINESS, active_only=True)) == 2
    assert len(repos.customers.list(BUSINESS)) == 3


def test_two_customers_named_ravi_make_a_name_ambiguous(repos: Repositories) -> None:
    _load(repos)

    matches = repos.customers.search_by_name(BUSINESS, "ravi")

    assert [c.name for c in matches] == ["Ravi Kumar", "Ravi Verma"]


def test_the_lg_ac_has_prior_service_history_newest_first(repos: Repositories) -> None:
    result = _load(repos)

    events = repos.service_events.list_by_asset(BUSINESS, result.ids["asset_lg_ac"])

    assert [e.summary.split(" | ")[0] for e in events] == [
        "Reported: AC not cooling",
        "Reported: Annual AC service",
    ]
    assert "refilled" in events[0].work_performed
    assert events[0].timestamp > events[1].timestamp


def test_history_is_reachable_by_customer_and_by_phone(repos: Repositories) -> None:
    result = _load(repos)

    (customer,) = repos.customers.find_by_phone(BUSINESS, "90000 20001")

    assert customer.customer_id == result.ids["customer_ravi_kumar"]
    assert len(repos.service_events.list_by_customer(BUSINESS, customer.customer_id)) == 2


def test_seed_leaves_one_open_job_ready_to_assign(repos: Repositories) -> None:
    result = _load(repos)

    (open_job,) = repos.jobs.list(BUSINESS, status=JobStatus.NEW)

    assert open_job.customer_id == result.ids["customer_meena_iyer"]
    assert len(repos.jobs.list(BUSINESS, status=JobStatus.COMPLETED)) == 3


def test_every_completed_job_left_an_audit_trail(repos: Repositories) -> None:
    _load(repos)

    for job in repos.jobs.list(BUSINESS, status=JobStatus.COMPLETED):
        actions = [
            a.action.value
            for a in repos.audits.list_for_entity(BUSINESS, AuditEntityType.JOB, job.job_id)
        ]
        assert actions == ["JOB_CREATED", "JOB_ASSIGNED", "JOB_STATUS_CHANGED", "JOB_COMPLETED"]


def test_seeding_twice_changes_nothing(repos: Repositories) -> None:
    _load(repos)
    jobs_before = len(repos.jobs.list(BUSINESS))

    second = _load(repos)

    assert not second.created
    assert len(repos.jobs.list(BUSINESS)) == jobs_before
