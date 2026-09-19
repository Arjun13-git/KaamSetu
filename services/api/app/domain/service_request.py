from typing import Annotated, Any, Self

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from app.core.ids import AssetId, AttachmentId, BusinessId, CustomerId, JobId, ServiceRequestId
from app.domain.base import DomainModel, ShortText, TimestampedModel
from app.domain.enums import ResolutionState, ServiceRequestStatus

RawText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
IdempotencyKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_:.-]{1,128}$")]

_CUSTOMER_ID = TypeAdapter(CustomerId)
_ASSET_ID = TypeAdapter(AssetId)


class MatchCandidate(DomainModel):
    """A possible existing record. A score is evidence for a human, never authorization."""

    entity_id: ShortText
    match_score: float = Field(ge=0, le=1)
    reasons: list[ShortText] = Field(default_factory=list, max_length=10)


class EntityResolution(DomainModel):
    """Whether a request maps to a new, an existing or an ambiguous customer/asset.

    ``AMBIGUOUS`` and ``UNRESOLVED`` never carry a chosen ``entity_id``: a person (or a
    deterministic rule) must resolve them first.
    """

    state: ResolutionState = ResolutionState.UNRESOLVED
    entity_id: ShortText | None = None
    candidates: list[MatchCandidate] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _check_state(self) -> Self:
        if self.state is ResolutionState.EXISTING and self.entity_id is None:
            raise ValueError("an EXISTING resolution requires an entity_id")
        if self.state is not ResolutionState.EXISTING and self.entity_id is not None:
            raise ValueError(f"a {self.state.value} resolution cannot carry an entity_id")
        if self.state is ResolutionState.AMBIGUOUS and len(self.candidates) < 2:
            raise ValueError("an AMBIGUOUS resolution requires at least two candidates")
        return self


class ServiceRequest(TimestampedModel):
    """The preserved intake record: what the customer said, what was understood, and how far
    resolution got. The Job is the operational record created from it.

    ``raw_text`` and ``extraction`` are untrusted data. ``extraction`` holds the validated
    structured extraction (with confidence/uncertainty) once the AI workflow defines its schema.
    """

    service_request_id: ServiceRequestId
    business_id: BusinessId
    raw_text: RawText
    status: ServiceRequestStatus = ServiceRequestStatus.RECEIVED
    extraction: dict[str, Any] | None = None
    customer_resolution: EntityResolution = Field(default_factory=EntityResolution)
    asset_resolution: EntityResolution = Field(default_factory=EntityResolution)
    attachment_ids: list[AttachmentId] = Field(default_factory=list, max_length=10)
    idempotency_key: IdempotencyKey | None = None
    failure_reason: ShortText | None = None
    job_id: JobId | None = None
    version: int = 1

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if self.version < 1:
            raise ValueError("version must be at least 1")
        if (self.status is ServiceRequestStatus.JOB_CREATED) != (self.job_id is not None):
            raise ValueError("job_id must be set if and only if the request is JOB_CREATED")
        customer_id = self.customer_resolution.entity_id
        if customer_id is not None:
            _CUSTOMER_ID.validate_python(customer_id)
        asset_id = self.asset_resolution.entity_id
        if asset_id is not None:
            _ASSET_ID.validate_python(asset_id)
        return self
