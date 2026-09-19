from datetime import date, datetime

from pydantic import Field

from app.core.context import RequestContext
from app.core.ids import IdPrefix, new_id
from app.domain.asset import Asset
from app.domain.audit import build_audit
from app.domain.base import DomainModel, ShortText
from app.domain.enums import AssetType, AuditAction, AuditEntityType
from app.domain.repositories import Repositories


class NewAsset(DomainModel):
    """Unknown details are omitted (or null) and stay unknown; nothing is inferred."""

    asset_type: AssetType
    brand: ShortText | None = None
    model: ShortText | None = None
    serial_number: ShortText | None = None
    purchase_date: date | None = None
    warranty_until: date | None = None
    location: ShortText | None = None
    metadata: dict[str, str] = Field(default_factory=dict, max_length=20)


def create_asset(
    ctx: RequestContext, repos: Repositories, now: datetime, customer_id: str, data: NewAsset
) -> Asset:
    customer = repos.customers.get(ctx.business_id, customer_id)  # NotFoundError across tenants
    asset = Asset(
        asset_id=new_id(IdPrefix.ASSET),
        business_id=ctx.business_id,
        customer_id=customer.customer_id,
        created_at=now,
        updated_at=now,
        **data.model_dump(),
    )
    repos.assets.create(asset)
    repos.audits.append(
        build_audit(ctx, now, AuditAction.ASSET_CREATED, AuditEntityType.ASSET, asset.asset_id)
    )
    return asset


def get_asset(ctx: RequestContext, repos: Repositories, asset_id: str) -> Asset:
    return repos.assets.get(ctx.business_id, asset_id)


def list_assets(ctx: RequestContext, repos: Repositories, customer_id: str) -> list[Asset]:
    repos.customers.get(ctx.business_id, customer_id)  # NotFoundError across tenants
    return repos.assets.list_by_customer(ctx.business_id, customer_id)
