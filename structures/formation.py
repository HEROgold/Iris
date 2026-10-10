# Code for reference when creation BattleFormation class
# class FormationObject:
#     monster_indexes: list = 8
#     address = 0xBBE93
#     count = 192
# class BossFormationObject:
#     reference_pointer = 2
#     address = 0xBC53D
#     count = 39

from typing import Self

from abc_.pointers import Pointer
from helpers.files import read_file, restore_pointer, write_file
from structures.monster import Monster


EMPTY_SLOT = 0xFF
"""Monster index that marks an unused slot in a formation row."""


class BattleFormation(Pointer):
    address: int | None
    index: int | None
    max_monsters = 8

    def __init__(self, monsters: list[Monster]) -> None:
        self.monsters = monsters

    # We Don't implement a from_index method, since there's 3 tables to read from.

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        pointer = address + index * 8
        read_file.seek(pointer)
        inst = cls.from_pointer(pointer)
        inst.address = address
        inst.index = index
        return inst

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        read_file.seek(pointer)
        _0 = read_file.read(1)
        _1 = read_file.read(1)
        _2 = read_file.read(1)
        _3 = read_file.read(1)
        _4 = read_file.read(1)
        _5 = read_file.read(1)
        _6 = read_file.read(1)
        _7 = read_file.read(1)

        monsters = [
            Monster.from_index(int.from_bytes(i))
            for i in [_0, _1, _2, _3, _4, _5, _6, _7]
        ]

        inst = cls(monsters)
        inst.pointer = pointer
        return inst

    @classmethod
    @restore_pointer
    def monster_indexes(cls, address: int, index: int) -> list[int]:
        """The eight raw monster-index bytes of one formation row.

        :meth:`from_table` builds a :class:`Monster` per slot, which parses that monster's AI
        scripts. Anything that only needs the slot contents (or the levels behind them) should read
        the row directly through this, which is much cheaper.
        """
        read_file.seek(address + index * cls.max_monsters)
        return list(read_file.read(cls.max_monsters))

    @classmethod
    def average_level_of(cls, address: int, index: int) -> float | None:
        """:attr:`average_level` for a formation row, without instantiating its monsters."""
        levels = [
            Monster.level_from_index(i)
            for i in cls.monster_indexes(address, index)
            if i != EMPTY_SLOT
        ]
        if not levels:
            return None
        return sum(levels) / len(levels)

    @property
    def average_level(self) -> float | None:
        """Mean level of the monsters actually present in this formation.

        Slot index ``0xFF`` is the empty-slot sentinel (``Monster.from_index`` turns it into a
        level-0 "Dummy"), so it is filtered out by index rather than by level -- a real monster may
        legitimately have level 0. Returns ``None`` when every slot is empty.
        """
        levels = [m.stats.level for m in self.monsters if m.index != EMPTY_SLOT]
        if not levels:
            return None
        return sum(levels) / len(levels)

    def write(self) -> None:
        write_file.seek(self.pointer)
        for monster in self.monsters:
            write_file.write(monster.index.to_bytes())
