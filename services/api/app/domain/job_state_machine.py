"""The job status graph. Callers may *request* a transition; this module decides legality.

Progression is forward-only. ``SCHEDULED`` and ``ON_THE_WAY`` may be skipped. ``CANCELLED`` is
reachable from any pre-completion state. ``COMPLETED`` and ``CANCELLED`` are terminal.

The graph alone is not the whole rule: ``ASSIGNED`` is entered only by assigning a technician and
``COMPLETED`` only by the completion use case (see ``job_workflow``).
"""

from app.core.errors import InvalidStateTransitionError
from app.domain.enums import JobStatus

_S = JobStatus

_LEGAL_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    _S.NEW: frozenset({_S.ASSIGNED, _S.CANCELLED}),
    _S.ASSIGNED: frozenset({_S.SCHEDULED, _S.ON_THE_WAY, _S.IN_PROGRESS, _S.CANCELLED}),
    _S.SCHEDULED: frozenset({_S.ON_THE_WAY, _S.IN_PROGRESS, _S.CANCELLED}),
    _S.ON_THE_WAY: frozenset({_S.IN_PROGRESS, _S.CANCELLED}),
    _S.IN_PROGRESS: frozenset({_S.COMPLETED, _S.CANCELLED}),
    _S.COMPLETED: frozenset(),
    _S.CANCELLED: frozenset(),
}

TERMINAL_STATUSES = frozenset({_S.COMPLETED, _S.CANCELLED})


def is_legal_transition(current: JobStatus, target: JobStatus) -> bool:
    return target in _LEGAL_TRANSITIONS[current]


def assert_legal_transition(current: JobStatus, target: JobStatus) -> None:
    if not is_legal_transition(current, target):
        raise InvalidStateTransitionError(
            f"A {current.value} job cannot move to {target.value}",
            details={"from": current.value, "to": target.value},
        )
