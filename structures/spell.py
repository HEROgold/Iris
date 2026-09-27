"""Spell records (table 0xAFA5B, $95:FA5B, 40 records) on ``rom_space.Table``.

A record is 17 header bytes (name, element, casters, MP cost, price, ...), the u16 offset of its L2BASM effect script
at ``+0x11`` (``0x13`` in vanilla), then the script. Jumps in the script are relative to the record start, so a record
can move within bank $95 without changing its bytes.
"""

from functools import cache
from typing import Self

from _types.objects import Cache
from abc_.pointers import Pointer
from enums.flags import CastableSpells
from errors import SpellNotFound
from helpers.files import write_file
from logger import iris
from rom_space.table import Table
from scripting.core import Data, Label, Script, assemble
from scripting.l2basm import L2BASM, parse_record
from scripting.l2basm.records import (
    SPELL_COUNT,
    SPELL_SCRIPT_FIELD,
    RecordSource,
    read_record,
    spell_records,
    table_address,
    table_bound,
)
from tables import SpellObject


SPELLS_ADDRESS = 0x000AFAAB
SCRIPT_ORIGIN = SPELL_SCRIPT_FIELD + 2
"""Record offset of the effect script: right after its u16 offset."""


class Spell(Pointer):
    _int_cache = Cache[int, Self]()
    _name_cache = Cache[str, Self]()

    code: Script
    """The effect script, entry label ``effect``, assembled at record offset ``SCRIPT_ORIGIN``."""
    external_effect: int | None
    """Raw record-relative effect offset when it points outside this record (shared code in some base patches)."""

    def __init__(  # noqa: PLR0913, PLR0917 (one argument per header field)
        self,
        name: str,
        unk1: int,
        element: int,
        characters: CastableSpells,
        unk4: int,
        mp_cost: int,
        zero: int,
        price: int,
    ) -> None:
        self.name = name
        self.unk1 = unk1
        self.element = element
        self.characters = characters
        self.unk4 = unk4
        self.mp_cost = mp_cost
        self.zero = zero
        self.price = price
        self.index = -1
        self.code = Script(L2BASM, [])
        self.external_effect = None

    def __repr__(self) -> str:
        return f"<Spell {self.index} {self.name!r}>"

    @classmethod
    def from_name(cls, name: str) -> Self:
        if inst := cls._name_cache.from_cache(name):
            return inst
        for index in range(SPELL_COUNT):
            inst = cls.from_index(index)
            if inst.name == name:
                cls._name_cache.to_cache(name, inst)
                return inst
        msg = f"Spell with name {name} not found."
        raise SpellNotFound(msg)

    @classmethod
    def from_index(cls, index: int) -> Self:
        if inst := cls._int_cache.from_cache(index):
            return inst
        rec = _record_sources().get(index)
        if rec is None:
            msg = f"Spell with index {index} not found."
            raise SpellNotFound(msg)
        inst = cls._from_record(rec)
        cls._int_cache.to_cache(index, inst)
        return inst

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        """The spell whose record starts at ``pointer`` (a vanilla ``SpellObject.pointers`` entry or a current start)."""
        if pointer in SpellObject.pointers:
            return cls.from_index(SpellObject.pointers.index(pointer))
        for rec in _record_sources().values():
            if rec.start == pointer:
                return cls.from_index(rec.index)
        msg = f"No spell record starts at {pointer:#x}."
        raise SpellNotFound(msg)

    @classmethod
    def reread(cls, index: int) -> Self:
        """Drop the cached spells and read this one again from the output ROM."""
        reset_spell_table()
        return cls.from_index(index)

    @classmethod
    def _from_record(cls, rec: RecordSource) -> Self:
        record = read_record(write_file, rec)  # the output ROM, so base-patch edits are what we read
        header = record[:SPELL_SCRIPT_FIELD]
        pos = SpellObject.name_text
        name = header[:pos].decode("latin-1")
        unk1, element, characters, unk4, mp_cost = header[pos : pos + 5]
        zero = int.from_bytes(header[pos + 5 : pos + 7], "little")
        price = int.from_bytes(header[pos + 7 : pos + 9], "little")
        inst = cls(name, unk1, element, CastableSpells(characters), unk4, mp_cost, zero, price)
        Pointer.__init__(inst, rec.start)
        inst.index = rec.index
        in_region = rec.start < table_bound(write_file, table_address(write_file, "spell"))
        if "effect" in rec.entries:
            parsed = parse_record(record, rec.entries, start=SCRIPT_ORIGIN)
            inst.code = parsed.script
            if in_region and parsed.end < len(record):  # unreached bytes up to the next record stay as they are
                inst.code.body.append(Data(record[parsed.end :]))
        else:
            inst.external_effect = rec.external["effect"]
            inst.code = Script(L2BASM, [Data(record[SCRIPT_ORIGIN:])] if in_region else [])
        return inst

    def header_bytes(self, effect: int) -> bytes:
        return b"".join([
            self.name.encode("latin-1").ljust(SpellObject.name_text, b" ")[: SpellObject.name_text],
            bytes([self.unk1, self.element, self.characters.value, self.unk4, self.mp_cost]),
            self.zero.to_bytes(2, "little"),
            self.price.to_bytes(2, "little"),
            effect.to_bytes(2, "little"),
        ])

    def build(self) -> bytes:
        """The whole record: header, effect offset, then the script (jumps are record-relative)."""
        out = assemble(self.code, SCRIPT_ORIGIN)
        if self.external_effect is not None and not any(isinstance(i, Label) and i.name == "effect" for i in self.code.body):
            return self.header_bytes(self.external_effect) + out.data
        return self.header_bytes(SCRIPT_ORIGIN + out.labels["effect"]) + out.data

    def write(self) -> None:
        iris.debug(f"Writing Spell {self.index} {self.name!r}")
        table = spell_table()
        table.records[self.index] = self  # a copy (deepcopy in the spell randomizer) replaces the cached record
        Spell._int_cache.to_cache(self.index, self)
        table.write()


@cache
def _record_sources() -> dict[int, RecordSource]:
    return {rec.index: rec for rec in spell_records(write_file)}


@cache
def spell_table() -> Table:
    """Every spell record on ``rom_space.Table``. A grown record moves within bank $95 (178 free bytes)."""
    address = table_address(write_file, "spell")
    records = [Spell.from_index(i) for i in range(SPELL_COUNT)]
    return Table("spells", address, records, table_bound(write_file, address))  # type: ignore[arg-type]


def reset_spell_table() -> None:
    spell_table.cache_clear()
    _record_sources.cache_clear()
    Spell._int_cache.clear()  # noqa: SLF001
    Spell._name_cache.clear()  # noqa: SLF001
