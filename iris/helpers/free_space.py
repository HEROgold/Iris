"""Find unused (zero-filled) space in the per-seed output ROM."""

import re
from collections.abc import Iterable
from typing import Protocol


class _Seekable(Protocol):
    def seek(self, offset: int, whence: int = 0, /) -> int: ...
    def read(self, size: int = -1, /) -> bytes: ...


MARGIN = 16
"""Zero bytes kept free on each side of an allocation."""

_ZERO_RUN = re.compile(rb"\x00+")


def free_runs(file: _Seekable, start: int, end: int) -> list[tuple[int, int]]:
    """Usable ``[low, high)`` intervals in ``[start, end)``: runs of ``0x00`` minus ``MARGIN`` on each side."""
    file.seek(start)
    window = file.read(end - start)
    runs = []
    for run in _ZERO_RUN.finditer(window):
        low = start + run.start() + MARGIN
        high = start + run.end() - MARGIN
        if high > low:
            runs.append((low, high))
    return runs


def find_free_space(
    file: _Seekable,
    start: int,
    end: int,
    size: int,
    avoid: Iterable[int] = (),
) -> int:
    """Return the lowest address in ``[start, end)`` where ``size`` zero bytes are free.

    A candidate must sit inside a run of ``0x00`` bytes with at least ``MARGIN`` zeros on each side,
    so a neighbouring structure's trailing zeros (terminators, empty table entries) stay untouched.
    Addresses in ``avoid`` (e.g. pointer-table targets) are never covered, even if they hold zeros.
    """
    blocked = sorted(set(avoid))
    for low, high in free_runs(file, start, end):
        candidate = low
        while candidate + size <= high:
            hits = [a for a in blocked if candidate <= a < candidate + size]
            if not hits:
                return candidate
            candidate = hits[-1] + 1 + MARGIN
    msg = f"No {size} free bytes (margin {MARGIN}) in {start:#x}-{end:#x}."
    raise ValueError(msg)
