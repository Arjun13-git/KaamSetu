"""Prefixed random identifiers.

Identifiers are created by application code, never by clients, models or the LLM. The
prefix makes an asset ID impossible to mistake for a customer ID when a model is validated.
"""

from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import StringConstraints


class IdPrefix(StrEnum):
    BUSINESS = "bus"
    CUSTOMER = "cus"
    ASSET = "ast"
    TECHNICIAN = "tec"
    SERVICE_REQUEST = "srq"
    JOB = "job"
    SERVICE_EVENT = "evt"
    ATTACHMENT = "att"
    AUDIT = "aud"
    ACTOR = "usr"
    REQUEST = "req"


def new_id(prefix: IdPrefix) -> str:
    return f"{prefix.value}_{uuid4().hex}"


def _pattern(prefix: IdPrefix) -> str:
    return rf"^{prefix.value}_[A-Za-z0-9][A-Za-z0-9_-]{{0,63}}$"


BusinessId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.BUSINESS))]
CustomerId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.CUSTOMER))]
AssetId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.ASSET))]
TechnicianId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.TECHNICIAN))]
ServiceRequestId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.SERVICE_REQUEST))]
JobId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.JOB))]
ServiceEventId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.SERVICE_EVENT))]
AttachmentId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.ATTACHMENT))]
AuditId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.AUDIT))]
ActorId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.ACTOR))]
RequestId = Annotated[str, StringConstraints(pattern=_pattern(IdPrefix.REQUEST))]
