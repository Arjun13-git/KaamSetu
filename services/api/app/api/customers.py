from datetime import datetime
from typing import Self

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import ClockDep, RepositoriesDep, RequestContextDep
from app.api.envelope import SuccessEnvelope
from app.core.ids import CustomerId
from app.domain.customer import Customer
from app.services import customer_service
from app.services.customer_service import NewCustomer

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerOut(BaseModel):
    """Public shape of a customer. The owning business is implied by the caller and not echoed."""

    customer_id: str
    name: str
    phone: str | None
    email: str | None
    address: str | None
    preferred_language: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_customer(cls, customer: Customer) -> Self:
        return cls(
            customer_id=customer.customer_id,
            name=customer.name,
            phone=customer.phone,
            email=customer.email,
            address=customer.address,
            preferred_language=customer.preferred_language,
            notes=customer.notes,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )


@router.post("", status_code=201)
def create_customer(
    body: NewCustomer, ctx: RequestContextDep, repos: RepositoriesDep, clock: ClockDep
) -> SuccessEnvelope[CustomerOut]:
    customer = customer_service.create_customer(ctx, repos, clock(), body)
    return SuccessEnvelope(data=CustomerOut.from_customer(customer), request_id=ctx.request_id)


@router.get("/{customer_id}")
def get_customer(
    customer_id: CustomerId, ctx: RequestContextDep, repos: RepositoriesDep
) -> SuccessEnvelope[CustomerOut]:
    customer = customer_service.get_customer(ctx, repos, customer_id)
    return SuccessEnvelope(data=CustomerOut.from_customer(customer), request_id=ctx.request_id)
