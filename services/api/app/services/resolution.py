"""Deterministic customer and asset resolution.

The model may *mention* a name or an appliance, but it never chooses a record. A customer is treated
as existing only on explicit evidence (the operator selected them, or the sender's phone number
matches exactly one customer). A name alone only ever produces candidates for a person to confirm.
An asset is matched only within an already-resolved customer, and only automatically when exactly
one of their assets fits what was said. Anything less is left for a human.
"""

from app.ai.schemas import AssetMention
from app.domain.asset import Asset
from app.domain.enums import AssetType, ResolutionState
from app.domain.normalization import normalize_name
from app.domain.repositories import Repositories
from app.domain.service_request import EntityResolution, MatchCandidate

# An asset is attached automatically only if the model was at least this sure of what it described.
ASSET_MIN_CONFIDENCE = 0.7
_MAX_CANDIDATES = 5


def resolve_customer(
    repos: Repositories,
    business_id: str,
    *,
    customer_id: str | None,
    phone: str | None,
    name_hint: str | None,
) -> EntityResolution:
    if customer_id is not None:
        customer = repos.customers.get(business_id, customer_id)
        return EntityResolution(
            state=ResolutionState.EXISTING,
            entity_id=customer.customer_id,
            candidates=[_candidate(customer.customer_id, 1.0, "selected by the operator")],
        )

    if phone is not None:
        by_phone = repos.customers.find_by_phone(business_id, phone)
        if len(by_phone) == 1:
            return EntityResolution(
                state=ResolutionState.EXISTING,
                entity_id=by_phone[0].customer_id,
                candidates=[_candidate(by_phone[0].customer_id, 0.95, "phone number matches")],
            )
        if len(by_phone) > 1:
            return EntityResolution(
                state=ResolutionState.AMBIGUOUS,
                candidates=[
                    _candidate(c.customer_id, 0.5, "phone number is shared")
                    for c in by_phone[:_MAX_CANDIDATES]
                ],
            )

    if name_hint:
        by_name = repos.customers.search_by_name(business_id, name_hint, limit=_MAX_CANDIDATES)
        if by_name:
            wanted = normalize_name(name_hint)
            candidates = [
                _candidate(c.customer_id, 0.8, "name matches exactly")
                if normalize_name(c.name) == wanted
                else _candidate(c.customer_id, 0.5, "name contains the mentioned name")
                for c in by_name
            ]
            # A name is never enough to choose: even one candidate waits for confirmation.
            state = ResolutionState.AMBIGUOUS if len(candidates) > 1 else ResolutionState.UNRESOLVED
            return EntityResolution(state=state, candidates=candidates)

    if phone is not None or name_hint:
        return EntityResolution(state=ResolutionState.NEW)
    return EntityResolution(state=ResolutionState.UNRESOLVED)


def resolve_asset(
    repos: Repositories,
    business_id: str,
    customer: EntityResolution,
    mention: AssetMention,
    confidence: float,
) -> EntityResolution:
    if customer.state is ResolutionState.NEW:
        return EntityResolution(state=ResolutionState.NEW)  # a new customer has no assets yet
    if customer.state is not ResolutionState.EXISTING or customer.entity_id is None:
        return EntityResolution(state=ResolutionState.UNRESOLVED)

    assets = repos.assets.list_by_customer(business_id, customer.entity_id)
    if not assets:
        return EntityResolution(state=ResolutionState.NEW)

    said_nothing_useful = mention.type is AssetType.UNKNOWN and not mention.brand
    if said_nothing_useful:
        return EntityResolution(
            state=ResolutionState.UNRESOLVED,
            candidates=[
                _candidate(a.asset_id, 0.3, "an asset of this customer")
                for a in assets[:_MAX_CANDIDATES]
            ],
        )

    scored = [(score, a) for a in assets if (score := _asset_score(a, mention)) is not None]
    if not scored:
        return EntityResolution(state=ResolutionState.NEW)
    scored.sort(key=lambda pair: pair[0], reverse=True)
    candidates = [
        _candidate(a.asset_id, score, _asset_reason(a, mention))
        for score, a in scored[:_MAX_CANDIDATES]
    ]

    if len(scored) > 1:
        return EntityResolution(state=ResolutionState.AMBIGUOUS, candidates=candidates)
    matched_type = mention.type is not AssetType.UNKNOWN
    if matched_type and confidence >= ASSET_MIN_CONFIDENCE:
        return EntityResolution(
            state=ResolutionState.EXISTING, entity_id=scored[0][1].asset_id, candidates=candidates
        )
    return EntityResolution(state=ResolutionState.UNRESOLVED, candidates=candidates)


def _asset_score(asset: Asset, mention: AssetMention) -> float | None:
    """How well an existing asset fits what was said, or ``None`` if it plainly does not."""
    score = 0.3
    if mention.type is not AssetType.UNKNOWN:
        if asset.asset_type is not mention.type:
            return None
        score = 0.6
    if mention.brand and asset.brand:
        if asset.brand.casefold() != mention.brand.casefold():
            return None
        score += 0.3
    if mention.model and asset.model:
        if asset.model.casefold() != mention.model.casefold():
            return None
        score += 0.1
    return round(min(score, 1.0), 2)


def _asset_reason(asset: Asset, mention: AssetMention) -> str:
    parts = []
    if mention.type is not AssetType.UNKNOWN:
        parts.append("type matches")
    if mention.brand and asset.brand:
        parts.append("brand matches")
    if mention.model and asset.model:
        parts.append("model matches")
    return ", ".join(parts) or "an asset of this customer"


def _candidate(entity_id: str, score: float, reason: str) -> MatchCandidate:
    return MatchCandidate(entity_id=entity_id, match_score=score, reasons=[reason])
