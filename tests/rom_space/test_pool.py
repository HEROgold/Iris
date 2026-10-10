"""rom_space.pool: per-bank free lists from blank runs, best-fit, bank-local, free/merge, rollback."""

import io
from collections.abc import Iterator

import pytest

from constants import EXPANDED_ROM_SIZE, RESERVED_REGIONS
from enums.patches import Patch
from errors import NoFreeSpace
from helpers.files import write_file
from patcher import apply_patch
from rom_space.pool import BANK_SIZE, FreeSpace, bank_of, pool, reset_pool
from tests.reset_file import reset_file


def _rom(banks: int, blank: dict[int, bytes] | None = None) -> io.BytesIO:
    data = bytearray(b"\x11" * banks * BANK_SIZE)
    for start, content in (blank or {}).items():
        data[start : start + len(content)] = content
    return io.BytesIO(bytes(data))


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    reset_file()
    reset_pool()
    yield
    reset_file()
    reset_pool()


def test_expansion_banks_are_free_minus_margins() -> None:
    space = FreeSpace(_rom(2, {0: bytes(2 * BANK_SIZE)}), expansion=range(0, 2 * BANK_SIZE))
    first = space.alloc(0x100)
    assert first == 16  # noqa: PLR2004 (16-byte margin)


def test_alloc_never_crosses_a_bank() -> None:
    space = FreeSpace(_rom(2, {0: bytes(2 * BANK_SIZE)}), expansion=range(0, 2 * BANK_SIZE))
    start = space.alloc(BANK_SIZE - 64)
    assert bank_of(start) == bank_of(start + BANK_SIZE - 64 - 1)


def test_best_fit_prefers_the_smallest_run() -> None:
    rom = _rom(1, {0x100: bytes(0x400), 0x1000: bytes(0x60)})
    space = FreeSpace(rom, expansion=None)
    assert space.alloc(0x20, bank=0) == 0x1000 + 16


def test_native_banks_are_scanned_for_zero_runs_on_first_use() -> None:
    rom = _rom(2, {BANK_SIZE + 0x200: bytes(0x80)})
    space = FreeSpace(rom, expansion=None)
    assert space.alloc(0x40, bank=1) == BANK_SIZE + 0x200 + 16


def test_ff_runs_count_only_in_the_expansion_area() -> None:
    rom = _rom(2, {0x200: b"\xff" * 0x100, BANK_SIZE: b"\xff" * BANK_SIZE})
    space = FreeSpace(rom, expansion=range(BANK_SIZE, 2 * BANK_SIZE))
    with pytest.raises(NoFreeSpace):
        space.alloc(0x40, bank=0)
    assert bank_of(space.alloc(0x40)) == 1


def test_near_and_reach() -> None:
    space = FreeSpace(_rom(2, {0: bytes(2 * BANK_SIZE)}), expansion=range(0, 2 * BANK_SIZE))
    start = space.alloc(0x10, near=BANK_SIZE, reach=0x100)
    assert 0 <= start - BANK_SIZE <= 0x100


def test_reserved_addresses_are_never_handed_out() -> None:
    rom = _rom(1, {0x100: bytes(0x100)})
    space = FreeSpace(rom, expansion=None)
    space.reserve([0x100 + 16 + 4])
    start = space.alloc(0x10, bank=0)
    assert not start <= 0x100 + 16 + 4 < start + 0x10


def test_free_zero_fills_and_merges() -> None:
    rom = _rom(1)
    space = FreeSpace(rom, expansion=None)
    space.free(0x200, 0x40)
    space.free(0x240, 0x40)
    rom.seek(0x200)
    assert rom.read(0x80) == bytes(0x80)
    assert space.alloc(0x80, bank=0) == 0x200


def test_plan_rolls_back_every_allocation_on_failure() -> None:
    rom = _rom(1, {0x100: bytes(0x200)})
    space = FreeSpace(rom, expansion=None)
    with pytest.raises(NoFreeSpace), space.plan():
        space.alloc(0x40, bank=0)
        space.alloc(0x40, bank=0)
        space.alloc(0x1000, bank=0)
    assert space.alloc(0x200 - 32, bank=0) == 0x100 + 16


def test_no_free_space_names_size_and_bank() -> None:
    space = FreeSpace(_rom(1), expansion=None)
    with pytest.raises(NoFreeSpace, match="0x40 bytes in bank 0x00"):
        space.alloc(0x40, bank=0)


def test_pool_expands_the_vanilla_rom_once() -> None:
    pool()
    write_file.seek(0, 2)
    assert write_file.tell() == EXPANDED_ROM_SIZE
    reset_pool()
    pool()
    write_file.seek(0, 2)
    assert write_file.tell() == EXPANDED_ROM_SIZE


@pytest.mark.parametrize("base", [None, Patch.FRUE, Patch.SPEKKIO, Patch.KUREJI])
def test_every_offered_range_is_blank_and_unreserved(base: Patch | None) -> None:
    if base is not None:
        apply_patch(base)
    space = pool()
    for start, stop in space.runs():
        write_file.seek(start)
        chunk = write_file.read(stop - start)
        assert chunk.strip(b"\x00") == b"" or chunk.strip(b"\xff") == b"", hex(start)
        assert not any(start < r.stop and r.start < stop for r in RESERVED_REGIONS), hex(start)


def test_near_uses_the_part_of_a_run_after_the_anchor() -> None:
    rom = _rom(1, {0x100: bytes(0x400)})
    space = FreeSpace(rom, expansion=None)
    assert space.alloc(0x40, bank=0, near=0x300) == 0x300


def test_bytes_written_behind_the_pools_back_are_not_handed_out() -> None:
    rom = _rom(1, {0x100: bytes(0x200)})
    space = FreeSpace(rom, expansion=None)
    space.alloc(0x10, bank=0)  # the bank is scanned now
    rom.seek(0x100 + 16)
    rom.write(b"\x5c" * 0x100)  # e.g. asar freecode after the scan
    start = space.alloc(0x40, bank=0)
    rom.seek(start)
    assert rom.read(0x40) == bytes(0x40)
