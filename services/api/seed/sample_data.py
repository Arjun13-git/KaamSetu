"""Load the deterministic demo dataset.

    result = load_demo_data(repos, business_id="bus_demo", actor_id="usr_dev")

The dataset is a pure function of ``as_of``: the same inputs always produce the same records, ids
and timestamps. Loading is idempotent and resumable (see ``seed.plan``): running it again changes
nothing, and a run that was interrupted is completed, not duplicated.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.repositories import Repositories
from seed.dataset import DEFAULT_AS_OF, build_demo_plan
from seed.plan import apply_plan


@dataclass(frozen=True, slots=True)
class SeedResult:
    created: dict[str, int]  # records written by this run, by kind
    existing: dict[str, int]  # records that were already present, by kind
    manifest: dict[str, Any]  # ids of everything in the dataset, by kind and key

    @property
    def total_created(self) -> int:
        return sum(self.created.values())

    @property
    def total_existing(self) -> int:
        return sum(self.existing.values())


def load_demo_data(
    repos: Repositories,
    *,
    business_id: str,
    actor_id: str,
    as_of: datetime = DEFAULT_AS_OF,
) -> SeedResult:
    plan = build_demo_plan(business_id, actor_id, as_of)
    tally = apply_plan(plan.ops, repos)
    return SeedResult(dict(tally.created), dict(tally.existing), plan.manifest)
