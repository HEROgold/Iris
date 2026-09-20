"""Unit tests for helpers.freespace.FreeSpaceAllocator and relocate_pointer_table_entry.

Pure allocator-logic tests: no ROM bytes are read, only helpers.files.write_file (for .write() /
relocate_pointer_table_entry) which the ROM fixture in conftest.py already provides.
"""

from errors import EventFreeSpaceError
from helpers.files import new_file, write_file
from helpers.freespace import BANK_MASK, REACH, FreeSpaceAllocator, relocate_pointer_table_entry
from tests.reset_file import reset_file


def test_allocate_returns_start_of_only_region() -> None:
    allocator = FreeSpaceAllocator(range(0x1000, 0x2000))
    assert allocator.allocate(0x10) == 0x1000


def test_allocate_advances_the_cursor_within_a_region() -> None:
    allocator = FreeSpaceAllocator(range(0x1000, 0x2000))
    first = allocator.allocate(0x10)
    second = allocator.allocate(0x10)
    assert second == first + 0x10


def test_allocate_best_fit_picks_the_smallest_region_that_fits() -> None:
    allocator = FreeSpaceAllocator(range(0, 1))  # placeholder, overwritten below
    allocator._regions = [[0x1000, 0x1100], [0x2000, 0x2020]]  # noqa: SLF001 (test-only poke)
    # Only the small region (0x2000-0x2020, 0x20 bytes) fits a 0x10 request as the *tightest* fit;
    # best-fit must prefer it over the larger 0x1000 region even though that one is listed first.
    chosen = allocator.allocate(0x10)
    assert chosen == 0x2000


def test_allocate_raises_when_nothing_fits() -> None:
    allocator = FreeSpaceAllocator(range(0x1000, 0x1010))
    try:
        allocator.allocate(0x100)
    except EventFreeSpaceError:
        pass
    else:
        msg = "expected EventFreeSpaceError"
        raise AssertionError(msg)


def test_allocate_rejects_non_positive_length() -> None:
    allocator = FreeSpaceAllocator(range(0x1000, 0x2000))
    try:
        allocator.allocate(0)
    except EventFreeSpaceError:
        pass
    else:
        msg = "expected EventFreeSpaceError"
        raise AssertionError(msg)


def test_deallocate_reclaims_space_for_a_later_allocation() -> None:
    allocator = FreeSpaceAllocator(range(0x1000, 0x1010))
    first = allocator.allocate(0x10)  # exhausts the region
    allocator.deallocate(first, 0x10)
    second = allocator.allocate(0x10)
    assert second == first


def test_deallocate_coalesces_with_adjacent_regions_on_both_sides() -> None:
    allocator = FreeSpaceAllocator(range(0x1000, 0x1030))
    a = allocator.allocate(0x10)  # 0x1000-0x1010
    b = allocator.allocate(0x10)  # 0x1010-0x1020
    c = allocator.allocate(0x10)  # 0x1020-0x1030
    allocator.deallocate(a, 0x10)
    allocator.deallocate(c, 0x10)
    allocator.deallocate(b, 0x10)  # should merge all three back into one 0x1000-0x1030 region
    assert allocator._regions == [[0x1000, 0x1030]]  # noqa: SLF001 (test-only poke)


def test_bank_local_rejects_a_candidate_crossing_a_bank_boundary() -> None:
    bank_end = 0x008000  # bank 0x00 ends here; a bank boundary under BANK_MASK
    allocator = FreeSpaceAllocator(range(bank_end - 4, bank_end + 0x10), bank_local=True)
    # An 8-byte allocation starting 4 bytes before the boundary would cross it -- must be refused,
    # so the allocator must skip ahead within the region (there's room after the boundary too).
    chosen = allocator.allocate(8)
    assert chosen & BANK_MASK == (chosen + 8 - 1) & BANK_MASK


def test_near_reach_constraint_is_enforced() -> None:
    allocator = FreeSpaceAllocator(range(0x1000, 0x9000), bank_local=True)
    anchor = 0x1000
    chosen = allocator.allocate(0x10, near=[anchor])
    assert 0 <= chosen - anchor <= REACH


def test_near_reach_constraint_raises_when_unreachable() -> None:
    allocator = FreeSpaceAllocator(range(0x10000, 0x20000))
    try:
        allocator.allocate(0x10, near=[0x0])
    except EventFreeSpaceError:
        pass
    else:
        msg = "expected EventFreeSpaceError"
        raise AssertionError(msg)


def test_relocate_pointer_table_entry_writes_raw_value_without_encode() -> None:
    try:
        address, index, size = 0x1000, 2, 2
        relocate_pointer_table_entry(address, index, size, 0x1234)
        write_file.flush()
        rom = new_file.read_bytes()
        assert rom[address + index * size: address + index * size + size] == (0x1234).to_bytes(2, "little")
    finally:
        reset_file()


def test_relocate_pointer_table_entry_applies_encode() -> None:
    try:
        address, index, size = 0x1000, 2, 3
        relocate_pointer_table_entry(address, index, size, 0x90000, encode=lambda offset: offset + 1)
        write_file.flush()
        rom = new_file.read_bytes()
        assert rom[address + index * size: address + index * size + size] == (0x90001).to_bytes(3, "little")
    finally:
        reset_file()
