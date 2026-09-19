from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.core.context import Actor, RequestContext
from app.core.errors import UnauthorizedError
from app.domain.repositories import Repositories


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_repositories(request: Request) -> Repositories:
    repositories: Repositories = request.app.state.repositories
    return repositories


def get_request_id(request: Request) -> str:
    request_id: str = request.state.request_id
    return request_id


SettingsDep = Annotated[Settings, Depends(get_settings)]
RepositoriesDep = Annotated[Repositories, Depends(get_repositories)]
RequestIdDep = Annotated[str, Depends(get_request_id)]


def get_actor(settings: SettingsDep) -> Actor:
    """Who is calling, decided entirely server-side.

    Until real authentication exists this is a fixed development identity that is available only
    in ``development``/``test``. It deliberately never reads a business or user id from the
    request, and any other environment is refused rather than defaulted.
    """
    if not settings.dev_actor_enabled:
        raise UnauthorizedError("Authentication is required")
    return Actor(business_id=settings.dev_business_id, actor_id=settings.dev_actor_id)


ActorDep = Annotated[Actor, Depends(get_actor)]


def get_request_context(actor: ActorDep, request_id: RequestIdDep) -> RequestContext:
    return RequestContext(actor=actor, request_id=request_id)


RequestContextDep = Annotated[RequestContext, Depends(get_request_context)]
