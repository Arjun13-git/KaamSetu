"""Domain model <-> DynamoDB item.

Items store the record as native DynamoDB attributes next to the key attributes, so they stay
readable in the AWS console. DynamoDB has no float type, so floats travel as ``Decimal`` and come
back as ``int`` when integral, otherwise ``float``.
"""

import json
from decimal import Decimal
from typing import Any

from app.domain.base import DomainModel

# ``item_type`` is a storage discriminator; it must never collide with a model field name.
INTERNAL_ATTRIBUTES = frozenset(
    {"PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK", "GSI3PK", "GSI3SK"}
    | {"item_type", "name_search"}
)


def to_item(
    model: DomainModel,
    keys: dict[str, str],
    item_type: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(model.model_dump_json(), parse_float=Decimal)
    return {**body, **(extra or {}), **keys, "item_type": item_type}


def from_item[T: DomainModel](item: dict[str, Any], model_type: type[T]) -> T:
    payload = {k: _plain(v) for k, v in item.items() if k not in INTERNAL_ATTRIBUTES}
    return model_type.model_validate(payload)


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value
