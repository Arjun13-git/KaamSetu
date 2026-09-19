"""Structured application errors. HTTP status mapping lives in the API layer."""

from enum import StrEnum
from typing import Any, ClassVar


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    AMBIGUOUS_ENTITY = "AMBIGUOUS_ENTITY"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    AI_INVALID_OUTPUT = "AI_INVALID_OUTPUT"
    STORAGE_ERROR = "STORAGE_ERROR"
    SEARCH_UNAVAILABLE = "SEARCH_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    """Base for errors that are safe to show a client. Messages must not contain secrets,
    stack traces, infrastructure details or private customer data."""

    code: ClassVar[ErrorCode] = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class DomainValidationError(DomainError):
    code = ErrorCode.VALIDATION_ERROR


class UnauthorizedError(DomainError):
    code = ErrorCode.UNAUTHORIZED


class ForbiddenError(DomainError):
    code = ErrorCode.FORBIDDEN


class NotFoundError(DomainError):
    """Also raised for records that exist in another business, so ids cannot be probed."""

    code = ErrorCode.NOT_FOUND


class ConflictError(DomainError):
    code = ErrorCode.CONFLICT


class InvalidStateTransitionError(DomainError):
    code = ErrorCode.INVALID_STATE_TRANSITION


class DuplicateRequestError(DomainError):
    code = ErrorCode.DUPLICATE_REQUEST


class StorageError(DomainError):
    code = ErrorCode.STORAGE_ERROR


class AiUnavailableError(DomainError):
    """The model could not be reached or refused the call. The caller falls back to manual entry."""

    code = ErrorCode.AI_UNAVAILABLE


class AiInvalidOutputError(DomainError):
    """The model answered, but not with a record that passes schema validation."""

    code = ErrorCode.AI_INVALID_OUTPUT
