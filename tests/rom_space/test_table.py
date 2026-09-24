"""rom_space.Table on a synthetic bank: each write step, code refs, pinned addresses, writing twice."""

import io
from dataclasses import dataclass

import pytest

from errors import CodeRefMismatch, NoFreeSpace, TableNotMovable
from rom_space.place import CodeAbs16, CodeBank, CodeLong, PointerSite
from rom_space.pool import BANK_SIZE, FreeSpace, bank_of
from rom_space.table import Table


TABLE = 0x8000  # bank 1
COUNT = 3
FIRST = TABLE + 2 * COUNT
RECORDS = [b"\xa1" * 8, b"\xb2" * 8, b"\xc3" * 8]
REGION_END = FIRST + 3 * 8 + 4  # 4 bytes of slack after the last record
GAP = 0x9000  # zero run in bank 1
CODE = 0x100  # fake code refs in bank 0
EXPANSION = range(2 * BANK_SIZE, 3 * BANK_SIZE)


@dataclass
class _Rec:
    data: bytes

    def build(self) -> bytes:
        return self.data


def _rom(*, gap: int = 0x100) -> io.BytesIO:
    data = bytearray(b"\x11" * 3 * BANK_SIZE)
    data[EXPANSION.start : EXPANSION.stop] = bytes(BANK_SIZE)
    pos = FIRST
    for i, rec in enumerate(RECORDS):
        data[TABLE + 2 * i : TABLE + 2 * i + 2] = (pos - TABLE).to_bytes(2, "little")
        data[pos : pos + len(rec)] = rec
        pos += len(rec)
    data[pos:REGION_END] = bytes(REGION_END - pos)
    data[GAP : GAP + gap] = bytes(gap)
    refs = [(CODE, CodeLong()), (CODE + 3, CodeAbs16()), (CODE + 5, CodeBank())]
    for at, encoding in refs:
        data[at : at + encoding.width] = encoding.encode(TABLE)
    return io.BytesIO(bytes(data))


def _table(rom: io.BytesIO, records: list[bytes], **kwargs: object) -> tuple[Table, FreeSpace]:
    space = FreeSpace(rom, expansion=EXPANSION)
    refs = [PointerSite(CODE, CodeLong()), PointerSite(CODE + 3, CodeAbs16()), PointerSite(CODE + 5, CodeBank())]
    table = Table("t", TABLE, [_Rec(r) for r in records], REGION_END, code_refs=refs, file=rom, space=space, **kwargs)  # type: ignore[arg-type]
    return table, space


def _entries(rom: io.BytesIO, table: int = TABLE) -> list[int]:
    rom.seek(table)
    raw = rom.read(2 * COUNT)
    return [table + int.from_bytes(raw[2 * i : 2 * i + 2], "little") for i in range(COUNT)]


def _record_at(rom: io.BytesIO, at: int, size: int) -> bytes:
    rom.seek(at)
    return rom.read(size)


def test_unchanged_writes_nothing() -> None:
    rom = _rom()
    before = rom.getvalue()
    table, _ = _table(rom, RECORDS)
    assert table.write() == "unchanged"
    assert rom.getvalue() == before


def test_shrinking_is_in_place_with_leftover_zeroed() -> None:
    rom = _rom()
    table, _ = _table(rom, [b"\xa1" * 4, RECORDS[1], RECORDS[2]])
    assert table.write() == "in_place"
    assert _record_at(rom, FIRST, 8) == b"\xa1" * 4 + bytes(4)
    assert _entries(rom) == [FIRST, FIRST + 8, FIRST + 16]


def test_small_growth_repacks_into_region_slack() -> None:
    rom = _rom()
    table, _ = _table(rom, [b"\xa1" * 12, RECORDS[1], RECORDS[2]])
    assert table.write() == "repack"
    assert _entries(rom) == [FIRST, FIRST + 12, FIRST + 20]
    assert _record_at(rom, FIRST + 20, 8) == RECORDS[2]


def test_larger_growth_moves_one_record_within_the_bank() -> None:
    rom = _rom()
    table, _ = _table(rom, [b"\xa1" * 40, RECORDS[1], RECORDS[2]])
    assert table.write() == "move_record"
    first = _entries(rom)[0]
    assert bank_of(first) == bank_of(TABLE)
    assert _record_at(rom, first, 40) == b"\xa1" * 40
    assert _record_at(rom, FIRST, 8) == bytes(8)


def test_writing_twice_after_a_move_targets_the_new_record() -> None:
    rom = _rom()
    table, _ = _table(rom, [b"\xa1" * 40, RECORDS[1], RECORDS[2]])
    table.write()
    moved = _entries(rom)[0]
    table.records[0] = _Rec(b"\xa9" * 40)
    assert table.write() == "in_place"
    assert _entries(rom)[0] == moved
    assert _record_at(rom, moved, 40) == b"\xa9" * 40


def test_make_room_is_asked_before_giving_up() -> None:
    rom = _rom(gap=0)
    asked: list[int] = []

    def make_room(bank: int) -> bool:
        asked.append(bank)
        table.space.free(GAP, 0x100)  # type: ignore[union-attr]
        return True

    table, _ = _table(rom, [b"\xa1" * 40, RECORDS[1], RECORDS[2]], make_room=make_room)
    assert table.write() == "move_record"
    assert asked == [bank_of(TABLE)]


def test_no_room_and_not_movable_raises() -> None:
    rom = _rom(gap=0)
    table, _ = _table(rom, [b"\xa1" * 40, RECORDS[1], RECORDS[2]])
    with pytest.raises(TableNotMovable):
        table.write()


def test_whole_table_move_rewrites_code_refs_and_frees_the_region() -> None:
    rom = _rom(gap=0)
    table, space = _table(rom, [b"\xa1" * 40, RECORDS[1], RECORDS[2]], movable=True)
    assert table.write() == "move_table"
    assert bank_of(table.address) == bank_of(EXPANSION.start)
    assert _record_at(rom, CODE, 3) == CodeLong().encode(table.address)
    assert _record_at(rom, CODE + 3, 2) == CodeAbs16().encode(table.address)
    assert _record_at(rom, CODE + 5, 1) == CodeBank().encode(table.address)
    assert _entries(rom, table.address)[0] == table.address + 2 * COUNT
    assert _record_at(rom, TABLE, REGION_END - TABLE) == bytes(REGION_END - TABLE)
    assert space.alloc(REGION_END - TABLE - 32, bank=bank_of(TABLE)) >= TABLE


def test_changed_code_ref_raises_before_writing() -> None:
    rom = _rom(gap=0)
    rom.seek(CODE)
    rom.write(b"\x00\x00\x00")
    before = rom.getvalue()
    table, _ = _table(rom, [b"\xa1" * 40, RECORDS[1], RECORDS[2]], movable=True)
    with pytest.raises(CodeRefMismatch):
        table.write()
    assert rom.getvalue() == before


def test_pinned_address_in_region_blocks_repack() -> None:
    rom = _rom()
    table, _ = _table(rom, [b"\xa1" * 12, RECORDS[1], RECORDS[2]], pinned={FIRST + 16})
    assert table.write() == "move_record"


def test_record_never_straddles_a_bank() -> None:
    rom = _rom(gap=0)
    table, _ = _table(rom, [b"\xa1" * 40, RECORDS[1], RECORDS[2]], movable=True)
    table.write()
    for start in _entries(rom, table.address):
        assert bank_of(start) == bank_of(start + 39)


def test_no_space_anywhere_raises_no_free_space() -> None:
    rom = _rom(gap=0)
    table, space = _table(rom, [b"\xa1" * (BANK_SIZE - 8), RECORDS[1], RECORDS[2]], movable=True)
    with pytest.raises(NoFreeSpace):
        table.write()


def test_a_fresh_table_knows_the_size_of_a_moved_record() -> None:
    rom = _rom()
    table, space = _table(rom, [b"\xa1" * 40, RECORDS[1], RECORDS[2]])
    table.write()
    again = Table("t", TABLE, [_Rec(b"\xa1" * 40), _Rec(RECORDS[1]), _Rec(RECORDS[2])], REGION_END, file=rom, space=space)
    assert again.write() == "unchanged"
    again.records[0] = _Rec(b"\xa2" * 40)
    assert again.write() == "in_place"
