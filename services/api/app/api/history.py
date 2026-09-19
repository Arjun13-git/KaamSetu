from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import RepositoriesDep, RequestContextDep
from app.api.envelope import SuccessEnvelope
from app.api.schemas import (
    AssetHistoryOut,
    AssetOut,
    CustomerHistoryOut,
    CustomerOut,
    JobOut,
    ServiceEventOut,
    success,
)
from app.core.ids import AssetId, CustomerId
from app.services import history_service

router = APIRouter(tags=["history"])

Limit = Annotated[int, Query(ge=1, le=200)]


@router.get("/assets/{asset_id}/history")
def asset_history(
    asset_id: AssetId, ctx: RequestContextDep, repos: RepositoriesDep, limit: Limit = 50
) -> SuccessEnvelope[AssetHistoryOut]:
    history = history_service.asset_history(ctx, repos, asset_id, limit)
    return success(
        ctx,
        AssetHistoryOut(
            asset=AssetOut.model_validate(history.asset),
            jobs=[JobOut.model_validate(j) for j in history.jobs],
            service_events=[ServiceEventOut.model_validate(e) for e in history.events],
        ),
    )


@router.get("/customers/{customer_id}/history")
def customer_history(
    customer_id: CustomerId, ctx: RequestContextDep, repos: RepositoriesDep, limit: Limit = 50
) -> SuccessEnvelope[CustomerHistoryOut]:
    history = history_service.customer_history(ctx, repos, customer_id, limit)
    return success(
        ctx,
        CustomerHistoryOut(
            customer=CustomerOut.model_validate(history.customer),
            assets=[AssetOut.model_validate(a) for a in history.assets],
            jobs=[JobOut.model_validate(j) for j in history.jobs],
            service_events=[ServiceEventOut.model_validate(e) for e in history.events],
        ),
    )
