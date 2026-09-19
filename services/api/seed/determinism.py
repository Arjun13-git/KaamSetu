"""Readable, repeatable identifiers for the demo dataset.

Production code creates ids with ``app.core.ids.new_id`` (a random UUID). That is right for the
application and wrong for a dataset that must be identical on every run. While a ``readable_ids``
block is active, ids come out as ``<prefix>_demo_<label>_<n>`` (``n`` counts from zero inside the
block), so the same workflow steps always yield the same ids. Nothing in ``app/`` is changed: the
seed only substitutes the UUID source for the duration of the block, then restores it.

Not thread-safe; the seed builds its dataset on a single thread.
"""

import itertools
from collections.abc import Iterator
from contextlib import contextmanager

import app.core.ids as ids


class _Token:
    """Stands in for a UUID: ``new_id`` only reads ``.hex``."""

    def __init__(self, hex: str) -> None:  # noqa: A002 - mirrors uuid.UUID.hex
        self.hex = hex


@contextmanager
def readable_ids(label: str) -> Iterator[None]:
    counter = itertools.count()
    original = ids.uuid4
    ids.uuid4 = lambda: _Token(f"demo_{label}_{next(counter)}")  # type: ignore[assignment]
    try:
        yield
    finally:
        ids.uuid4 = original
