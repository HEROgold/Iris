"""IP effect scripts (table 0xAF1EF, $95:F1EF, 141 entries) on ``rom_space.Table``.

Each entry points at a ``$FF`` marker; the L2BASM script follows it. Jumps in the script are relative to the marker,
so an effect is one ``Script`` whose body starts with ``Data(b"\\xff")`` and the ``effect`` label, assembled at origin 0.

``IPAttack.effect`` is an index into this table, and several IPs share one effect (the mirror IPs all use ``$5C``).
Editing an ``IPEffect`` changes every IP that uses its index.
"""

from functools import cache

from helpers.files import write_file
from logger import iris
from rom_space.place import CodeAbs16, CodeLong, PointerSite
from rom_space.table import Table
from scripting.core import Data, Item, Label, Script, assemble
from scripting.l2basm import L2BASM, parse_record
from scripting.l2basm.helpers import block
from scripting.l2basm.records import IP_EFFECT_COUNT, ip_effect_records, read_record, table_address, table_bound


MARKER = b"\xff"
IP_EFFECT_CODE_REFS: list[PointerSite] = [
    PointerSite(0xF46E, CodeLong()),  # LDA $95F1EF,X (accessor at $81:F46B)
    PointerSite(0xF473, CodeAbs16()),  # ADC #$F1EF
]
"""Known so far; the accessor returns only the low word, so its callers' bank assumptions still need listing (HER-199)."""
IP_EFFECTS_MOVABLE = False
"""True once a moved table passes an emulator check (HER-199)."""


class IPEffect:
    """One IP effect script. Every IP whose ``effect`` is ``index`` runs it, so an edit applies to all of them."""

    def __init__(self, index: int, code: Script) -> None:
        self.index = index
        self.code = code

    def __repr__(self) -> str:
        return f"<IPEffect {self.index}>"

    @classmethod
    def from_index(cls, index: int) -> "IPEffect":
        return ip_effect_table().records[index]  # type: ignore[return-value]

    @classmethod
    def reread(cls, index: int) -> "IPEffect":
        """Drop the cached table and read this effect again from the output ROM (appended effects are kept)."""
        ip_effect_table.cache_clear()
        return cls.from_index(index)

    def build(self) -> bytes:
        return assemble(self.code, 0).data

    def write(self) -> None:
        iris.debug(f"Writing IP effect {self.index}")
        ip_effect_table().write()


_count = IP_EFFECT_COUNT
"""Entries in the table this run: vanilla plus appended effects."""


def _read(index: int, record: bytes, entries: dict[str, int], *, trailing: bool) -> IPEffect:
    parsed = parse_record(record, entries, start=0)
    code = parsed.script
    if trailing and parsed.end < len(record):  # unreached bytes up to the next record stay as they are
        code.body.append(Data(record[parsed.end :]))
    return IPEffect(index, code)


@cache
def ip_effect_table() -> Table:
    """Every IP effect on ``rom_space.Table``. Bank $95 has no free space after the table: growth repacks or moves it."""
    address = table_address(write_file, "ip_effect")
    bound = table_bound(write_file, address)
    records = [
        _read(rec.index, read_record(write_file, rec), rec.entries, trailing=address <= rec.start < bound)
        for rec in ip_effect_records(write_file, _count)
    ]
    return Table(
        "ip_effects",
        address,
        records,  # type: ignore[arg-type]
        bound,
        code_refs=IP_EFFECT_CODE_REFS,
        movable=IP_EFFECTS_MOVABLE,
    )


def append_ip_effect(items: list[Item]) -> int:
    """Add a new IP effect running ``items``; returns its index for ``IPAttack.effect``. Written by the next write."""
    global _count  # noqa: PLW0603 (the entry count lives as long as the output ROM)
    table = ip_effect_table()
    index = table.append(IPEffect(len(table.records), Script(L2BASM, [Data(MARKER), Label("effect"), *block(items)])))  # type: ignore[arg-type]
    _count = len(table.records)
    return index


def reset_ip_effect_table() -> None:
    global _count  # noqa: PLW0603
    _count = IP_EFFECT_COUNT
    ip_effect_table.cache_clear()
