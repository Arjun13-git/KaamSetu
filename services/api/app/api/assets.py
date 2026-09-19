from fastapi import APIRouter

from app.api.deps import ClockDep, RepositoriesDep, RequestContextDep
from app.api.envelope import SuccessEnvelope
from app.api.schemas import AssetOut, success
from app.core.ids import AssetId, CustomerId
from app.services import asset_service
from app.services.asset_service import NewAsset

router = APIRouter(tags=["assets"])


@router.post("/customers/{customer_id}/assets", status_code=201)
def create_asset(
    customer_id: CustomerId,
    body: NewAsset,
    ctx: RequestContextDep,
    repos: RepositoriesDep,
    clock: ClockDep,
) -> SuccessEnvelope[AssetOut]:
    asset = asset_service.create_asset(ctx, repos, clock(), customer_id, body)
    return success(ctx, AssetOut.model_validate(asset))


@router.get("/customers/{customer_id}/assets")
def list_assets(
    customer_id: CustomerId, ctx: RequestContextDep, repos: RepositoriesDep
) -> SuccessEnvelope[list[AssetOut]]:
    found = asset_service.list_assets(ctx, repos, customer_id)
    return success(ctx, [AssetOut.model_validate(a) for a in found])


@router.get("/assets/{asset_id}")
def get_asset(
    asset_id: AssetId, ctx: RequestContextDep, repos: RepositoriesDep
) -> SuccessEnvelope[AssetOut]:
    return success(ctx, AssetOut.model_validate(asset_service.get_asset(ctx, repos, asset_id)))
