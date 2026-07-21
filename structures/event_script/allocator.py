"""Free-space allocation for compiled (modified/generated) scripts.

Draws from ``constants.EMPTY_BYTES`` and enforces the two SNES constraints that event pointers
require: a script must fit inside a single LoROM 32 KB bank, and it must sit within ``0x7FFF`` of
every pointer that references it (event-list entries are 15-bit relative offsets). Unmodified
scripts keep their original location (Mode A), so this pool is only consumed by dirty scripts.
"""

import logging

from constants import EMPTY_BYTES
from errors import EventFreeSpaceError
from helpers.files import write_file
from logger import iris


log = logging.getLogger(f"{iris.name}.EventScript.Allocator")

BANK_MASK = 0xFF8000
REACH = 0x7FFF


class FreeSpaceAllocator:
    """A mutable free-space pool derived from ``constants.EMPTY_BYTES``."""

    def __init__(self) -> None:
        self._regions: list[list[int]] = [[r.start, r.stop] for r in EMPTY_BYTES]

    def allocate(self, length: int, near: list[int] | None = None) -> int:
        """Reserve ``length`` bytes and return the chosen start offset.

        ``near`` anchors constrain reachability: the region start must be within ``0..0x7FFF`` of
        each anchor. Raises :class:`EventFreeSpaceError` when nothing fits.
        """
        if length <= 0:
            msg = f"Cannot allocate {length} bytes."
            raise EventFreeSpaceError(msg)

        for region in sorted(self._regions, key=lambda r: r[1] - r[0]):
            start, stop = region
            candidate = start
            if candidate + length > stop:
                continue
            if candidate & BANK_MASK != (candidate + length - 1) & BANK_MASK:
                continue
            if near is not None and not all(0 <= candidate - anchor <= REACH for anchor in near):
                continue
            region[0] = candidate + length
            if region[0] >= region[1]:
                self._regions.remove(region)
            return candidate

        msg = "Not enough event free space"
        raise EventFreeSpaceError(msg)

    def write(self, pointer: int, data: bytes) -> None:
        write_file.seek(pointer)
        write_file.write(data)
