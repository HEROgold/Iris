"""The $42 subroutine table (0xB7ADD, $96:FADD): 41 L2BASM bodies every other script calls with ``42 XX 00``.

Every monster, capsule, item and IP effect that calls a subroutine shares it: editing a body changes all of them.
``scripting.l2basm.opcodes.SUBROUTINE_DESCRIPTIONS`` says what each vanilla body does.

The accessor at 0x2BD99 loads the bank with ``LDA #$96; STA $BD`` and the pointer with
``LDA $96FADD,X; CLC; ADC #$FADD``. Moving the table rewrites those three operands. Jumps inside a body are relative
to the body start, so a body's bytes don't depend on where it sits.
"""

from functools import cache

from helpers.addresses import address_from_lorom
from helpers.files import write_file
from rom_space.place import CodeAbs16, CodeBank, CodeLong, PointerSite
from rom_space.pool import bank_of
from rom_space.table import Table
from scripting.core import Item, Label, Script, assemble
from scripting.l2basm import L2BASM, parse_record
from scripting.l2basm.helpers import routine
from scripting.l2basm.records import SUBROUTINE_COUNT, SUBROUTINE_TABLE, read_record, subroutine_records


SUBROUTINE_CODE_REFS: list[PointerSite] = [
    PointerSite(0x2BDA3, CodeLong()),  # LDA $96FADD,X
    PointerSite(0x2BDA8, CodeAbs16()),  # ADC #$FADD
    PointerSite(0x2BD9A, CodeBank()),  # LDA #$96 ; STA $BD
]
SUBROUTINES_MOVABLE = True
"""The code refs are verified: a moved table played correctly in an emulator (HER-188, 2026-09-25)."""
BANK_96 = bank_of(SUBROUTINE_TABLE)


class Subroutine:
    """One $42 body (entry label ``body``). Every script that calls ``42 index 00`` runs it."""

    def __init__(self, index: int, code: Script, start: int) -> None:
        self.index = index
        self.code = code
        self._start = start

    @classmethod
    def from_index(cls, index: int) -> "Subroutine":
        return subroutine_table().records[index]  # type: ignore[return-value]

    def build(self) -> bytes:
        return assemble(self.code, self._start).data


def _current_table_address() -> int:
    """Where the table is now, read back from the ``LDA long,X`` operand (it moves with the table)."""
    write_file.seek(SUBROUTINE_CODE_REFS[0].at)
    return address_from_lorom(int.from_bytes(write_file.read(3), "little"))


@cache
def subroutine_table() -> Table:
    address = _current_table_address()
    records = []
    ends = []
    for rec in subroutine_records(write_file, table=address, count=_count):
        parsed = parse_record(read_record(write_file, rec), rec.entries)
        assert parsed.start == 0, rec.index
        records.append(Subroutine(rec.index, parsed.script, parsed.start))
        ends.append(rec.start + parsed.end)
    return Table(
        "subroutines",
        address,
        records,  # type: ignore[arg-type]
        max(ends),
        code_refs=SUBROUTINE_CODE_REFS,
        movable=SUBROUTINES_MOVABLE,
    )


_count = SUBROUTINE_COUNT
"""Entries in the table this run: vanilla plus appended subroutines."""


def append_subroutine(items: list[Item]) -> int:
    """Add a subroutine running ``items``; returns its number for ``42 XX 00``. Written by the next table write.

    A RETURN (``43``) is added if ``items`` don't end with one.

    Bank $96 has no free space, so the write moves the table out of it (``SUBROUTINES_MOVABLE``).
    """
    global _count  # noqa: PLW0603 (the entry count lives as long as the output ROM)
    table = subroutine_table()
    index = table.append(Subroutine(len(table.records), Script(L2BASM, [Label("body"), *routine(items)]), 0))  # type: ignore[arg-type]
    _count = len(table.records)
    return index


def reread_table() -> Table:
    """Drop the cached table and read it again from the output ROM (appended subroutines are kept)."""
    subroutine_table.cache_clear()
    return subroutine_table()


def reset() -> None:
    global _count  # noqa: PLW0603
    _count = SUBROUTINE_COUNT
    subroutine_table.cache_clear()


def make_room_in_bank_96(bank: int) -> bool:
    """Move the $42 table out of bank $96 so monster and item records can grow there. True if it moved."""
    table = subroutine_table()
    if bank != BANK_96 or bank_of(table.address) != BANK_96 or not SUBROUTINES_MOVABLE:
        return False
    table.movable = True
    table.move()
    return True
