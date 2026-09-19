"""Deterministic normalization used for lookups. Never guesses: invalid input returns ``None``."""

import re
import unicodedata

_NON_DIGITS = re.compile(r"\D")
_MIN_E164_DIGITS = 8
_MAX_E164_DIGITS = 15
_NATIONAL_NUMBER_LENGTH = 10


def normalize_phone(raw: str, default_country_code: str = "91") -> str | None:
    """Return an E.164-style number (``+919876543210``) or ``None`` if it cannot be trusted.

    Numbers without an explicit ``+`` country code are only accepted when they look like a
    national number of the default country; anything else is treated as invalid rather than
    guessed.
    """
    stripped = raw.strip()
    digits = _NON_DIGITS.sub("", stripped)
    if not digits:
        return None

    if stripped.startswith("+"):
        candidate = digits
    elif digits.startswith("00"):
        candidate = digits[2:]
    elif len(digits) == _NATIONAL_NUMBER_LENGTH + 1 and digits.startswith("0"):
        candidate = default_country_code + digits[1:]
    elif len(digits) == _NATIONAL_NUMBER_LENGTH:
        candidate = default_country_code + digits
    elif digits.startswith(default_country_code) and (
        len(digits) == len(default_country_code) + _NATIONAL_NUMBER_LENGTH
    ):
        candidate = digits
    else:
        return None

    if candidate.startswith("0") or not _MIN_E164_DIGITS <= len(candidate) <= _MAX_E164_DIGITS:
        return None
    return f"+{candidate}"


def normalize_name(raw: str) -> str:
    """Case-fold and collapse whitespace so name search is insensitive to both."""
    return " ".join(unicodedata.normalize("NFKC", raw).casefold().split())


def normalize_serial(raw: str) -> str:
    """Upper-case and drop whitespace/hyphens so serial lookups tolerate typing variations."""
    return re.sub(r"[\s-]+", "", raw).upper()
