"""Tests for the ROM-expansion reservations backing ZoneData relocation.

Mirrors ``test_scale_encounters.py::test_reserved_region_is_blank_in_the_base_rom``: a reservation
constant is a claim, not a fact, until checked against the actual bytes of whichever ROM is loaded.
"""

from iris.constants import RESERVED_REGIONS, ZONE_DATA_FREESPACE
from iris.helpers.files import read_file
from iris.helpers.rom_expansion import assert_no_overlaps


_BASE_ROM_SIZE = 3 * 1024 * 1024  # the unexpanded cart


def test_new_regions_live_past_the_base_rom() -> None:
    assert ZONE_DATA_FREESPACE.start >= _BASE_ROM_SIZE
    read_file.seek(0, 2)
    assert read_file.tell() <= _BASE_ROM_SIZE, "base ROM is larger than expected; re-check the reservations"


def test_zone_data_freespace_is_bank_aligned() -> None:
    # Blobs are allocated inside one bank each; starting the pool at a bank boundary wastes nothing on the first one.
    assert ZONE_DATA_FREESPACE.start & 0x7FFF == 0


def test_reserved_regions_do_not_overlap() -> None:
    assert_no_overlaps(RESERVED_REGIONS)


def test_reserved_regions_are_ordered_and_disjoint_by_construction() -> None:
    # A stricter, redundant check purely against the constants (no ROM I/O): catches a typo'd
    # region even if assert_no_overlaps' own logic were ever wrong.
    ordered = sorted(RESERVED_REGIONS, key=lambda r: r.start)
    for a, b in zip(ordered, ordered[1:], strict=False):
        assert a.stop <= b.start
