import pytest

from app.core.errors import InvalidStateTransitionError
from app.domain.enums import JobStatus
from app.domain.job_state_machine import (
    TERMINAL_STATUSES,
    assert_legal_transition,
    is_legal_transition,
)

S = JobStatus

EXPECTED_LEGAL = {
    (S.NEW, S.ASSIGNED),
    (S.NEW, S.CANCELLED),
    (S.ASSIGNED, S.SCHEDULED),
    (S.ASSIGNED, S.ON_THE_WAY),  # SCHEDULED skipped
    (S.ASSIGNED, S.IN_PROGRESS),  # SCHEDULED and ON_THE_WAY skipped
    (S.ASSIGNED, S.CANCELLED),
    (S.SCHEDULED, S.ON_THE_WAY),
    (S.SCHEDULED, S.IN_PROGRESS),  # ON_THE_WAY skipped
    (S.SCHEDULED, S.CANCELLED),
    (S.ON_THE_WAY, S.IN_PROGRESS),
    (S.ON_THE_WAY, S.CANCELLED),
    (S.IN_PROGRESS, S.COMPLETED),
    (S.IN_PROGRESS, S.CANCELLED),
}


@pytest.mark.parametrize("current", list(JobStatus))
@pytest.mark.parametrize("target", list(JobStatus))
def test_every_status_pair_matches_the_approved_graph(
    current: JobStatus, target: JobStatus
) -> None:
    assert is_legal_transition(current, target) is ((current, target) in EXPECTED_LEGAL)


def test_progression_is_forward_only() -> None:
    assert not is_legal_transition(S.IN_PROGRESS, S.ON_THE_WAY)
    assert not is_legal_transition(S.ON_THE_WAY, S.SCHEDULED)
    assert not is_legal_transition(S.ASSIGNED, S.NEW)


def test_terminal_statuses_have_no_exits() -> None:
    for terminal in TERMINAL_STATUSES:
        assert not any(is_legal_transition(terminal, target) for target in JobStatus)


def test_new_jobs_cannot_skip_assignment() -> None:
    for target in (S.SCHEDULED, S.ON_THE_WAY, S.IN_PROGRESS, S.COMPLETED):
        assert not is_legal_transition(S.NEW, target)


def test_illegal_transition_raises_a_structured_error() -> None:
    with pytest.raises(InvalidStateTransitionError) as caught:
        assert_legal_transition(S.COMPLETED, S.IN_PROGRESS)

    assert caught.value.details == {"from": "COMPLETED", "to": "IN_PROGRESS"}
