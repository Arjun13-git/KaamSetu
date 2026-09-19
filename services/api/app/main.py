import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from pydantic import TypeAdapter, ValidationError

from app import __version__
from app.api import health
from app.api.errors import register_exception_handlers
from app.core.config import Settings
from app.core.ids import IdPrefix, RequestId, new_id
from app.domain.repositories import Repositories
from app.providers.persistence.factory import build_repositories

logger = logging.getLogger("kaamsetu.api")

_REQUEST_ID = TypeAdapter(RequestId)


def _request_id_from(header: str | None) -> str:
    """Honour a caller's correlation id only when it is well formed; otherwise mint one."""
    if header:
        try:
            return _REQUEST_ID.validate_python(header)
        except ValidationError:
            pass
    return new_id(IdPrefix.REQUEST)


def create_app(
    settings: Settings | None = None, repositories: Repositories | None = None
) -> FastAPI:
    """Application factory. Run with ``uvicorn app.main:create_app --factory``."""
    settings = settings or Settings()
    expose_docs = settings.app_env != "production"
    app = FastAPI(
        title="KaamSetu API",
        version=__version__,
        docs_url="/docs" if expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    app.state.settings = settings
    app.state.repositories = repositories or build_repositories(settings)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = _request_id_from(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        # Path only: query strings can carry customer search terms and other PII.
        logger.info(
            "%s %s -> %s [%s]", request.method, request.url.path, response.status_code, request_id
        )
        return response

    register_exception_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    return app
