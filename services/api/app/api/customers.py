from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, RepositoriesDep, RequestContextDep
from app.api.envelope import SuccessEnvelope
from app.api.schemas import CustomerOut, success
from app.core.ids import CustomerId
from app.services import customer_service
from app.services.customer_service import NewCustomer

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", status_code=201)
def create_customer(
    body: NewCustomer, ctx: RequestContextDep, repos: RepositoriesDep, clock: ClockDep
) -> SuccessEnvelope[CustomerOut]:
    customer = customer_service.create_customer(ctx, repos, clock(), body)
    return success(ctx, CustomerOut.model_validate(customer))


@router.get("")
def find_customers(
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    phone: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SuccessEnvelope[list[CustomerOut]]:
    found = customer_service.find_customers(ctx, repos, query=q, phone=phone, limit=limit)
    return success(ctx, [CustomerOut.model_validate(c) for c in found])


@router.get("/{customer_id}")
def get_customer(
    customer_id: CustomerId, ctx: RequestContextDep, repos: RepositoriesDep
) -> SuccessEnvelope[CustomerOut]:
    customer = customer_service.get_customer(ctx, repos, customer_id)
    return success(ctx, CustomerOut.model_validate(customer))
