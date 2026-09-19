import pytest
from pydantic import TypeAdapter, ValidationError

from app.core.ids import AssetId, CustomerId, IdPrefix, new_id


def test_new_id_carries_prefix_and_is_random() -> None:
    first = new_id(IdPrefix.CUSTOMER)
    second = new_id(IdPrefix.CUSTOMER)

    assert first.startswith("cus_")
    assert first != second


def test_generated_ids_validate_against_their_own_type() -> None:
    TypeAdapter(CustomerId).validate_python(new_id(IdPrefix.CUSTOMER))


def test_an_id_of_the_wrong_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(CustomerId).validate_python(new_id(IdPrefix.ASSET))
    with pytest.raises(ValidationError):
        TypeAdapter(AssetId).validate_python("ast_")
