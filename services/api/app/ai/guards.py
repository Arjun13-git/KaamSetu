"""Deterministic checks applied to a model's (already schema-valid) answer.

The model proposes; these rules have the last word on things code can decide better than a model:
dates in the past, and safety wording, which can only ever raise urgency.
"""

import datetime as dt
import re
from dataclasses import dataclass

from app.ai.schemas import IntakeExtraction, Source, TimePreference
from app.domain.enums import Urgency

# Wording that suggests danger, in English and common Hinglish spellings. Matching only raises the
# urgency for a person to look at; it never diagnoses and never lowers anything.
_SAFETY_PATTERN = re.compile(
    r"\b("
    r"spark(s|ing|ed)?|burning|burnt|smoke|smoking|shock(ed)?|electrocut\w*|fire|flames?|"
    r"short[- ]?circuit|exposed (wire|wires|wiring)|gas (leak|smell)|leaking gas|melt(ed|ing)?|"
    r"chingari|cheengari|aag|dhuan|dhuaan|jalne|jalne ki|current (lag|laga|lagta|lag raha)"
    r")\b",
    re.IGNORECASE,
)


def detect_safety_concern(text: str) -> bool:
    return _SAFETY_PATTERN.search(text) is not None


@dataclass(frozen=True, slots=True)
class GuardResult:
    data: IntakeExtraction
    safety_concern: bool
    warnings: list[str]


def apply_guards(data: IntakeExtraction, *, text: str, today: dt.date) -> GuardResult:
    warnings: list[str] = []
    missing = list(data.missing_information)
    sources = dict(data.sources)
    preference = data.time_preference

    if preference.date is not None and preference.date < today:
        warnings.append("The preferred date is in the past and was ignored")
        preference = TimePreference()
        if "time_preference" not in missing:
            missing.append("time_preference")
        sources.pop("time_preference", None)
    elif preference.start and preference.end and preference.end <= preference.start:
        warnings.append("The preferred end time was not after the start and was ignored")
        preference = preference.evolve(end=None)

    problem = data.problem
    safety = problem.urgency is Urgency.SAFETY_CRITICAL or detect_safety_concern(text)
    if safety and problem.urgency is not Urgency.SAFETY_CRITICAL:
        warnings.append("Safety-related wording was found; urgency was raised to safety_critical")
        problem = problem.evolve(urgency=Urgency.SAFETY_CRITICAL)
        sources["problem.urgency"] = Source.INFERRED

    guarded = data.evolve(
        time_preference=preference, problem=problem, missing_information=missing, sources=sources
    )
    return GuardResult(data=guarded, safety_concern=safety, warnings=warnings)
