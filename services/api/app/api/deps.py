import hmac
from typing import Annotated

from fastapi import Depends, Header, Request

from app.ai.extractor import IntakeExtractor
from app.core.clock import Clock
from app.core.config import Settings
from app.core.context import Actor, RequestContext
from app.core.errors import UnauthorizedError
from app.domain.repositories import Repositories

DEMO_KEY_HEADER = "x-demo-key"


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_repositories(request: Request) -> Repositories:
    repositories: Repositories = request.app.state.repositories
    return repositories


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


def get_extractor(request: Request) -> IntakeExtractor:
    extractor: IntakeExtractor = request.app.state.extractor
    return extractor


def get_request_id(request: Request) -> str:
    request_id: str = request.state.request_id
    return request_id


IdempotencyKeyHeader = Annotated[
    str | None, Header(alias="Idempotency-Key", pattern=r"^[A-Za-z0-9_:.-]{1,128}$")
]

SettingsDep = Annotated[Settings, Depends(get_settings)]
RepositoriesDep = Annotated[Repositories, Depends(get_repositories)]
ClockDep = Annotated[Clock, Depends(get_clock)]
ExtractorDep = Annotated[IntakeExtractor, Depends(get_extractor)]
RequestIdDep = Annotated[str, Depends(get_request_id)]


def _demo_key_is_valid(request: Request, settings: Settings) -> bool:
    if settings.demo_api_key is None:
        return False
    supplied = request.headers.get(DEMO_KEY_HEADER, "")
    expected = settings.demo_api_key.get_secret_value()
    return hmac.compare_digest(supplied.encode(), expected.encode())


def get_actor(request: Request, settings: SettingsDep) -> Actor:
    """Who is calling, decided entirely server-side.

    Until real authentication exists the only identity is a fixed one. It is available without
    credentials in ``development``/``test``, to holders of the shared key in ``demo``, and never in
    ``production``. The tenant is never read from the request, and a missing key and a wrong key
    are indistinguishable to the caller.
    """
    allowed = settings.dev_actor_enabled or (
        settings.demo_actor_enabled and _demo_key_is_valid(request, settings)
    )
    if not allowed:
        raise UnauthorizedError("Authentication is required")
    return Actor(business_id=settings.dev_business_id, actor_id=settings.dev_actor_id)


ActorDep = Annotated[Actor, Depends(get_actor)]


def get_request_context(actor: ActorDep, request_id: RequestIdDep) -> RequestContext:
    return RequestContext(actor=actor, request_id=request_id)


RequestContextDep = Annotated[RequestContext, Depends(get_request_context)]
