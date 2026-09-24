"""The $42 subroutine table (0xB7ADD, $96:FADD): 41 L2BASM bodies every other script calls with ``42 XX 00``.

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
from scripting.core import Script, assemble
from scripting.l2basm import parse_record
from scripting.l2basm.records import SUBROUTINE_TABLE, read_record, subroutine_records


SUBROUTINE_CODE_REFS: list[PointerSite] = [
    PointerSite(0x2BDA3, CodeLong()),  # LDA $96FADD,X
    PointerSite(0x2BDA8, CodeAbs16()),  # ADC #$FADD
    PointerSite(0x2BD9A, CodeBank()),  # LDA #$96 ; STA $BD
]
SUBROUTINES_MOVABLE = False
"""Set to True once HER-188's emulator check of a moved table passes."""
BANK_96 = bank_of(SUBROUTINE_TABLE)


class Subroutine:
    def __init__(self, index: int, code: Script, start: int) -> None:
        self.index = index
        self.code = code
        self._start = start

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
    for rec in subroutine_records(write_file, table=address):
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


def reset() -> None:
    subroutine_table.cache_clear()


def make_room_in_bank_96(bank: int) -> bool:
    """Move the $42 table out of bank $96 so monster and item records can grow there. True if it moved."""
    table = subroutine_table()
    if bank != BANK_96 or bank_of(table.address) != BANK_96 or not SUBROUTINES_MOVABLE:
        return False
    table.movable = True
    table.move()
    return True
