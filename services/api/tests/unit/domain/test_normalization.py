import pytest

from app.domain.normalization import normalize_name, normalize_phone, normalize_serial


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("98765 43210", "+919876543210"),
        ("09876543210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("+91-98765-43210", "+919876543210"),
        ("0091 98765 43210", "+919876543210"),
        ("+1 (415) 555-2671", "+14155552671"),
    ],
)
def test_phone_numbers_normalize_to_e164(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "12345", "+0123456789", "98765", "+1234567890123456"])
def test_untrustworthy_phone_numbers_are_rejected_not_guessed(raw: str) -> None:
    assert normalize_phone(raw) is None


def test_name_normalization_ignores_case_and_spacing() -> None:
    assert normalize_name("  RAVI   Kumar ") == "ravi kumar"


def test_serial_normalization_ignores_case_spaces_and_hyphens() -> None:
    assert normalize_serial("ab-12 34") == "AB1234"
