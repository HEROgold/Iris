"""rom_space.place: encodings, in place vs move, pointer rewrites, rollback, read-back."""

import io

import pytest

from errors import NoFreeSpace
from rom_space.place import (
    BankExtended15,
    BytesBlock,
    CodeAbs16,
    CodeBank,
    CodeLong,
    Lorom24,
    Placement,
    PointerSite,
    U16Rel,
    place,
)
from rom_space.pool import BANK_SIZE, FreeSpace


OLD = 0x100
OLD_SIZE = 0x20
GAP = 0x400  # a zero run in bank 0 that the pool finds


def _setup() -> tuple[io.BytesIO, FreeSpace]:
    data = bytearray(b"\x11" * 2 * BANK_SIZE)
    data[GAP : GAP + 0x200] = bytes(0x200)
    rom = io.BytesIO(bytes(data))
    return rom, FreeSpace(rom, expansion=None)


def _read(rom: io.BytesIO, at: int, size: int) -> bytes:
    rom.seek(at)
    return rom.read(size)


@pytest.mark.parametrize(
    ("encoding", "address", "expected"),
    [
        (U16Rel(0xB05C0), 0xB0780, (0x1C0).to_bytes(2, "little")),
        (Lorom24(), 0x310000, bytes([0x00, 0x80, 0xE2])),
        (BankExtended15(0x38000), 0x340010, (0x10 | (0x308000 & 0x7FFF)).to_bytes(2, "little") + bytes([0x308000 >> 15])),
        (CodeLong(), 0xB7ADD, bytes([0xDD, 0xFA, 0x96])),
        (CodeAbs16(), 0xB7ADD, bytes([0xDD, 0xFA])),
        (CodeBank(), 0xB7ADD, bytes([0x96])),
    ],
)
def test_encodings(encoding: object, address: int, expected: bytes) -> None:
    assert encoding.encode(address) == expected  # type: ignore[attr-defined]


def test_delta_is_added() -> None:
    assert PointerSite(0, CodeAbs16(), delta=1).value(0xB4F69) == bytes([0x6A, 0xCF])


def test_fitting_block_is_written_in_place_and_leftover_zeroed() -> None:
    rom, space = _setup()
    site = PointerSite(0x10, U16Rel(0))
    (address,) = place([Placement("t", BytesBlock(b"\x22" * 10), range(OLD, OLD + OLD_SIZE), [site], bank=0)], file=rom, space=space)
    assert address == OLD
    assert _read(rom, OLD, OLD_SIZE) == b"\x22" * 10 + bytes(OLD_SIZE - 10)
    assert _read(rom, 0x10, 2) == b"\x11\x11"  # site untouched when nothing moved


def test_growing_block_moves_rewrites_sites_and_zeroes_the_old_span() -> None:
    rom, space = _setup()
    site = PointerSite(0x10, U16Rel(0))
    (address,) = place([Placement("t", BytesBlock(b"\x33" * 0x40), range(OLD, OLD + OLD_SIZE), [site], bank=0)], file=rom, space=space)
    assert GAP <= address < GAP + 0x200
    assert _read(rom, address, 0x40) == b"\x33" * 0x40
    assert _read(rom, 0x10, 2) == address.to_bytes(2, "little")
    assert _read(rom, OLD, OLD_SIZE) == bytes(OLD_SIZE)


def test_bank_pin_is_respected() -> None:
    rom, space = _setup()
    with pytest.raises(NoFreeSpace):
        place([Placement("t", BytesBlock(b"\x33" * 0x40), range(OLD, OLD + OLD_SIZE), [], bank=1)], file=rom, space=space)


def test_failed_plan_writes_nothing() -> None:
    rom, space = _setup()
    before = rom.getvalue()
    placements = [
        Placement("a", BytesBlock(b"\x44" * 0x40), range(OLD, OLD + OLD_SIZE), [PointerSite(0x10, U16Rel(0))], bank=0),
        Placement("b", BytesBlock(b"\x55" * 0x4000), range(0x200, 0x220), [PointerSite(0x12, U16Rel(0))], bank=0),
    ]
    with pytest.raises(NoFreeSpace):
        place(placements, file=rom, space=space)
    assert rom.getvalue() == before


def test_force_move_moves_even_when_it_fits() -> None:
    rom, space = _setup()
    (address,) = place(
        [Placement("t", BytesBlock(b"\x22" * 4), range(OLD, OLD + OLD_SIZE), [PointerSite(0x10, U16Rel(0))], bank=0, force_move=True)],
        file=rom,
        space=space,
    )
    assert address != OLD


def test_avoided_addresses_are_never_covered() -> None:
    rom, space = _setup()
    space.reserve(range(GAP, GAP + 0x100))
    (address,) = place([Placement("t", BytesBlock(b"\x33" * 0x40), range(OLD, OLD + OLD_SIZE), [], bank=0)], file=rom, space=space)
    assert address >= GAP + 0x100
