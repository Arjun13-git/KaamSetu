from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Actor:
    """The authenticated principal. ``business_id`` comes from the server-side auth
    mechanism, never from a request body, query string or client-supplied header."""

    business_id: str
    actor_id: str


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor: Actor
    request_id: str

    @property
    def business_id(self) -> str:
        return self.actor.business_id

    @property
    def actor_id(self) -> str:
        return self.actor.actor_id
