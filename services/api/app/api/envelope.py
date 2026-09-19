from typing import Any

from pydantic import BaseModel, Field

from app.core.errors import ErrorCode


class SuccessEnvelope[T](BaseModel):
    data: T
    request_id: str


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody
    request_id: str
