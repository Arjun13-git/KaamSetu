from datetime import date

from pydantic import Field

from app.core.ids import AssetId, BusinessId, CustomerId
from app.domain.base import ShortText, TimestampedModel
from app.domain.enums import AssetType


class Asset(TimestampedModel):
    """A physical thing a customer owns. Brand, model, serial and warranty stay ``None`` when
    unknown; they are never inferred."""

    asset_id: AssetId
    business_id: BusinessId
    customer_id: CustomerId
    asset_type: AssetType
    brand: ShortText | None = None
    model: ShortText | None = None
    serial_number: ShortText | None = None
    purchase_date: date | None = None
    warranty_until: date | None = None
    location: ShortText | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
