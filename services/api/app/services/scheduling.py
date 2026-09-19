"""Business-local time handling for extracted visit preferences."""

import datetime as dt
from zoneinfo import ZoneInfo

from app.ai.schemas import TimePreference
from app.core.context import RequestContext
from app.core.errors import NotFoundError
from app.domain.job import TimeSlot
from app.domain.repositories import Repositories


def business_timezone(ctx: RequestContext, repos: Repositories, default: str) -> str:
    """The business's own timezone, or ``default`` if it has no record yet."""
    try:
        return repos.businesses.get(ctx.business_id).timezone
    except NotFoundError:
        return default


def local_today(now: dt.datetime, timezone: str) -> dt.date:
    return now.astimezone(ZoneInfo(timezone)).date()


def preferred_slot(preference: TimePreference, timezone: str) -> TimeSlot | None:
    """A slot only when both a date and a start time were stated. A date alone is not turned into a
    time of day: unknown stays unknown."""
    if preference.date is None or preference.start is None:
        return None
    zone = ZoneInfo(timezone)
    start = dt.datetime.combine(preference.date, preference.start, tzinfo=zone)
    end = None
    if preference.end is not None:
        candidate = dt.datetime.combine(preference.date, preference.end, tzinfo=zone)
        end = candidate if candidate > start else None
    return TimeSlot(start=start, end=end)
