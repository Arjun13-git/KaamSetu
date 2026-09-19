"""Maps every failure to the structured error envelope. Clients never see stack traces, raw input,
infrastructure details or exception text that did not come from a ``DomainError``."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.envelope import ErrorBody, ErrorEnvelope
from app.core.errors import DomainError, ErrorCode

logger = logging.getLogger("kaamsetu.api")

_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.AMBIGUOUS_ENTITY: 409,
    ErrorCode.INVALID_STATE_TRANSITION: 409,
    ErrorCode.DUPLICATE_REQUEST: 409,
    ErrorCode.AI_UNAVAILABLE: 503,
    ErrorCode.AI_INVALID_OUTPUT: 502,
    ErrorCode.STORAGE_ERROR: 503,
    ErrorCode.SEARCH_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}

_CODE_BY_HTTP_STATUS: dict[int, ErrorCode] = {
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
}


def error_response(
    request: Request,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
    *,
    status_code: int | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "req_unknown")
    body = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, details=details or {}), request_id=request_id
    )
    return JSONResponse(
        status_code=status_code or _STATUS_BY_CODE[code],
        content=body.model_dump(mode="json"),
        headers={"X-Request-Id": request_id},
    )


def _validation_details(errors: list[Any]) -> dict[str, Any]:
    """Only where and why a field failed. The submitted value is never echoed back."""
    return {
        "fields": [
            {
                "loc": [str(part) for part in error.get("loc", ())],
                "message": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
            for error in errors
        ]
    }


async def _domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return error_response(request, exc.code, exc.message, exc.details)


async def _request_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return error_response(
        request,
        ErrorCode.VALIDATION_ERROR,
        "The request is not valid",
        _validation_details(list(exc.errors())),
    )


async def _model_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ValidationError)
    return error_response(
        request,
        ErrorCode.VALIDATION_ERROR,
        "The data is not valid",
        _validation_details(exc.errors()),
    )


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code >= 500:
        return error_response(
            request, ErrorCode.INTERNAL_ERROR, "An unexpected error occurred", status_code=500
        )
    code = _CODE_BY_HTTP_STATUS.get(exc.status_code, ErrorCode.VALIDATION_ERROR)
    message = "Resource not found" if code is ErrorCode.NOT_FOUND else "The request was rejected"
    return error_response(request, code, message, status_code=exc.status_code)


async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "req_unknown")
    logger.error("Unhandled error [%s]", request_id, exc_info=exc)
    return error_response(request, ErrorCode.INTERNAL_ERROR, "An unexpected error occurred")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _request_validation_error)
    app.add_exception_handler(ValidationError, _model_validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
