"""A generic, relocating free-space allocator.

Two distinct concerns, kept separate. ``helpers.rom_expansion`` answers "which fixed range of bytes
may I use at all" -- checked once, statically, against one reserved region (e.g.
``constants.ZONE_DATA_FREESPACE``). This module answers "how do many small, growing/shrinking
allocations *within* that range come and go across one run without colliding" -- a free-list
allocator, not a bump cursor, so relocating the same blob repeatedly reclaims its old slot instead
of leaking space forever.

Modeled on terrorwave's ``MapMetaObject``/``MapEventObject`` allocators (best-fit search,
deallocate-with-coalesce), generalized so every consumer of a given region shares one instance --
directly fixing the "two independent bump allocators can collide" problem
``structures/zone.py``'s ``_free_cursor`` and ``structures/event_script/allocator.py``'s
``FreeSpaceAllocator`` have today (each draws from ``constants.EMPTY_BYTES`` independently).
"""

from collections.abc import Callable

from constants import EVENT_SCRIPT_FREESPACE, ZONE_DATA_FREESPACE
from errors import EventFreeSpaceError
from helpers.files import write_file


BANK_MASK = 0xFF8000
REACH = 0x7FFF


class FreeSpaceAllocator:
    """A mutable best-fit free-list over one fixed region.

    ``bank_local=True`` additionally refuses a candidate that would cross a 32KB LoROM bank
    boundary, and lets ``allocate`` take ``near`` anchors that must stay within a 15-bit (``0x7FFF``)
    relative reach -- the two constraints Lufia II's event-list pointers need (see
    ``structures.event_script.allocator``, whose ``FreeSpaceAllocator`` this generalizes/replaces).
    ZoneData relocation needs neither constraint, hence the flag rather than always enforcing them.
    """

    def __init__(self, region: range, *, bank_local: bool = False) -> None:
        self._regions: list[list[int]] = [[region.start, region.stop]]
        self._bank_local = bank_local

    def allocate(self, length: int, *, near: list[int] | None = None) -> int:
        """Reserve ``length`` bytes and return the chosen start offset.

        Best-fit: the smallest region that still fits is used first, which fragments the pool less
        than first-fit over many allocate/deallocate cycles. Raises :class:`EventFreeSpaceError`
        when nothing fits.
        """
        if length <= 0:
            msg = f"Cannot allocate {length} bytes."
            raise EventFreeSpaceError(msg)

        for region in sorted(self._regions, key=lambda r: r[1] - r[0]):
            start, stop = region
            for candidate in self._candidates(start, stop):
                if candidate + length > stop:
                    continue
                if self._bank_local and candidate & BANK_MASK != (candidate + length - 1) & BANK_MASK:
                    continue
                if near is not None and not all(0 <= candidate - anchor <= REACH for anchor in near):
                    continue
                region[0] = candidate + length
                if region[0] >= region[1]:
                    self._regions.remove(region)
                return candidate

        msg = "Not enough free space in this allocator's region."
        raise EventFreeSpaceError(msg)

    def _candidates(self, start: int, stop: int) -> list[int]:
        """Candidate start offsets to try within one region, in preference order.

        Plain ``start`` first. For a bank-local allocator, also try the start of the *next* bank if
        it's still inside the region: without this, a single dedicated region (unlike the several
        disjoint ``EMPTY_BYTES`` ranges the original event-script allocator drew from) would get
        permanently stuck the moment its cursor drifted within reach of a bank boundary, even though
        plenty of free space remains just past it. The skipped bytes are simply not reclaimed (bank
        padding), same as real ROM layout tools accept.
        """
        candidates = [start]
        if self._bank_local:
            next_bank = (start & ~REACH) + REACH + 1
            if start < next_bank < stop:
                candidates.append(next_bank)
        return candidates

    def deallocate(self, start: int, length: int) -> None:
        """Return ``[start, start+length)`` to the pool, coalescing with any adjacent free region.

        Lets a repeatedly-relocated blob (the same map/script written many times in one run) give
        its previous slot back instead of the pool monotonically shrinking.
        """
        if length <= 0:
            return
        merged = [start, start + length]
        for region in list(self._regions):
            if region[0] == merged[1]:
                merged[1] = region[1]
                self._regions.remove(region)
            elif region[1] == merged[0]:
                merged[0] = region[0]
                self._regions.remove(region)
        self._regions.append(merged)

    def write(self, pointer: int, data: bytes) -> None:
        write_file.seek(pointer)
        write_file.write(data)


def relocate_pointer_table_entry(
    address: int,
    index: int,
    size: int,
    new_offset: int,
    *,
    encode: Callable[[int], int] | None = None,
) -> None:
    """Overwrite one entry of a fixed-stride pointer table with an (optionally encoded) value.

    Generalizes ``helpers.bits.update_pointer_table`` (hardcoded to ``constants.POINTER_SIZE``, 2
    bytes) to any entry width -- e.g. ZoneData's 3-byte LoROM pointer table at ``0x27FCBC``.
    ``encode`` transforms the plain (headerless PC) offset into whatever the table actually stores
    (e.g. ``helpers.addresses.address_to_lorom``); omit it for a table that stores the raw offset.
    """
    value = new_offset if encode is None else encode(new_offset)
    write_file.seek(address + index * size)
    write_file.write(value.to_bytes(size, "little"))


# One process-wide instance per reserved region: every caller in a run shares the same free-list,
# so two relocations into the same pool cannot pick overlapping bytes (fixes the "zone.py's bump
# cursor and event_script/allocator.py's FreeSpaceAllocator never coordinated" gap -- both drew
# independently from constants.EMPTY_BYTES, which is also just plain wrong; see that constant).
zone_data_allocator = FreeSpaceAllocator(ZONE_DATA_FREESPACE)
event_script_allocator = FreeSpaceAllocator(EVENT_SCRIPT_FREESPACE, bank_local=True)
