"""One shared free-space pool, kept as a free list per LoROM bank.

Where free space comes from:

- The expansion area (``0x300000-0x3FFFFF`` after ``ensure_rom_expanded``): blank runs of ``0x00`` or ``0xFF``.
- Any other bank, the first time something asks for space in it: runs of ``0x00`` only. This keeps today's
  capsule behaviour (records grow into bank ``$97``'s zero gaps).
- Spans a placement frees (``free``), for example a table's old home after it moved.

Runs keep a 16-byte margin at each end so a neighbour's trailing zeros stay untouched. ``RESERVED_REGIONS`` and
``reserve()``d addresses are never handed out.
"""

import re
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import IO

from constants import EXPANDED_ROM_SIZE, RESERVED_REGIONS
from errors import NoFreeSpace
from helpers.files import write_file
from helpers.rom_expansion import ensure_rom_expanded


BANK_SIZE = 0x8000
MARGIN = 16
MIN_RUN = 64
EXPANSION = range(0x300000, EXPANDED_ROM_SIZE)
_ZEROS = re.compile(rb"\x00+")
_BLANK = re.compile(rb"\x00+|\xff+")


def bank_of(address: int) -> int:
    return address // BANK_SIZE


class FreeSpace:
    def __init__(self, file: IO[bytes], expansion: range | None, reserved: Iterable[range] = ()) -> None:
        self._file = file
        self._reserved = list(reserved)
        self._blocked: set[int] = set()
        self._runs: dict[int, list[list[int]]] = {}
        self._journal: list[tuple[int, int]] | None = None
        self._expansion_banks: set[int] = set()
        if expansion is not None:
            self._expansion_banks = set(range(bank_of(expansion.start), bank_of(expansion.stop - 1) + 1))
            for bank in self._expansion_banks:
                self._rescan(bank)

    # -- building the free lists -------------------------------------------------------------------------------

    def _scan(self, bank: int, pattern: re.Pattern[bytes], *, min_run: int) -> None:
        start = bank * BANK_SIZE
        self._file.seek(start)
        window = self._file.read(BANK_SIZE)
        runs: list[list[int]] = []
        for match in pattern.finditer(window):
            if match.end() - match.start() < min_run:
                continue
            low, high = start + match.start() + MARGIN, start + match.end() - MARGIN
            runs.extend(self._minus_reserved(low, high))
        self._runs[bank] = runs

    def _minus_reserved(self, low: int, high: int) -> list[list[int]]:
        pieces = [[low, high]]
        for region in self._reserved:
            nxt = []
            for a, b in pieces:
                if region.stop <= a or b <= region.start:
                    nxt.append([a, b])
                    continue
                if a < region.start:
                    nxt.append([a, region.start])
                if region.stop < b:
                    nxt.append([region.stop, b])
            pieces = nxt
        return [p for p in pieces if p[1] > p[0]]

    def _rescan(self, bank: int) -> None:
        if bank in self._expansion_banks:
            self._scan(bank, _BLANK, min_run=MIN_RUN)
        else:
            self._scan(bank, _ZEROS, min_run=2 * MARGIN + 1)

    def _bank_runs(self, bank: int) -> list[list[int]]:
        if bank not in self._runs:
            self._rescan(bank)
        return self._runs[bank]

    def _still_blank(self, start: int, size: int) -> bool:
        """Whether ``[start, start+size)`` is still blank: something (asar ``freecode``) may have written it."""
        self._file.seek(start)
        chunk = self._file.read(size)
        return chunk == bytes(size) or (bank_of(start) in self._expansion_banks and chunk == bytes([0xFF]) * size)

    def runs(self) -> list[tuple[int, int]]:
        return sorted((a, b) for runs in self._runs.values() for a, b in runs)

    # -- allocation ----------------------------------------------------------------------------------------

    def reserve(self, addresses: Iterable[int]) -> None:
        self._blocked.update(addresses)

    def _fits(self, candidate: int, size: int, near: int | None, reach: int) -> int | None:
        """First start >= candidate (and >= near) that avoids blocked addresses, or None."""
        if near is not None:
            candidate = max(candidate, near)
        hits = [a for a in self._blocked if candidate <= a < candidate + size]
        while hits:
            candidate = max(hits) + 1
            hits = [a for a in self._blocked if candidate <= a < candidate + size]
        if near is not None and not 0 <= candidate - near <= reach:
            return None
        return candidate

    def alloc(self, size: int, *, bank: int | None = None, near: int | None = None, reach: int = 0xFFFF) -> int:
        if size <= 0:
            msg = f"Cannot allocate {size} bytes."
            raise ValueError(msg)
        banks = [bank] if bank is not None else sorted(self._runs)
        candidates = [(run[1] - run[0], b, run) for b in banks for run in self._bank_runs(b)]
        for _, b, run in sorted(candidates, key=lambda c: (c[0], c[2][0])):
            start = self._fits(run[0], size, near, reach)
            if start is None or start + size > run[1] or bank_of(start) != bank_of(start + size - 1):
                continue
            if not self._still_blank(start, size):
                self._rescan(b)  # the bank changed behind the pool's back; its runs are stale
                return self.alloc(size, bank=bank, near=near, reach=reach)
            self._take(b, run, start, size)
            return start
        where = f"bank {bank:#04x}" if bank is not None else "any bank"
        msg = f"No {size:#x} bytes in {where}" + (f" within {reach:#x} of {near:#x}" if near is not None else "") + "."
        raise NoFreeSpace(msg)

    def alloc_bank(self, size: int) -> int:
        """Space for a whole table: the tightest run in any bank that fits ``size``."""
        return self.alloc(size)

    def _take(self, bank: int, run: list[int], start: int, size: int) -> None:
        runs = self._runs[bank]
        runs.remove(run)
        if run[0] < start:
            runs.append([run[0], start])
        if start + size < run[1]:
            runs.append([start + size, run[1]])
        if self._journal is not None:
            self._journal.append((start, size))

    def release(self, start: int, size: int) -> None:
        """Give ``[start, start+size)`` back to its bank's free list without writing anything."""
        runs = self._bank_runs(bank_of(start))
        merged = [start, start + size]
        for run in list(runs):
            if run[0] == merged[1]:
                merged[1] = run[1]
                runs.remove(run)
            elif run[1] == merged[0]:
                merged[0] = run[0]
                runs.remove(run)
        runs.append(merged)

    def free(self, start: int, size: int) -> None:
        """Zero-fill ``[start, start+size)`` and give it back."""
        self._bank_runs(bank_of(start))  # scan the bank first, or the new zeros would be counted twice
        self._file.seek(start)
        self._file.write(bytes(size))
        self.release(start, size)

    @contextmanager
    def plan(self) -> Iterator[None]:
        """Roll back every allocation made inside the block if an exception escapes it."""
        outer = self._journal
        self._journal = []
        try:
            yield
        except BaseException:
            for start, size in reversed(self._journal):
                self.release(start, size)
            raise
        finally:
            journal = self._journal
            self._journal = outer
            if outer is not None and journal is not None:
                outer.extend(journal)


_pool: FreeSpace | None = None


def pool() -> FreeSpace:
    """The shared pool on ``write_file``. Built on first use, after base patches have been applied."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        ensure_rom_expanded(EXPANDED_ROM_SIZE)
        _pool = FreeSpace(write_file, EXPANSION, RESERVED_REGIONS)
    return _pool


def reset_pool() -> None:
    global _pool  # noqa: PLW0603
    _pool = None
